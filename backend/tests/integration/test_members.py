import sqlite3
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from backend.tests.integration.conftest import FakeClock, SignedIn

INVALID = {"detail": "Invalid request"}
NOT_SIGNED_IN = {"detail": "Not signed in"}


def register(
    client: TestClient, user_id: str = "ada", display_name: str = "Ada Lovelace"
) -> Response:
    return client.post("/api/members", json={"user_id": user_id, "display_name": display_name})


def sign_in(client: TestClient, user_id: str = "ada", entered: object = "anything") -> Response:
    # Any non-empty password is accepted until real passwords arrive (spec D1).
    return client.post("/api/sign-in", json={"user_id": user_id, "password": entered})


def test_register_creates_a_member(client: TestClient) -> None:
    response = register(client)

    assert response.status_code == 201
    assert response.json() == {"user_id": "ada", "display_name": "Ada Lovelace"}


@pytest.mark.parametrize("again", ["ada", "ADA", "Ada"])
def test_register_refuses_a_taken_user_id_ignoring_case(client: TestClient, again: str) -> None:
    register(client)

    response = register(client, user_id=again, display_name="Other")

    assert response.status_code == 409
    assert response.json() == {"detail": "User ID already taken"}


def test_register_stores_user_ids_lower_case(client: TestClient) -> None:
    response = register(client, user_id="AdaL")

    assert response.json()["user_id"] == "adal"


@pytest.mark.parametrize(
    "body",
    [
        {"user_id": "ab", "display_name": "Ada"},
        {"user_id": "a" * 31, "display_name": "Ada"},
        {"user_id": "1ada", "display_name": "Ada"},
        {"user_id": "ada!", "display_name": "Ada"},
        {"user_id": "<script>", "display_name": "Ada"},
        {"user_id": "ada", "display_name": "R2D2"},
        {"user_id": "ada", "display_name": "A" * 51},
        {"user_id": "ada", "display_name": ""},
        {"user_id": "ada", "display_name": "<b>Ada</b>"},
        {"user_id": "ada"},
        {"user_id": "ada", "display_name": "Ada", "is_admin": True},
        {"user_id": 123, "display_name": "Ada"},
    ],
)
def test_register_rejects_invalid_input_without_echoing_it(
    client: TestClient, body: dict[str, object]
) -> None:
    response = client.post("/api/members", json=body)

    assert response.status_code == 422
    assert response.json() == INVALID


def test_sign_in_starts_a_session(client: TestClient) -> None:
    register(client)

    response = sign_in(client)

    assert response.status_code == 200
    assert response.json() == {"user_id": "ada", "display_name": "Ada Lovelace"}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("session=")
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api" in cookie
    assert "Max-Age=604800" in cookie
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"user_id": "ada", "display_name": "Ada Lovelace"}


def test_sign_in_ignores_user_id_case(client: TestClient) -> None:
    register(client)

    assert sign_in(client, user_id="ADA").status_code == 200


def test_sign_in_as_an_unregistered_member_is_refused(client: TestClient) -> None:
    response = sign_in(client, user_id="bob")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid user ID or password"}
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("password", ["", "p" * 129, None, 123])
def test_sign_in_rejects_invalid_passwords(client: TestClient, password: object) -> None:
    register(client)

    response = sign_in(client, entered=password)

    assert response.status_code == 422
    assert response.json() == INVALID


def test_sign_in_requires_a_password(client: TestClient) -> None:
    register(client)

    response = client.post("/api/sign-in", json={"user_id": "ada"})

    assert response.status_code == 422


def test_sign_out_ends_the_session(client: TestClient) -> None:
    register(client)
    sign_in(client)
    token = client.cookies["session"]

    response = client.post("/api/sign-out")

    assert response.status_code == 204
    assert 'session=""' in response.headers["set-cookie"]
    client.cookies.set("session", token)
    assert client.get("/api/me").status_code == 401


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
        for table in ("members", "sessions")
        for row in database.execute(f"PRAGMA table_info({table})")
    }
    assert not any("password" in column for column in columns)


@pytest.mark.parametrize("chunked", [False, True])
def test_a_body_over_4_kb_is_refused(client: TestClient, chunked: bool) -> None:
    body = b'{"user_id": "ada", "display_name": "' + b"A" * 5000 + b'"}'
    # A generator body is sent chunked, with no Content-Length header.
    content = iter([body[:2000], body[2000:]]) if chunked else body

    response = client.post(
        "/api/members", content=content, headers={"content-type": "application/json"}
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request too large"}


def test_a_corrupted_database_returns_503(client: TestClient, db_path: Path) -> None:
    db_path.write_bytes(b"this is not a database" * 100)

    response = register(client)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
