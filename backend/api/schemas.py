import unicodedata
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from backend.domain.models import (
    GroupDetail,
    GroupSummary,
    JoinRequest,
    Member,
    MembershipStatus,
    RequestStatus,
)

# Letters (any script), optionally joined by single spaces, hyphens or apostrophes.
NAME_PATTERN = r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$"
NAME_MAX_LENGTH = 50
USER_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]*$"

# Upper-case is accepted and folded, so "ADA" collides with "ada" instead of failing validation.
UserId = Annotated[
    str,
    StringConstraints(min_length=3, max_length=30, pattern=USER_ID_PATTERN),
    AfterValidator(str.lower),
]


def _no_hidden_characters(value: str) -> str:
    # Format characters (zero-width joiners, direction overrides) and control characters are
    # invisible or reorder text, so they could make a name look like another one.
    if any(unicodedata.category(char) in {"Cf", "Cc"} for char in value):
        raise ValueError
    return value


DisplayName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=NAME_MAX_LENGTH, pattern=NAME_PATTERN),
    AfterValidator(_no_hidden_characters),
]
Password = Annotated[str, StringConstraints(min_length=1, max_length=128)]


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Registration(RequestBody):
    user_id: UserId
    display_name: DisplayName


class SignIn(RequestBody):
    user_id: UserId
    # Required but not checked yet (spec D1). It is never stored, logged or returned.
    password: Password


class MemberResponse(BaseModel):
    user_id: str
    display_name: str

    @classmethod
    def of(cls, member: Member) -> "MemberResponse":
        return cls(user_id=member.user_id, display_name=member.display_name)


# Letters and digits (any script), spaces and - ' & . , starting with a letter or digit.
GROUP_NAME_PATTERN = r"^[^\W_](?:[^\W_]|[-'&., ])*$"
GROUP_NAME_CHARS_PATTERN = r"^(?:[^\W_]|[-'&., ])+$"
GROUP_NAME_MAX_LENGTH = 60
DESCRIPTION_MAX_LENGTH = 200


def _single_spaced(value: str) -> str:
    # The regex engine has no lookahead, so spacing is checked here; ValueError becomes a 422.
    if value.endswith(" ") or "  " in value:
        raise ValueError
    return value


GroupName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=GROUP_NAME_MAX_LENGTH, pattern=GROUP_NAME_PATTERN),
    AfterValidator(_single_spaced),
    AfterValidator(_no_hidden_characters),
]
# Line breaks are control characters too, so a description is a single line.
Description = Annotated[
    str,
    StringConstraints(max_length=DESCRIPTION_MAX_LENGTH),
    AfterValidator(_no_hidden_characters),
]


class NewGroup(RequestBody):
    name: GroupName
    description: Description = ""


class JoinByName(RequestBody):
    group_name: GroupName


class GroupResponse(BaseModel):
    group_id: int
    name: str
    description: str
    owner_display_name: str
    member_count: int
    my_status: MembershipStatus

    @classmethod
    def of(cls, summary: GroupSummary) -> "GroupResponse":
        return cls(
            group_id=summary.group_id,
            name=summary.name,
            description=summary.description,
            owner_display_name=summary.owner_display_name,
            member_count=summary.member_count,
            my_status=summary.my_status,
        )


class MemberNameResponse(BaseModel):
    # No user_id: until passwords are checked (spec D1), a user ID is enough to sign in.
    display_name: str


class PendingRequestResponse(BaseModel):
    request_id: int
    display_name: str


class GroupDetailResponse(GroupResponse):
    # null when the viewer may not see the list.
    members: list[MemberNameResponse] | None
    pending_requests: list[PendingRequestResponse] | None

    @classmethod
    def of_detail(cls, detail: GroupDetail) -> "GroupDetailResponse":
        members = detail.members
        pending = detail.pending_requests
        return cls(
            **GroupResponse.of(detail.summary).model_dump(),
            members=None
            if members is None
            else [MemberNameResponse(display_name=m.display_name) for m in members],
            pending_requests=None
            if pending is None
            else [
                PendingRequestResponse(request_id=p.request_id, display_name=p.display_name)
                for p in pending
            ],
        )


class JoinRequestResponse(BaseModel):
    request_id: int
    group_id: int
    status: RequestStatus

    @classmethod
    def of(cls, request: JoinRequest) -> "JoinRequestResponse":
        return cls(request_id=request.request_id, group_id=request.group_id, status=request.status)
