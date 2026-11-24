from fastapi import APIRouter, Response

from backend.api.dependencies import SESSION_COOKIE, CurrentMember, SessionToken, StoreDep
from backend.api.schemas import MemberResponse, ProfileUpdate
from backend.services import members

router = APIRouter(prefix="/api")


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


@router.post("/me/profile")
def update_profile(body: ProfileUpdate, member: CurrentMember, store: StoreDep) -> MemberResponse:
    return MemberResponse.of(members.update_profile(store, member, body.display_name, body.mobile))
