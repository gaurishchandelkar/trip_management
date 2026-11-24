"""Signing in and registering through an identity provider (docs/specs/sso-registration.md).

A sign-in leaves for the provider with a random state, nonce and PKCE verifier, kept in a
single-use flow record. When the browser comes back, the code is exchanged and the ID token
checked. A known account starts a session; an unknown one becomes a pending registration that
waits for a user ID, display name and mobile number.
"""

import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from enum import StrEnum

from backend.domain.errors import (
    IdentityRejectedError,
    LimitReachedError,
    ProviderUnavailableError,
    UnauthenticatedError,
)
from backend.domain.models import (
    DISPLAY_NAME_MAX_LENGTH,
    MAX_OPEN_SIGN_INS,
    MAX_PENDING_PER_ACCOUNT,
    MAX_PENDING_REGISTRATIONS,
    SIGN_IN_LIFETIME,
    Member,
    PendingRegistration,
    SignInFlow,
    hash_token,
)
from backend.domain.pkce import code_challenge, new_code_verifier
from backend.services.identity_port import IdentityProvider
from backend.services.members import Clock, start_session, utc_now
from backend.storage.store import Store

logger = logging.getLogger(__name__)

HOME = "/"
MAX_RETURN_TO_LENGTH = 200
# One slash, then printable ASCII with no backslash: never "//host", "/\host" or a scheme.
# Browsers drop tabs and newlines from URLs, so "/<tab>/host" would become "//host".
APP_PATH = re.compile(r"/(?![/\\])[\x21-\x5b\x5d-\x7e]*")


class Failure(StrEnum):
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class SignInStart:
    redirect_url: str
    flow_id: str


@dataclass(frozen=True)
class SignedIn:
    member: Member
    session_token: str
    return_to: str


@dataclass(frozen=True)
class NeedsRegistration:
    registration_token: str


@dataclass(frozen=True)
class SignInFailed:
    failure: Failure


type SignInOutcome = SignedIn | NeedsRegistration | SignInFailed


def safe_return_to(value: str | None) -> str:
    """A path inside the app to land on after signing in, or home."""
    if value is None or len(value) > MAX_RETURN_TO_LENGTH or not APP_PATH.fullmatch(value):
        return HOME
    return value


def _log(provider: IdentityProvider, outcome: str, user_id: str | None = None) -> None:
    # Provider, outcome and user ID only: never a code, token, state, nonce, subject or name.
    if user_id is None:
        logger.info("sign-in provider=%s outcome=%s", provider.name, outcome)
    else:
        logger.info("sign-in provider=%s outcome=%s user_id=%s", provider.name, outcome, user_id)


def start_sign_in(
    store: Store, provider: IdentityProvider, return_to: str | None, now: Clock = utc_now
) -> SignInStart:
    """Raises ProviderUnavailableError, or LimitReachedError when too many sign-ins are open."""
    flow_id, state, nonce = (secrets.token_urlsafe(32) for _ in range(3))
    verifier = new_code_verifier()
    # Asked first, so a provider that's down leaves no flow behind.
    redirect_url = provider.authorization_url(state, nonce, code_challenge(verifier))
    with store.transaction() as tx:
        tx.delete_expired_sign_ins(now())
        if tx.count_sign_in_flows() >= MAX_OPEN_SIGN_INS:
            raise LimitReachedError
        tx.add_sign_in_flow(
            SignInFlow(
                flow_hash=hash_token(flow_id),
                provider=provider.name,
                state_hash=hash_token(state),
                nonce=nonce,
                code_verifier=verifier,
                return_to=safe_return_to(return_to),
                expires_at=now() + SIGN_IN_LIFETIME,
            )
        )
    return SignInStart(redirect_url=redirect_url, flow_id=flow_id)


def finish_sign_in(
    store: Store,
    provider: IdentityProvider,
    flow_id: str | None,
    state: str | None,
    code: str | None,
    error: str | None,
    now: Clock = utc_now,
) -> SignInOutcome:
    """Handles the provider sending the browser back. Never raises for a bad callback."""
    flow = None
    if flow_id:
        with store.transaction() as tx:
            flow = tx.take_sign_in_flow(hash_token(flow_id))
    state_matches = (
        flow is not None
        and state is not None
        and hmac.compare_digest(hash_token(state), flow.state_hash)
    )
    if flow is None or flow.expired(now()) or flow.provider != provider.name or not state_matches:
        _log(provider, "failed")
        return SignInFailed(Failure.FAILED)
    if error is not None or not code:
        cancelled = error == "access_denied"
        _log(provider, "cancelled" if cancelled else "failed")
        return SignInFailed(Failure.CANCELLED if cancelled else Failure.FAILED)
    try:
        identity = provider.verified_identity(code, flow.code_verifier, flow.nonce)
    except (ProviderUnavailableError, IdentityRejectedError):
        _log(provider, "failed")
        return SignInFailed(Failure.FAILED)

    outcome: SignInOutcome = SignInFailed(Failure.FAILED)
    with store.transaction() as tx:
        member = tx.member_for_identity(provider.name, identity.subject)
        if member is not None:
            session_token = start_session(tx, member.user_id, now)
            outcome = SignedIn(member=member, session_token=session_token, return_to=flow.return_to)
        else:
            tx.delete_expired_sign_ins(now())
            if tx.count_pending_registrations() < MAX_PENDING_REGISTRATIONS:
                token = secrets.token_urlsafe(32)
                name = identity.name or ""
                tx.add_pending_registration(
                    PendingRegistration(
                        token_hash=hash_token(token),
                        provider=provider.name,
                        subject=identity.subject,
                        suggested_name=name if len(name) <= DISPLAY_NAME_MAX_LENGTH else "",
                        return_to=flow.return_to,
                        expires_at=now() + SIGN_IN_LIFETIME,
                    ),
                    keep=MAX_PENDING_PER_ACCOUNT,
                )
                outcome = NeedsRegistration(registration_token=token)
    if isinstance(outcome, SignedIn):
        _log(provider, "signed_in", outcome.member.user_id)
    else:
        _log(provider, "needs_registration" if isinstance(outcome, NeedsRegistration) else "failed")
    return outcome


def pending_registration(
    store: Store, token: str | None, now: Clock = utc_now
) -> PendingRegistration:
    """Raises UnauthenticatedError when there's no usable pending registration."""
    pending = None
    if token:
        with store.transaction() as tx:
            pending = tx.get_pending_registration(hash_token(token))
    if pending is None or pending.expired(now()):
        raise UnauthenticatedError
    return pending


def complete_registration(
    store: Store,
    token: str | None,
    user_id: str,
    display_name: str,
    mobile: str,
    now: Clock = utc_now,
) -> tuple[Member, str]:
    """Creates the member, links the provider account and starts a session, all at once.

    Raises UnauthenticatedError without a usable pending registration, UserIdTakenError (the
    pending registration stays usable), or AccountAlreadyLinkedError.
    """
    if not token:
        raise UnauthenticatedError
    token_hash = hash_token(token)
    member = Member(user_id=user_id, display_name=display_name, mobile=mobile)
    with store.transaction() as tx:
        pending = tx.get_pending_registration(token_hash)
        if pending is None or pending.expired(now()):
            raise UnauthenticatedError
        tx.add_member(member)
        tx.add_identity(pending.provider, pending.subject, user_id)
        tx.delete_pending_registration(token_hash)
        session_token = start_session(tx, user_id, now)
    logger.info("registration provider=%s outcome=registered user_id=%s", pending.provider, user_id)
    return member, session_token
