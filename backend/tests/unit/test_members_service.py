from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.domain.errors import UnauthenticatedError
from backend.domain.models import Member
from backend.services import members
from backend.storage.store import Store

START = datetime(2027, 1, 1, tzinfo=UTC)
ADA = Member(user_id="ada", display_name="Ada Lovelace", mobile="+919876543210")


@pytest.fixture
def store(tmp_path: Path) -> Store:
    store = Store(tmp_path / "trip.db")
    store.create_schema()
    with store.transaction() as tx:
        tx.add_member(ADA)
    return store


def session_for(store: Store, user_id: str = "ada", now: datetime = START) -> str:
    with store.transaction() as tx:
        return members.start_session(tx, user_id, lambda: now)


def test_a_session_identifies_its_member(store: Store) -> None:
    token = session_for(store)

    assert len(token) >= 43
    assert members.current_member(store, token, lambda: START) == ADA


def test_each_session_gets_a_new_token(store: Store) -> None:
    assert session_for(store) != session_for(store)


@pytest.mark.parametrize("token", [None, "", "unknown"])
def test_current_member_refuses_missing_or_unknown_tokens(store: Store, token: str | None) -> None:
    with pytest.raises(UnauthenticatedError):
        members.current_member(store, token)


def test_an_expired_session_is_refused_and_deleted(store: Store) -> None:
    token = session_for(store)
    later = START + timedelta(days=7)

    with pytest.raises(UnauthenticatedError):
        members.current_member(store, token, lambda: later)
    # Deleted, so it stays refused even if the clock went backwards.
    with pytest.raises(UnauthenticatedError):
        members.current_member(store, token, lambda: START)


def test_sign_out_ends_the_session(store: Store) -> None:
    token = session_for(store, now=members.utc_now())

    members.sign_out(store, token)

    with pytest.raises(UnauthenticatedError):
        members.current_member(store, token)


def test_utc_now_is_timezone_aware() -> None:
    assert members.utc_now().tzinfo is UTC
