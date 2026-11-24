import logging
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


def test_update_profile_changes_name_and_mobile_only(store: Store) -> None:
    updated = members.update_profile(store, ADA, "Augusta", "+447700900123")

    assert updated == Member(user_id="ada", display_name="Augusta", mobile="+447700900123")
    with store.transaction() as tx:
        assert tx.get_member("ada") == updated


def test_update_profile_for_a_member_who_is_gone_is_refused(store: Store) -> None:
    ghost = Member(user_id="ghost", display_name="Ghost", mobile="+447700900123")

    with pytest.raises(UnauthenticatedError):
        members.update_profile(store, ghost, "Ghost", "+447700900123")


@pytest.mark.parametrize(
    ("name", "mobile", "fields"),
    [
        ("Augusta", "+447700900123", "display_name,mobile"),
        ("Ada Lovelace", "+447700900123", "mobile"),
        ("Augusta", "+919876543210", "display_name"),
        ("Ada Lovelace", "+919876543210", "none"),
    ],
)
def test_profile_update_logs_fields_not_values(
    store: Store, caplog: pytest.LogCaptureFixture, name: str, mobile: str, fields: str
) -> None:
    with caplog.at_level(logging.INFO, logger="backend.services.members"):
        members.update_profile(store, ADA, name, mobile)

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [f"profile updated user_id=ada fields={fields}"]
    for value in ("Augusta", "Lovelace", "+447700900123", "+919876543210", "9876543210"):
        assert value not in messages[0]


def test_utc_now_is_timezone_aware() -> None:
    assert members.utc_now().tzinfo is UTC
