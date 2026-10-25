import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    ColumnElement,
    Connection,
    RowMapping,
    case,
    create_engine,
    delete,
    event,
    exists,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.pool import NullPool

from backend.domain.errors import (
    GroupNameTakenError,
    RequestAlreadyPendingError,
    StorageUnavailableError,
    UserIdTakenError,
)
from backend.domain.models import (
    GroupSummary,
    JoinRequest,
    Member,
    MembershipStatus,
    PendingRequest,
    RequestStatus,
    Session,
    name_key,
)
from backend.storage.schema import groups, join_requests, members, memberships, metadata, sessions

BUSY_TIMEOUT_S = 5


def _on_connect(dbapi_connection: sqlite3.Connection, _record: object) -> None:
    # Hand transaction control to SQLAlchemy, so _on_begin decides how each one starts.
    dbapi_connection.isolation_level = None
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


def _on_begin(connection: Connection) -> None:
    # IMMEDIATE takes the write lock up front. Two deferred transactions that both read and then
    # write would fail with "database is locked" instead of waiting their turn.
    connection.exec_driver_sql("BEGIN IMMEDIATE")


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        # NullPool: no connection holds the file open between requests.
        self._engine = create_engine(
            f"sqlite:///{path}", poolclass=NullPool, connect_args={"timeout": BUSY_TIMEOUT_S}
        )
        event.listen(self._engine, "connect", _on_connect)
        event.listen(self._engine, "begin", _on_begin)

    def create_schema(self) -> None:
        with self.transaction() as tx:
            metadata.create_all(tx.connection)

    @contextmanager
    def transaction(self) -> Generator["Transaction"]:
        """One unit of work: commits if the block succeeds, rolls back if it raises."""
        try:
            with self._engine.begin() as connection:
                yield Transaction(connection)
        except DBAPIError as exc:
            # Never leak SQL or driver messages: the API turns this into a generic 503.
            raise StorageUnavailableError from exc


class Transaction:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    # Members

    def add_member(self, member: Member) -> None:
        try:
            self.connection.execute(
                insert(members).values(user_id=member.user_id, display_name=member.display_name)
            )
        except IntegrityError as exc:
            raise UserIdTakenError from exc

    def get_member(self, user_id: str) -> Member | None:
        row = self.connection.execute(
            select(members.c.user_id, members.c.display_name).where(members.c.user_id == user_id)
        ).first()
        return Member(user_id=row.user_id, display_name=row.display_name) if row else None

    # Sessions

    def add_session(self, session: Session) -> None:
        self.connection.execute(
            insert(sessions).values(
                token_hash=session.token_hash,
                user_id=session.user_id,
                expires_at=int(session.expires_at.timestamp()),
            )
        )

    def get_session(self, token_hash: str) -> Session | None:
        row = self.connection.execute(
            select(sessions).where(sessions.c.token_hash == token_hash)
        ).first()
        if row is None:
            return None
        return Session(
            token_hash=row.token_hash,
            user_id=row.user_id,
            expires_at=datetime.fromtimestamp(row.expires_at, UTC),
        )

    def delete_session(self, token_hash: str) -> None:
        self.connection.execute(delete(sessions).where(sessions.c.token_hash == token_hash))

    # Groups

    def add_group(self, name: str, description: str, owner_id: str) -> int:
        try:
            group_id: int = self.connection.execute(
                insert(groups)
                .values(
                    name=name, name_key=name_key(name), description=description, owner_id=owner_id
                )
                .returning(groups.c.group_id)
            ).scalar_one()
        except IntegrityError as exc:
            raise GroupNameTakenError from exc
        self.add_membership(group_id, owner_id)
        return group_id

    def count_owned_groups(self, user_id: str) -> int:
        query = select(func.count()).select_from(groups).where(groups.c.owner_id == user_id)
        return self.connection.execute(query).scalar_one()

    def find_group_id(self, name: str) -> int | None:
        return self.connection.execute(
            select(groups.c.group_id).where(groups.c.name_key == name_key(name))
        ).scalar_one_or_none()

    def group_summary(self, group_id: int, viewer_id: str) -> GroupSummary | None:
        query = _summaries(viewer_id).where(groups.c.group_id == group_id)
        row = self.connection.execute(query).mappings().first()
        return _summary(row) if row else None

    def browse_groups(self, viewer_id: str, search: str | None, limit: int) -> list[GroupSummary]:
        query = _summaries(viewer_id)
        if search:
            query = query.where(groups.c.name_key.contains(name_key(search), autoescape=True))
        rows = self.connection.execute(query.order_by(groups.c.name_key).limit(limit)).mappings()
        return [_summary(row) for row in rows]

    def member_groups(self, user_id: str) -> list[GroupSummary]:
        query = _summaries(user_id).where(_is_member(user_id)).order_by(groups.c.name_key)
        return [_summary(row) for row in self.connection.execute(query).mappings()]

    def group_members(self, group_id: int) -> tuple[Member, ...]:
        rows = self.connection.execute(
            select(members.c.user_id, members.c.display_name)
            .join(memberships, memberships.c.user_id == members.c.user_id)
            .where(memberships.c.group_id == group_id)
            .order_by(members.c.display_name, members.c.user_id)
        )
        return tuple(Member(user_id=r.user_id, display_name=r.display_name) for r in rows)

    def count_members(self, group_id: int) -> int:
        query = (
            select(func.count()).select_from(memberships).where(memberships.c.group_id == group_id)
        )
        return self.connection.execute(query).scalar_one()

    def add_membership(self, group_id: int, user_id: str) -> None:
        self.connection.execute(insert(memberships).values(group_id=group_id, user_id=user_id))

    # Join requests

    def add_join_request(self, group_id: int, user_id: str) -> JoinRequest:
        try:
            request_id: int = self.connection.execute(
                insert(join_requests)
                .values(group_id=group_id, user_id=user_id, status=RequestStatus.PENDING)
                .returning(join_requests.c.request_id)
            ).scalar_one()
        except IntegrityError as exc:
            raise RequestAlreadyPendingError from exc
        return JoinRequest(
            request_id=request_id,
            group_id=group_id,
            user_id=user_id,
            status=RequestStatus.PENDING,
        )

    def count_pending_requests(self, user_id: str) -> int:
        query = (
            select(func.count())
            .select_from(join_requests)
            .where(
                join_requests.c.user_id == user_id,
                join_requests.c.status == RequestStatus.PENDING,
            )
        )
        return self.connection.execute(query).scalar_one()

    def get_pending_request(self, request_id: int) -> JoinRequest | None:
        row = self.connection.execute(
            select(join_requests).where(
                join_requests.c.request_id == request_id,
                join_requests.c.status == RequestStatus.PENDING,
            )
        ).first()
        if row is None:
            return None
        return JoinRequest(
            request_id=row.request_id,
            group_id=row.group_id,
            user_id=row.user_id,
            status=RequestStatus(row.status),
        )

    def pending_requests(self, group_id: int) -> tuple[PendingRequest, ...]:
        rows = self.connection.execute(
            select(join_requests.c.request_id, members.c.display_name)
            .join(members, members.c.user_id == join_requests.c.user_id)
            .where(
                join_requests.c.group_id == group_id,
                join_requests.c.status == RequestStatus.PENDING,
            )
            .order_by(join_requests.c.request_id)
        )
        return tuple(
            PendingRequest(request_id=r.request_id, display_name=r.display_name) for r in rows
        )

    def decide_request(self, request_id: int, status: RequestStatus) -> bool:
        """Records a decision on a pending request. False if it was already decided."""
        result = self.connection.execute(
            update(join_requests)
            .where(
                join_requests.c.request_id == request_id,
                join_requests.c.status == RequestStatus.PENDING,
            )
            .values(status=status)
        )
        return result.rowcount == 1


def _is_member(user_id: str) -> ColumnElement[bool]:
    return exists().where(
        memberships.c.group_id == groups.c.group_id, memberships.c.user_id == user_id
    )


def _summaries(viewer_id: str):
    owner = members.alias("owner")
    member_count = (
        select(func.count())
        .select_from(memberships)
        .where(memberships.c.group_id == groups.c.group_id)
        .scalar_subquery()
    )
    pending = exists().where(
        join_requests.c.group_id == groups.c.group_id,
        join_requests.c.user_id == viewer_id,
        join_requests.c.status == RequestStatus.PENDING,
    )
    my_status = case(
        (groups.c.owner_id == viewer_id, MembershipStatus.OWNER.value),
        (_is_member(viewer_id), MembershipStatus.MEMBER.value),
        (pending, MembershipStatus.PENDING.value),
        else_=MembershipStatus.NONE.value,
    )
    return select(
        groups.c.group_id,
        groups.c.name,
        groups.c.description,
        groups.c.owner_id,
        owner.c.display_name.label("owner_display_name"),
        member_count.label("member_count"),
        my_status.label("my_status"),
    ).join(owner, owner.c.user_id == groups.c.owner_id)


def _summary(row: RowMapping) -> GroupSummary:
    return GroupSummary(
        group_id=row["group_id"],
        name=row["name"],
        description=row["description"],
        owner_id=row["owner_id"],
        owner_display_name=row["owner_display_name"],
        member_count=row["member_count"],
        my_status=MembershipStatus(row["my_status"]),
    )
