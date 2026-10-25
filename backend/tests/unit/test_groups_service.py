import logging
from pathlib import Path

import pytest

from backend.domain.errors import (
    AlreadyMemberError,
    ForbiddenError,
    GroupNameTakenError,
    LimitReachedError,
    NotFoundError,
    RequestAlreadyPendingError,
)
from backend.domain.models import (
    MAX_GROUP_MEMBERS,
    MAX_OWNED_GROUPS,
    MAX_PENDING_REQUESTS,
    Member,
    MembershipStatus,
    RequestStatus,
)
from backend.services import groups
from backend.storage.store import Store

ADA = Member(user_id="ada", display_name="Ada")
BOB = Member(user_id="bob", display_name="Bob")
CAROL = Member(user_id="carol", display_name="Carol")


@pytest.fixture
def store(tmp_path: Path) -> Store:
    store = Store(tmp_path / "trip.db")
    store.create_schema()
    with store.transaction() as tx:
        for member in (ADA, BOB, CAROL):
            tx.add_member(member)
    return store


@pytest.fixture
def goa(store: Store) -> int:
    return groups.create_group(store, ADA, "Goa", "Beach").group_id


def test_create_group_makes_the_creator_owner(store: Store) -> None:
    summary = groups.create_group(store, ADA, "Goa", "Beach")

    assert (summary.name, summary.description, summary.member_count) == ("Goa", "Beach", 1)
    assert summary.my_status == MembershipStatus.OWNER


def test_create_group_refuses_a_taken_name(store: Store, goa: int) -> None:
    with pytest.raises(GroupNameTakenError):
        groups.create_group(store, BOB, "GOA", "")


def test_create_group_enforces_the_owned_group_limit(store: Store) -> None:
    for n in range(MAX_OWNED_GROUPS):
        groups.create_group(store, ADA, f"Trip {n}", "")

    with pytest.raises(LimitReachedError):
        groups.create_group(store, ADA, "One too many", "")


def test_create_group_logs_ids_only(store: Store, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="backend.services.groups"):
        group_id = groups.create_group(store, ADA, "Secret plans", "Private notes").group_id

    assert [r.getMessage() for r in caplog.records] == [
        f"created group group_id={group_id} owner=ada"
    ]


def test_browse_and_my_groups(store: Store, goa: int) -> None:
    groups.create_group(store, BOB, "Ladakh", "")

    assert [g.name for g in groups.browse_groups(store, CAROL, None)] == ["Goa", "Ladakh"]
    assert [g.name for g in groups.browse_groups(store, CAROL, "lad")] == ["Ladakh"]
    assert [g.name for g in groups.my_groups(store, ADA)] == ["Goa"]


def test_request_to_join_creates_a_pending_request(store: Store, goa: int) -> None:
    request = groups.request_to_join(store, BOB, goa)

    assert (request.group_id, request.user_id, request.status) == (
        goa,
        "bob",
        RequestStatus.PENDING,
    )


def test_request_to_join_refuses_duplicates_and_members(store: Store, goa: int) -> None:
    groups.request_to_join(store, BOB, goa)

    with pytest.raises(RequestAlreadyPendingError):
        groups.request_to_join(store, BOB, goa)
    with pytest.raises(AlreadyMemberError):
        groups.request_to_join(store, ADA, goa)


def test_request_to_join_an_unknown_group(store: Store) -> None:
    with pytest.raises(NotFoundError):
        groups.request_to_join(store, BOB, 999)


def test_request_by_name_ignores_case(store: Store, goa: int) -> None:
    assert groups.request_to_join_by_name(store, BOB, "gOA").group_id == goa

    with pytest.raises(NotFoundError):
        groups.request_to_join_by_name(store, BOB, "Nowhere")


def test_request_to_join_enforces_the_pending_limit(store: Store) -> None:
    group_ids = [
        groups.create_group(store, ADA if n < 20 else CAROL, f"Trip {n}", "").group_id
        for n in range(MAX_PENDING_REQUESTS + 1)
    ]
    for group_id in group_ids[:-1]:
        groups.request_to_join(store, BOB, group_id)

    with pytest.raises(LimitReachedError):
        groups.request_to_join(store, BOB, group_ids[-1])


def test_approve_adds_the_member(store: Store, goa: int) -> None:
    request = groups.request_to_join(store, BOB, goa)

    decided = groups.approve(store, ADA, request.request_id)

    assert decided.status == RequestStatus.APPROVED
    detail = groups.group_detail(store, BOB, goa)
    assert detail.summary.my_status == MembershipStatus.MEMBER
    assert detail.members == (ADA, BOB)
    assert detail.pending_requests is None


def test_reject_leaves_the_requester_out(store: Store, goa: int) -> None:
    request = groups.request_to_join(store, BOB, goa)

    assert groups.reject(store, ADA, request.request_id).status == RequestStatus.REJECTED
    assert groups.group_detail(store, BOB, goa).summary.my_status == MembershipStatus.NONE
    assert groups.request_to_join(store, BOB, goa).status == RequestStatus.PENDING


def test_only_the_owner_decides(store: Store, goa: int) -> None:
    request = groups.request_to_join(store, BOB, goa)

    with pytest.raises(ForbiddenError):
        groups.approve(store, CAROL, request.request_id)
    with pytest.raises(ForbiddenError):
        groups.reject(store, BOB, request.request_id)


def test_deciding_twice_or_an_unknown_request_is_not_found(store: Store, goa: int) -> None:
    request = groups.request_to_join(store, BOB, goa)
    groups.approve(store, ADA, request.request_id)

    with pytest.raises(NotFoundError):
        groups.approve(store, ADA, request.request_id)
    with pytest.raises(NotFoundError):
        groups.reject(store, ADA, 999)


def test_approve_enforces_the_member_limit(store: Store, goa: int) -> None:
    request = groups.request_to_join(store, BOB, goa)
    with store.transaction() as tx:
        for n in range(MAX_GROUP_MEMBERS - 1):
            tx.add_member(Member(user_id=f"friend{n}", display_name="Friend"))
            tx.add_membership(goa, f"friend{n}")

    with pytest.raises(LimitReachedError):
        groups.approve(store, ADA, request.request_id)
    # The refused approval left the request pending.
    assert groups.reject(store, ADA, request.request_id).status == RequestStatus.REJECTED


def test_decisions_log_ids_only(store: Store, goa: int, caplog: pytest.LogCaptureFixture) -> None:
    request = groups.request_to_join(store, BOB, goa)

    with caplog.at_level(logging.INFO, logger="backend.services.groups"):
        groups.approve(store, ADA, request.request_id)

    assert [r.getMessage() for r in caplog.records] == [
        f"approved join request request_id={request.request_id} group_id={goa} user_id=bob by=ada"
    ]


def test_group_detail_by_viewer(store: Store, goa: int) -> None:
    request = groups.request_to_join(store, BOB, goa)

    owner = groups.group_detail(store, ADA, goa)
    outsider = groups.group_detail(store, CAROL, goa)

    assert owner.members == (ADA,)
    assert owner.pending_requests is not None
    assert [p.request_id for p in owner.pending_requests] == [request.request_id]
    assert (outsider.members, outsider.pending_requests) == (None, None)
    with pytest.raises(NotFoundError):
        groups.group_detail(store, ADA, 999)
