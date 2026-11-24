from typing import Annotated

from fastapi import Cookie, Depends, Request, Response

from backend.domain.errors import NotFoundError
from backend.domain.models import SESSION_LIFETIME, Member
from backend.services.identity_port import IdentityProvider
from backend.services.members import Clock, current_member, utc_now
from backend.storage.store import Store

SESSION_COOKIE = "session"


def get_store(request: Request) -> Store:
    store: Store = request.app.state.store
    return store


def get_clock() -> Clock:
    return utc_now


def get_identity_provider(request: Request) -> IdentityProvider:
    """The configured provider. Without one, every sign-in route answers 404."""
    provider: IdentityProvider | None = request.app.state.identity_provider
    if provider is None:
        raise NotFoundError
    return provider


def get_secure_cookies(request: Request) -> bool:
    """True when the app is served over https, so every cookie it sets or clears is Secure."""
    secure: bool = request.app.state.secure_cookies
    return secure


StoreDep = Annotated[Store, Depends(get_store)]
ClockDep = Annotated[Clock, Depends(get_clock)]
IdentityProviderDep = Annotated[IdentityProvider, Depends(get_identity_provider)]
SecureCookies = Annotated[bool, Depends(get_secure_cookies)]
SessionToken = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


def get_current_member(store: StoreDep, clock: ClockDep, token: SessionToken = None) -> Member:
    return current_member(store, token, clock)


CurrentMember = Annotated[Member, Depends(get_current_member)]


def set_session_cookie(response: Response, token: str, secure: bool) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/api",
        httponly=True,
        samesite="strict",
        secure=secure,
    )
