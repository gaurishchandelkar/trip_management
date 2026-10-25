import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime

from backend.domain.errors import InvalidCredentialsError, UnauthenticatedError
from backend.domain.models import SESSION_LIFETIME, Member, Session, hash_token
from backend.storage.store import Store

type Clock = Callable[[], datetime]

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def register(store: Store, user_id: str, display_name: str) -> Member:
    member = Member(user_id=user_id, display_name=display_name)
    with store.transaction() as tx:
        tx.add_member(member)
    return member


def sign_in(store: Store, user_id: str, now: Clock = utc_now) -> tuple[Member, str]:
    """Starts a session for a registered member. Returns the member and the session token."""
    token = secrets.token_urlsafe(32)
    with store.transaction() as tx:
        member = tx.get_member(user_id)
        if member is None:
            raise InvalidCredentialsError
        tx.add_session(
            Session(
                token_hash=hash_token(token), user_id=user_id, expires_at=now() + SESSION_LIFETIME
            )
        )
    logger.info("signed in user_id=%s", user_id)
    return member, token


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
