from fastapi import APIRouter, Response

from backend.api.dependencies import (
    SESSION_COOKIE,
    ClockDep,
    CurrentMember,
    SessionToken,
    StoreDep,
)
from backend.api.schemas import MemberResponse, Registration, SignIn
from backend.domain.models import SESSION_LIFETIME
from backend.services import members

router = APIRouter(prefix="/api")


@router.post("/members", status_code=201)
def register(body: Registration, store: StoreDep) -> MemberResponse:
    return MemberResponse.of(members.register(store, body.user_id, body.display_name))


@router.post("/sign-in")
def sign_in(body: SignIn, response: Response, store: StoreDep, clock: ClockDep) -> MemberResponse:
    member, token = members.sign_in(store, body.user_id, clock)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/api",
        httponly=True,
        samesite="strict",
    )
    return MemberResponse.of(member)


@router.post("/sign-out", status_code=204)
def sign_out(
    _member: CurrentMember, response: Response, store: StoreDep, token: SessionToken = None
) -> None:
    if token:
        members.sign_out(store, token)
    response.delete_cookie(SESSION_COOKIE, path="/api", httponly=True, samesite="strict")


@router.get("/me")
def me(member: CurrentMember) -> MemberResponse:
    return MemberResponse.of(member)
