import logging
from dataclasses import replace

from backend.domain.errors import (
    AlreadyMemberError,
    ForbiddenError,
    LimitReachedError,
    NotFoundError,
    RequestAlreadyPendingError,
)
from backend.domain.models import (
    BROWSE_LIMIT,
    MAX_GROUP_MEMBERS,
    MAX_OWNED_GROUPS,
    MAX_PENDING_REQUESTS,
    GroupDetail,
    GroupSummary,
    JoinRequest,
    Member,
    MembershipStatus,
    RequestStatus,
)
from backend.storage.store import Store, Transaction

logger = logging.getLogger(__name__)

IN_GROUP = {MembershipStatus.OWNER, MembershipStatus.MEMBER}


def _summary(tx: Transaction, group_id: int, actor: Member) -> GroupSummary:
    summary = tx.group_summary(group_id, actor.user_id)
    if summary is None:
        raise NotFoundError
    return summary


def create_group(store: Store, actor: Member, name: str, description: str) -> GroupSummary:
    with store.transaction() as tx:
        if tx.count_owned_groups(actor.user_id) >= MAX_OWNED_GROUPS:
            raise LimitReachedError
        group_id = tx.add_group(name, description, actor.user_id)
        summary = _summary(tx, group_id, actor)
    logger.info("created group group_id=%s owner=%s", group_id, actor.user_id)
    return summary


def my_groups(store: Store, actor: Member) -> list[GroupSummary]:
    with store.transaction() as tx:
        return tx.member_groups(actor.user_id)


def browse_groups(store: Store, actor: Member, search: str | None) -> list[GroupSummary]:
    with store.transaction() as tx:
        return tx.browse_groups(actor.user_id, search, BROWSE_LIMIT)


def group_detail(store: Store, actor: Member, group_id: int) -> GroupDetail:
    """Everyone signed in sees the summary; members see who's in; the owner sees requests too."""
    with store.transaction() as tx:
        summary = _summary(tx, group_id, actor)
        in_group = summary.my_status in IN_GROUP
        owner = summary.my_status == MembershipStatus.OWNER
        return GroupDetail(
            summary=summary,
            members=tx.group_members(group_id) if in_group else None,
            pending_requests=tx.pending_requests(group_id) if owner else None,
        )


def _request_to_join(tx: Transaction, actor: Member, group_id: int) -> JoinRequest:
    status = _summary(tx, group_id, actor).my_status
    if status in IN_GROUP:
        raise AlreadyMemberError
    if status == MembershipStatus.PENDING:
        raise RequestAlreadyPendingError
    if tx.count_pending_requests(actor.user_id) >= MAX_PENDING_REQUESTS:
        raise LimitReachedError
    return tx.add_join_request(group_id, actor.user_id)


def request_to_join(store: Store, actor: Member, group_id: int) -> JoinRequest:
    with store.transaction() as tx:
        return _request_to_join(tx, actor, group_id)


def request_to_join_by_name(store: Store, actor: Member, name: str) -> JoinRequest:
    with store.transaction() as tx:
        group_id = tx.find_group_id(name)
        if group_id is None:
            raise NotFoundError
        return _request_to_join(tx, actor, group_id)


def _decide(store: Store, actor: Member, request_id: int, decision: RequestStatus) -> JoinRequest:
    with store.transaction() as tx:
        request = tx.get_pending_request(request_id)
        if request is None:
            raise NotFoundError
        summary = _summary(tx, request.group_id, actor)
        if summary.my_status != MembershipStatus.OWNER:
            raise ForbiddenError
        approving = decision == RequestStatus.APPROVED
        if approving and summary.member_count >= MAX_GROUP_MEMBERS:
            raise LimitReachedError
        if not tx.decide_request(request_id, decision):
            raise NotFoundError
        if approving:
            tx.add_membership(request.group_id, request.user_id)
    logger.info(
        "%s join request request_id=%s group_id=%s user_id=%s by=%s",
        decision,
        request_id,
        request.group_id,
        request.user_id,
        actor.user_id,
    )
    return replace(request, status=decision)


def approve(store: Store, actor: Member, request_id: int) -> JoinRequest:
    return _decide(store, actor, request_id, RequestStatus.APPROVED)


def reject(store: Store, actor: Member, request_id: int) -> JoinRequest:
    return _decide(store, actor, request_id, RequestStatus.REJECTED)
