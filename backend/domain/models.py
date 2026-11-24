import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

MAX_GROUP_MEMBERS = 50
MAX_OWNED_GROUPS = 20
MAX_PENDING_REQUESTS = 20
BROWSE_LIMIT = 50
SESSION_LIFETIME = timedelta(days=7)
DISPLAY_NAME_MAX_LENGTH = 50
# A sign-in that leaves for the provider, and a registration waiting for its user ID, each
# have 10 minutes. At most 1,000 of each are open at once, so the tables can't grow unbounded.
SIGN_IN_LIFETIME = timedelta(minutes=10)
MAX_OPEN_SIGN_INS = 1000
MAX_PENDING_REGISTRATIONS = 1000
# Signing in again with the same new account keeps its newest few, so a second tab still
# works but one account can't fill the table on its own.
MAX_PENDING_PER_ACCOUNT = 3


class MembershipStatus(StrEnum):
    OWNER = "owner"
    MEMBER = "member"
    PENDING = "pending"
    NONE = "none"


class RequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Member:
    """A member. The user ID is the key everywhere; the display name and mobile are only shown."""

    user_id: str
    display_name: str
    mobile: str


@dataclass(frozen=True)
class Identity:
    """Who the identity provider says signed in. `name` is only ever a suggestion."""

    subject: str
    name: str | None


@dataclass(frozen=True)
class SignInFlow:
    """A sign-in waiting for the provider to send the browser back. Used once."""

    flow_hash: str
    provider: str
    state_hash: str
    nonce: str
    code_verifier: str
    return_to: str
    expires_at: datetime

    def expired(self, now: datetime) -> bool:
        return now >= self.expires_at


@dataclass(frozen=True)
class PendingRegistration:
    """A verified identity with no member yet, waiting for a user ID and mobile number."""

    token_hash: str
    provider: str
    subject: str
    suggested_name: str
    return_to: str
    expires_at: datetime

    def expired(self, now: datetime) -> bool:
        return now >= self.expires_at


@dataclass(frozen=True)
class Session:
    token_hash: str
    user_id: str
    expires_at: datetime

    def expired(self, now: datetime) -> bool:
        return now >= self.expires_at


@dataclass(frozen=True)
class GroupSummary:
    group_id: int
    name: str
    description: str
    owner_id: str
    owner_display_name: str
    member_count: int
    my_status: MembershipStatus


@dataclass(frozen=True)
class Person:
    """A member as someone else sees them. `mobile` is None unless the viewer may see it."""

    user_id: str
    display_name: str
    mobile: str | None


@dataclass(frozen=True)
class PendingRequest:
    request_id: int
    requester: Person


@dataclass(frozen=True)
class GroupDetail:
    summary: GroupSummary
    # None means the viewer may not see the list, which differs from an empty list.
    members: tuple[Person, ...] | None
    pending_requests: tuple[PendingRequest, ...] | None


def can_see_mobiles(viewer_status: MembershipStatus) -> bool:
    """Only a group's owner sees the mobile numbers of its members and requesters (spec D7)."""
    return viewer_status == MembershipStatus.OWNER


@dataclass(frozen=True)
class JoinRequest:
    request_id: int
    group_id: int
    user_id: str
    status: RequestStatus


def name_key(name: str) -> str:
    """The form a group name is compared in, so uniqueness and search ignore case in any script."""
    return name.casefold()


def hash_token(token: str) -> str:
    # Only the hash is stored, so a leaked database doesn't hand out live sessions.
    return hashlib.sha256(token.encode()).hexdigest()
