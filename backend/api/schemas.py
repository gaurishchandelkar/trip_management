from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from backend.domain.models import Member

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
DisplayName = Annotated[
    str, StringConstraints(min_length=1, max_length=NAME_MAX_LENGTH, pattern=NAME_PATTERN)
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
