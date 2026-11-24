import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime

from backend.domain.errors import UnauthenticatedError
from backend.domain.models import SESSION_LIFETIME, Member, Session, hash_token
from backend.storage.store import Store, Transaction

type Clock = Callable[[], datetime]

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def start_session(tx: Transaction, user_id: str, now: Clock) -> str:
    """Stores a new session for the member and returns its token. Only the hash is stored."""
    token = secrets.token_urlsafe(32)
    tx.add_session(
        Session(token_hash=hash_token(token), user_id=user_id, expires_at=now() + SESSION_LIFETIME)
    )
    return token


def update_profile(store: Store, member: Member, display_name: str, mobile: str) -> Member:
    """Saves the member's display name and mobile together. The user ID stays as it is."""
    updated = Member(user_id=member.user_id, display_name=display_name, mobile=mobile)
    with store.transaction() as tx:
        before = tx.get_member(member.user_id)
        if before is None:
            raise UnauthenticatedError
        tx.update_member(updated)
    changed = [
        field
        for field, old, new in (
            ("display_name", before.display_name, display_name),
            ("mobile", before.mobile, mobile),
        )
        if old != new
    ]
    # Which fields changed, never their values: names and numbers stay out of the logs.
    logger.info("profile updated user_id=%s fields=%s", member.user_id, ",".join(changed) or "none")
    return updated


def sign_out(store: Store, token: str) -> None:
    with store.transaction() as tx:
        tx.delete_session(hash_token(token))


def current_member(store: Store, token: str | None, now: Clock = utc_now) -> Member:
    if not token:
        raise UnauthenticatedError
    token_hash = hash_token(token)
    member = None
    with store.transaction() as tx:
        session = tx.get_session(token_hash)
        if session is not None and session.expired(now()):
            tx.delete_session(token_hash)
        elif session is not None:
            member = tx.get_member(session.user_id)
    # Raised after the transaction, so deleting an expired session isn't rolled back.
    if member is None:
        raise UnauthenticatedError
    return member
