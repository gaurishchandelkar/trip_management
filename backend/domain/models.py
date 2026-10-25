import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

MAX_GROUP_MEMBERS = 50
MAX_OWNED_GROUPS = 20
MAX_PENDING_REQUESTS = 20
BROWSE_LIMIT = 50
SESSION_LIFETIME = timedelta(days=7)


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
    user_id: str
    display_name: str


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
class PendingRequest:
    request_id: int
    display_name: str


@dataclass(frozen=True)
class GroupDetail:
    summary: GroupSummary
    # None means the viewer may not see the list, which differs from an empty list.
    members: tuple[Member, ...] | None
    pending_requests: tuple[PendingRequest, ...] | None


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
