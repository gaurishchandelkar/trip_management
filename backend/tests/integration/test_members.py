import sqlite3
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.tests.integration.conftest import FakeClock, SignedIn

NOT_SIGNED_IN = {"detail": "Not signed in"}


def test_me_returns_the_signed_in_member(signed_in: SignedIn) -> None:
    ada = signed_in("ada")

    response = ada.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {"user_id": "ada", "display_name": "Ada", "mobile": "+919876543210"}


def test_sign_out_ends_the_session(signed_in: SignedIn) -> None:
    ada = signed_in("ada")
    token = ada.cookies["session"]

    response = ada.post("/api/sign-out")

    assert response.status_code == 204
    assert 'session=""' in response.headers["set-cookie"]
    ada.cookies.set("session", token)
    assert ada.get("/api/me").status_code == 401


@pytest.mark.parametrize(("method", "path"), [("GET", "/api/me"), ("POST", "/api/sign-out")])
def test_no_session_is_refused(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path)

    assert response.status_code == 401
    assert response.json() == NOT_SIGNED_IN


def test_an_unknown_session_token_is_refused(client: TestClient) -> None:
    client.cookies.set("session", "not-a-real-token")

    assert client.get("/api/me").status_code == 401


def test_a_session_expires_after_seven_days(signed_in: SignedIn, clock: FakeClock) -> None:
    ada = signed_in("ada")
    clock.advance(timedelta(days=7) - timedelta(seconds=1))
    assert ada.get("/api/me").status_code == 200

    clock.advance(timedelta(seconds=1))

    assert ada.get("/api/me").status_code == 401


@pytest.fixture
def database(client: TestClient, db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path)
    yield connection
    connection.close()


def test_only_a_hash_of_the_session_token_is_stored(
    signed_in: SignedIn, database: sqlite3.Connection
) -> None:
    ada = signed_in("ada")
    token = ada.cookies["session"]

    stored = [row[0] for row in database.execute("SELECT token_hash FROM sessions")]

    assert len(stored) == 1
    assert token not in stored[0]
    columns = {
        row[1]
        for table in ("members", "sessions", "identities")
        for row in database.execute(f"PRAGMA table_info({table})")
    }
    assert not any("password" in column for column in columns)


@pytest.mark.parametrize("chunked", [False, True])
def test_a_body_over_4_kb_is_refused(signed_in: SignedIn, chunked: bool) -> None:
    ada = signed_in("ada")
    body = b'{"name": "Goa", "description": "' + b"A" * 5000 + b'"}'
    # A generator body is sent chunked, with no Content-Length header.
    content = iter([body[:2000], body[2000:]]) if chunked else body

    response = ada.post(
        "/api/groups", content=content, headers={"content-type": "application/json"}
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request too large"}


def test_a_corrupted_database_returns_503(signed_in: SignedIn, db_path: Path) -> None:
    ada = signed_in("ada")
    db_path.write_bytes(b"this is not a database" * 100)

    response = ada.get("/api/me")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
