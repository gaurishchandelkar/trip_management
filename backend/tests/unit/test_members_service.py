import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.domain.errors import InvalidCredentialsError, UnauthenticatedError, UserIdTakenError
from backend.domain.models import Member
from backend.services import members
from backend.storage.store import Store

START = datetime(2027, 1, 1, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    store = Store(tmp_path / "trip.db")
    store.create_schema()
    members.register(store, "ada", "Ada Lovelace")
    return store


def test_register_returns_the_member(tmp_path: Path) -> None:
    store = Store(tmp_path / "trip.db")
    store.create_schema()

    assert members.register(store, "bob", "Bob") == Member(user_id="bob", display_name="Bob")


def test_register_refuses_a_taken_user_id(store: Store) -> None:
    with pytest.raises(UserIdTakenError):
        members.register(store, "ada", "Another")


def test_sign_in_returns_a_token_for_the_member(store: Store) -> None:
    member, token = members.sign_in(store, "ada", lambda: START)

    assert member == Member(user_id="ada", display_name="Ada Lovelace")
    assert len(token) >= 43
    assert members.current_member(store, token, lambda: START) == member


def test_each_sign_in_gets_a_new_token(store: Store) -> None:
    _, first = members.sign_in(store, "ada")
    _, second = members.sign_in(store, "ada")

    assert first != second


def test_sign_in_refuses_an_unregistered_member(store: Store) -> None:
    with pytest.raises(InvalidCredentialsError):
        members.sign_in(store, "bob")


def test_sign_in_logs_the_user_id_only(store: Store, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="backend.services.members"):
        _, token = members.sign_in(store, "ada")

    messages = [record.getMessage() for record in caplog.records]
    assert messages == ["signed in user_id=ada"]
    assert not any("Ada Lovelace" in m or token in m for m in messages)


@pytest.mark.parametrize("token", [None, "", "unknown"])
def test_current_member_refuses_missing_or_unknown_tokens(store: Store, token: str | None) -> None:
    with pytest.raises(UnauthenticatedError):
        members.current_member(store, token)


def test_an_expired_session_is_refused_and_deleted(store: Store) -> None:
    _, token = members.sign_in(store, "ada", lambda: START)
    later = START + timedelta(days=7)

    with pytest.raises(UnauthenticatedError):
        members.current_member(store, token, lambda: later)
    # Deleted, so it stays refused even if the clock went backwards.
    with pytest.raises(UnauthenticatedError):
        members.current_member(store, token, lambda: START)


def test_sign_out_ends_the_session(store: Store) -> None:
    _, token = members.sign_in(store, "ada")

    members.sign_out(store, token)

    with pytest.raises(UnauthenticatedError):
        members.current_member(store, token)


def test_utc_now_is_timezone_aware() -> None:
    assert members.utc_now().tzinfo is UTC
