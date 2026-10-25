from typing import Annotated

from fastapi import Cookie, Depends, Request

from backend.domain.models import Member
from backend.services.members import Clock, current_member, utc_now
from backend.storage.store import Store

SESSION_COOKIE = "session"


def get_store(request: Request) -> Store:
    store: Store = request.app.state.store
    return store


def get_clock() -> Clock:
    return utc_now


StoreDep = Annotated[Store, Depends(get_store)]
ClockDep = Annotated[Clock, Depends(get_clock)]
SessionToken = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


def get_current_member(store: StoreDep, clock: ClockDep, token: SessionToken = None) -> Member:
    return current_member(store, token, clock)


CurrentMember = Annotated[Member, Depends(get_current_member)]
