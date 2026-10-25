from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.domain.errors import (
    GroupNameTakenError,
    RequestAlreadyPendingError,
    StorageUnavailableError,
    UserIdTakenError,
)
from backend.domain.models import Member, MembershipStatus, RequestStatus, Session
from backend.storage.store import Store

ADA = Member(user_id="ada", display_name="Ada Lovelace")
BOB = Member(user_id="bob", display_name="Bob")


@pytest.fixture
def store(tmp_path: Path) -> Store:
    store = Store(tmp_path / "trip.db")
    store.create_schema()
    with store.transaction() as tx:
        tx.add_member(ADA)
        tx.add_member(BOB)
    return store


def test_schema_is_created_on_a_fresh_file(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"

    Store(path).create_schema()

    assert path.is_file()


def test_create_schema_is_idempotent(store: Store) -> None:
    store.create_schema()

    with store.transaction() as tx:
        assert tx.get_member("ada") == ADA


def test_a_transaction_that_raises_leaves_no_rows(store: Store) -> None:
    with pytest.raises(RuntimeError), store.transaction() as tx:
        tx.add_member(Member(user_id="carol", display_name="Carol"))
        raise RuntimeError

    with store.transaction() as tx:
        assert tx.get_member("carol") is None


def test_duplicate_user_id_is_refused(store: Store) -> None:
    with pytest.raises(UserIdTakenError), store.transaction() as tx:
        tx.add_member(Member(user_id="ada", display_name="Another Ada"))


def test_duplicate_group_name_is_refused_ignoring_case(store: Store) -> None:
    with store.transaction() as tx:
        tx.add_group("Goa 2027", "", "ada")

    with pytest.raises(GroupNameTakenError), store.transaction() as tx:
        tx.add_group("GOA 2027", "", "bob")


def test_second_pending_request_is_refused(store: Store) -> None:
    with store.transaction() as tx:
        group_id = tx.add_group("Goa", "", "ada")
        tx.add_join_request(group_id, "bob")

    with pytest.raises(RequestAlreadyPendingError), store.transaction() as tx:
        tx.add_join_request(group_id, "bob")


def test_a_decided_request_can_be_followed_by_a_new_one(store: Store) -> None:
    with store.transaction() as tx:
        group_id = tx.add_group("Goa", "", "ada")
        first = tx.add_join_request(group_id, "bob")
        assert tx.decide_request(first.request_id, RequestStatus.REJECTED)
        second = tx.add_join_request(group_id, "bob")

    assert second.request_id != first.request_id


def test_deciding_an_already_decided_request_changes_nothing(store: Store) -> None:
    with store.transaction() as tx:
        group_id = tx.add_group("Goa", "", "ada")
        request = tx.add_join_request(group_id, "bob")
        assert tx.decide_request(request.request_id, RequestStatus.APPROVED)

        assert not tx.decide_request(request.request_id, RequestStatus.REJECTED)
        assert tx.get_pending_request(request.request_id) is None


def test_corrupted_file_raises_storage_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "trip.db"
    store = Store(path)
    store.create_schema()
    path.write_bytes(b"this is not a database" * 100)

    with pytest.raises(StorageUnavailableError), store.transaction() as tx:
        tx.get_member("ada")


def test_sessions_round_trip_and_delete(store: Store) -> None:
    session = Session(
        token_hash="h" * 64, user_id="ada", expires_at=datetime(2030, 1, 1, tzinfo=UTC)
    )

    with store.transaction() as tx:
        tx.add_session(session)
        assert tx.get_session(session.token_hash) == session
        tx.delete_session(session.token_hash)
        assert tx.get_session(session.token_hash) is None


def test_group_summaries_report_counts_and_viewer_status(store: Store) -> None:
    with store.transaction() as tx:
        tx.add_member(Member(user_id="carol", display_name="Carol"))
        goa = tx.add_group("Goa", "Beach", "ada")
        tx.add_membership(goa, "bob")
        tx.add_join_request(goa, "carol")

        statuses = {
            viewer: tx.group_summary(goa, viewer) for viewer in ("ada", "bob", "carol", "nobody")
        }

    summary = statuses["ada"]
    assert summary is not None
    assert (summary.name, summary.description, summary.owner_display_name) == (
        "Goa",
        "Beach",
        "Ada Lovelace",
    )
    assert summary.member_count == 2
    assert {viewer: s.my_status for viewer, s in statuses.items() if s} == {
        "ada": MembershipStatus.OWNER,
        "bob": MembershipStatus.MEMBER,
        "carol": MembershipStatus.PENDING,
        "nobody": MembershipStatus.NONE,
    }


def test_browse_searches_ignoring_case_and_limits(store: Store) -> None:
    with store.transaction() as tx:
        for name in ("Goa 2027", "Ladakh", "goa monsoon", "100% Fun"):
            tx.add_group(name, "", "ada")

        assert [g.name for g in tx.browse_groups("bob", "GOA", 50)] == ["Goa 2027", "goa monsoon"]
        assert [g.name for g in tx.browse_groups("bob", None, 2)] == ["100% Fun", "Goa 2027"]
        # Wildcards in the search are literal, not LIKE patterns.
        assert tx.browse_groups("bob", "%", 50)[0].name == "100% Fun"
        assert tx.browse_groups("bob", "_", 50) == []


def test_member_groups_lists_only_groups_the_member_is_in(store: Store) -> None:
    with store.transaction() as tx:
        goa = tx.add_group("Goa", "", "ada")
        tx.add_group("Ladakh", "", "ada")
        tx.add_membership(goa, "bob")

        assert [g.name for g in tx.member_groups("bob")] == ["Goa"]
        assert [g.name for g in tx.member_groups("ada")] == ["Goa", "Ladakh"]


def test_group_lookups_members_and_pending_requests(store: Store) -> None:
    with store.transaction() as tx:
        goa = tx.add_group("Goa", "", "ada")
        request = tx.add_join_request(goa, "bob")

        assert tx.find_group_id("GOA") == goa
        assert tx.find_group_id("Nowhere") is None
        assert tx.group_summary(goa + 1, "ada") is None
        assert tx.group_members(goa) == (ADA,)
        assert tx.count_owned_groups("ada") == 1
        assert tx.count_pending_requests("bob") == 1
        assert tx.get_pending_request(request.request_id) == request
        assert [(p.request_id, p.display_name) for p in tx.pending_requests(goa)] == [
            (request.request_id, "Bob")
        ]


def test_storage_errors_never_carry_the_bound_values(store: Store) -> None:
    session = Session(
        token_hash="h" * 64, user_id="ghost", expires_at=datetime(2030, 1, 1, tzinfo=UTC)
    )

    # An unknown user_id breaks the foreign key: an error nothing above storage anticipates.
    with pytest.raises(StorageUnavailableError) as raised, store.transaction() as tx:
        tx.add_session(session)

    message = str(raised.value.__cause__)
    assert "FOREIGN KEY" in message
    assert "ghost" not in message
    assert "h" * 64 not in message
