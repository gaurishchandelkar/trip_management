from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.api.dependencies import CurrentMember, StoreDep
from backend.api.schemas import (
    GROUP_NAME_CHARS_PATTERN,
    GROUP_NAME_MAX_LENGTH,
    GroupDetailResponse,
    GroupResponse,
    JoinByName,
    JoinRequestResponse,
    NewGroup,
)
from backend.services import groups

router = APIRouter(prefix="/api")

# Bounded so an oversized ID is a 422, not an integer overflow inside SQLite.
MAX_ID = 2**31 - 1
GroupId = Annotated[int, Path(ge=1, le=MAX_ID)]
RequestId = Annotated[int, Path(ge=1, le=MAX_ID)]
Search = Annotated[
    str | None,
    Query(min_length=1, max_length=GROUP_NAME_MAX_LENGTH, pattern=GROUP_NAME_CHARS_PATTERN),
]


@router.get("/me/groups")
def my_groups(member: CurrentMember, store: StoreDep) -> list[GroupResponse]:
    return [GroupResponse.of(g) for g in groups.my_groups(store, member)]


@router.post("/groups", status_code=201)
def create_group(body: NewGroup, member: CurrentMember, store: StoreDep) -> GroupResponse:
    return GroupResponse.of(groups.create_group(store, member, body.name, body.description))


@router.get("/groups")
def browse_groups(member: CurrentMember, store: StoreDep, q: Search = None) -> list[GroupResponse]:
    return [GroupResponse.of(g) for g in groups.browse_groups(store, member, q)]


@router.get("/groups/{group_id}")
def group_detail(group_id: GroupId, member: CurrentMember, store: StoreDep) -> GroupDetailResponse:
    return GroupDetailResponse.of_detail(groups.group_detail(store, member, group_id))


@router.post("/groups/{group_id}/join-requests", status_code=201)
def request_to_join(
    group_id: GroupId, member: CurrentMember, store: StoreDep
) -> JoinRequestResponse:
    return JoinRequestResponse.of(groups.request_to_join(store, member, group_id))


@router.post("/join-requests", status_code=201)
def request_to_join_by_name(
    body: JoinByName, member: CurrentMember, store: StoreDep
) -> JoinRequestResponse:
    return JoinRequestResponse.of(groups.request_to_join_by_name(store, member, body.group_name))


@router.post("/join-requests/{request_id}/approve")
def approve(request_id: RequestId, member: CurrentMember, store: StoreDep) -> JoinRequestResponse:
    return JoinRequestResponse.of(groups.approve(store, member, request_id))


@router.post("/join-requests/{request_id}/reject")
def reject(request_id: RequestId, member: CurrentMember, store: StoreDep) -> JoinRequestResponse:
    return JoinRequestResponse.of(groups.reject(store, member, request_id))
