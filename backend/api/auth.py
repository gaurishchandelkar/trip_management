"""Sign-in and registration through Google (docs/specs/sso-registration.md).

The start and callback routes are browser navigations, so they answer with redirects to the
app, never with JSON. Every redirect stays on our own origin except the one to the provider.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response
from fastapi.responses import RedirectResponse

from backend.api.dependencies import (
    ClockDep,
    IdentityProviderDep,
    StoreDep,
    set_session_cookie,
)
from backend.api.schemas import (
    CompleteRegistration,
    MemberResponse,
    PendingRegistrationResponse,
    ProvidersResponse,
    suggested_display_name,
)
from backend.domain.errors import (
    LimitReachedError,
    ProviderUnavailableError,
    StorageUnavailableError,
)
from backend.domain.models import SIGN_IN_LIFETIME
from backend.services import auth
from backend.services.auth import Failure, NeedsRegistration, SignedIn, SignInFailed
from backend.services.identity_port import IdentityProvider

router = APIRouter(prefix="/api")

FLOW_COOKIE = "sign_in_flow"
REGISTRATION_COOKIE = "pending_registration"
REGISTER_PAGE = "/register/complete"
MAX_CALLBACK_PARAMETER_LENGTH = 512
COOKIE_MAX_AGE = int(SIGN_IN_LIFETIME.total_seconds())

FlowId = Annotated[str | None, Cookie(alias=FLOW_COOKIE)]
RegistrationToken = Annotated[str | None, Cookie(alias=REGISTRATION_COOKIE)]


def _to_app(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=302)


def _failed(failure: Failure = Failure.FAILED) -> RedirectResponse:
    return _to_app(f"/?sign_in={failure}")


def _clear_flow_cookie(response: Response) -> None:
    response.delete_cookie(FLOW_COOKIE, path="/api/auth", httponly=True, samesite="lax")


def _clear_registration_cookie(response: Response) -> None:
    response.delete_cookie(REGISTRATION_COOKIE, path="/api", httponly=True, samesite="strict")


@router.get("/auth/providers")
def providers(request: Request) -> ProvidersResponse:
    provider: IdentityProvider | None = request.app.state.identity_provider
    return ProvidersResponse(providers=[] if provider is None else [provider.name])


@router.get("/auth/google/start")
def start(
    provider: IdentityProviderDep, store: StoreDep, clock: ClockDep, return_to: str | None = None
) -> RedirectResponse:
    try:
        started = auth.start_sign_in(store, provider, return_to, clock)
    except (ProviderUnavailableError, LimitReachedError, StorageUnavailableError):
        return _failed()
    response = RedirectResponse(started.redirect_url, status_code=302)
    # Lax, not Strict: the callback is a top-level navigation from the provider's site, and a
    # Strict cookie isn't sent on it. It holds only a random ID for a single-use flow.
    response.set_cookie(
        FLOW_COOKIE,
        started.flow_id,
        max_age=COOKIE_MAX_AGE,
        path="/api/auth",
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/auth/google/callback")
def callback(
    provider: IdentityProviderDep,
    store: StoreDep,
    clock: ClockDep,
    flow_id: FlowId = None,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    parameters = (code, state, error)
    if any(p is not None and len(p) > MAX_CALLBACK_PARAMETER_LENGTH for p in parameters):
        response = _failed()
    else:
        try:
            outcome = auth.finish_sign_in(store, provider, flow_id, state, code, error, clock)
        except StorageUnavailableError:
            outcome = SignInFailed(Failure.FAILED)
        if isinstance(outcome, SignedIn):
            response = _to_app(outcome.return_to)
            set_session_cookie(response, outcome.session_token)
        elif isinstance(outcome, NeedsRegistration):
            response = _to_app(REGISTER_PAGE)
            response.set_cookie(
                REGISTRATION_COOKIE,
                outcome.registration_token,
                max_age=COOKIE_MAX_AGE,
                path="/api",
                httponly=True,
                samesite="strict",
            )
        else:
            response = _failed(outcome.failure)
    _clear_flow_cookie(response)
    return response


@router.get("/auth/registration")
def pending_registration(
    _provider: IdentityProviderDep,
    store: StoreDep,
    clock: ClockDep,
    token: RegistrationToken = None,
) -> PendingRegistrationResponse:
    pending = auth.pending_registration(store, token, clock)
    return PendingRegistrationResponse(
        display_name=suggested_display_name(pending.suggested_name),
        return_to=pending.return_to,
    )


@router.post("/auth/registration", status_code=201)
def complete_registration(
    body: CompleteRegistration,
    response: Response,
    _provider: IdentityProviderDep,
    store: StoreDep,
    clock: ClockDep,
    token: RegistrationToken = None,
) -> MemberResponse:
    member, session_token = auth.complete_registration(
        store, token, body.user_id, body.display_name, body.mobile, clock
    )
    set_session_cookie(response, session_token)
    _clear_registration_cookie(response)
    return MemberResponse.of(member)
