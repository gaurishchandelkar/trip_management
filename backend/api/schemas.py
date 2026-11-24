import re
import unicodedata
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
)

from backend.domain.models import (
    GroupDetail,
    GroupSummary,
    JoinRequest,
    Member,
    MembershipStatus,
    PendingRequest,
    Person,
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

# International format: "+", a country code that doesn't start with 0, 8 to 15 digits in all.
MOBILE_PATTERN = re.compile(r"\+[1-9][0-9]{7,14}")
MOBILE_INPUT_MAX_LENGTH = 20


def _normalized_mobile(value: str) -> str:
    # Spaces and hyphens are how people group digits; the number itself is stored without them.
    number = value.replace(" ", "").replace("-", "")
    if not MOBILE_PATTERN.fullmatch(number):
        raise ValueError
    return number


Mobile = Annotated[
    str,
    StringConstraints(max_length=MOBILE_INPUT_MAX_LENGTH),
    AfterValidator(_normalized_mobile),
]


def suggested_display_name(name: str) -> str:
    """The provider's name if it passes the display-name rule, otherwise empty."""
    try:
        return TypeAdapter(DisplayName).validate_python(name)
    except ValidationError:
        return ""


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompleteRegistration(RequestBody):
    user_id: UserId
    display_name: DisplayName
    mobile: Mobile


class ProfileUpdate(RequestBody):
    """Both fields every time. A user_id in the body is an unknown field, so a 422."""

    display_name: DisplayName
    mobile: Mobile


class MemberResponse(BaseModel):
    """The signed-in member, about themselves. Only they ever see their own mobile here."""

    user_id: str
    display_name: str
    mobile: str

    @classmethod
    def of(cls, member: Member) -> "MemberResponse":
        return cls(user_id=member.user_id, display_name=member.display_name, mobile=member.mobile)


class ProvidersResponse(BaseModel):
    providers: list[str]


class PendingRegistrationResponse(BaseModel):
    display_name: str
    return_to: str


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
    owner_user_id: str
    owner_display_name: str
    member_count: int
    my_status: MembershipStatus

    @classmethod
    def of(cls, summary: GroupSummary) -> "GroupResponse":
        return cls(
            group_id=summary.group_id,
            name=summary.name,
            description=summary.description,
            owner_user_id=summary.owner_id,
            owner_display_name=summary.owner_display_name,
            member_count=summary.member_count,
            my_status=summary.my_status,
        )


class PersonResponse(BaseModel):
    user_id: str
    display_name: str
    # Only the group's owner gets it; for anyone else the key isn't in the JSON at all.
    mobile: str | None = Field(default=None, exclude_if=lambda value: value is None)

    @classmethod
    def of(cls, person: Person) -> "PersonResponse":
        return cls(user_id=person.user_id, display_name=person.display_name, mobile=person.mobile)


class PendingRequestResponse(PersonResponse):
    request_id: int

    @classmethod
    def of_request(cls, request: PendingRequest) -> "PendingRequestResponse":
        requester = request.requester
        return cls(
            request_id=request.request_id,
            user_id=requester.user_id,
            display_name=requester.display_name,
            mobile=requester.mobile,
        )


class GroupDetailResponse(GroupResponse):
    # null when the viewer may not see the list.
    members: list[PersonResponse] | None
    pending_requests: list[PendingRequestResponse] | None

    @classmethod
    def of_detail(cls, detail: GroupDetail) -> "GroupDetailResponse":
        members = detail.members
        pending = detail.pending_requests
        return cls(
            **GroupResponse.of(detail.summary).model_dump(),
            members=None if members is None else [PersonResponse.of(m) for m in members],
            pending_requests=None
            if pending is None
            else [PendingRequestResponse.of_request(p) for p in pending],
        )


class JoinRequestResponse(BaseModel):
    request_id: int
    group_id: int
    status: RequestStatus

    @classmethod
    def of(cls, request: JoinRequest) -> "JoinRequestResponse":
        return cls(request_id=request.request_id, group_id=request.group_id, status=request.status)
