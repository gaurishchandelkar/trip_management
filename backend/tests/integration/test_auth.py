import sqlite3
import threading
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from backend.domain.errors import DomainError, IdentityRejectedError, ProviderUnavailableError
from backend.domain.models import (
    MAX_OPEN_SIGN_INS,
    MAX_PENDING_REGISTRATIONS,
    PendingRegistration,
    SignInFlow,
)
from backend.storage.schema import metadata
from backend.storage.store import Store
from backend.tests.integration.conftest import FakeClock
from backend.tests.integration.fake_provider import (
    AUTHORIZE_URL,
    CALLBACK,
    REGISTRATION,
    START,
    FakeIdentityProvider,
    come_back,
    sign_up,
    start,
)

FAILED = "/?sign_in=failed"
REGISTER = "/register/complete"
ADA = {"user_id": "ada", "display_name": "Ada Lovelace", "mobile": "+919876543210"}


def cookie_header(response: Any, name: str) -> str:
    headers: list[str] = response.headers.get_list("set-cookie")
    return next(header for header in headers if header.startswith(f"{name}="))


def registered(client: TestClient, provider: FakeIdentityProvider, subject: str = "s-ada") -> None:
    state = start(client)
    assert come_back(client, state, provider.approve(state, subject)) == REGISTER


def every_stored_value(db_path: Path) -> list[object]:
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as connection:
        return [
            value
            for table in metadata.sorted_tables
            for row in connection.execute(select(table))
            for value in row
        ]


# Starting a sign-in


def test_start_redirects_with_pkce_state_and_nonce(client: TestClient) -> None:
    response = client.get(START, follow_redirects=False)

    assert response.status_code == 302
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == AUTHORIZE_URL
    flow = cookie_header(response, "sign_in_flow").lower()
    assert "httponly" in flow
    assert "samesite=lax" in flow
    assert "path=/api/auth" in flow
    assert "max-age=600" in flow


def test_each_start_sends_a_fresh_state(client: TestClient) -> None:
    assert start(client) != start(client)


def test_provider_down_at_start_redirects_to_failed(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    provider.failure = ProviderUnavailableError

    response = client.get(START, follow_redirects=False)

    assert response.headers["location"] == FAILED
    assert "sign_in_flow" not in response.cookies


def test_open_sign_in_cap_fails_new_starts(
    client: TestClient, db_path: Path, clock: FakeClock
) -> None:
    with Store(db_path).transaction() as tx:
        for n in range(MAX_OPEN_SIGN_INS):
            later = clock.now + timedelta(minutes=5)
            tx.add_sign_in_flow(SignInFlow(f"f{n}", "google", "s", "n", "v", "/", later))

    response = client.get(START, follow_redirects=False)

    assert response.headers["location"] == FAILED


def test_expired_sign_ins_make_room_for_new_ones(
    client: TestClient, db_path: Path, clock: FakeClock
) -> None:
    with Store(db_path).transaction() as tx:
        for n in range(MAX_OPEN_SIGN_INS):
            tx.add_sign_in_flow(SignInFlow(f"f{n}", "google", "s", "n", "v", "/", clock.now))

    start(client)


# return_to


def test_return_to_keeps_an_app_path(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider
) -> None:
    sign_up(TestClient(app), provider, "ada", subject="s-ada")

    state = start(client, return_to="/groups/7")

    assert come_back(client, state, provider.approve(state, "s-ada")) == "/groups/7"


@pytest.mark.parametrize(
    "return_to",
    [
        "https://evil.example",
        "//evil.example",
        "/\\evil.example",
        "/\t/evil.example",
        "javascript:alert(1)",
        "groups/7",
        "/" + "a" * 200,
        "",
    ],
)
def test_return_to_ignores_anything_else(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider, return_to: str
) -> None:
    sign_up(TestClient(app), provider, "ada", subject="s-ada")

    state = start(client, return_to=return_to)

    assert come_back(client, state, provider.approve(state, "s-ada")) == "/"


# Callback, returning member


def test_callback_signs_in_a_linked_member(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider
) -> None:
    sign_up(TestClient(app), provider, "ada", subject="s-ada", display_name="Ada Lovelace")
    state = start(client, return_to="/groups/3")

    response = client.get(
        CALLBACK,
        params={"state": state, "code": provider.approve(state, "s-ada")},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/groups/3"
    session = cookie_header(response, "session").lower()
    assert "httponly" in session
    assert "samesite=strict" in session
    assert 'sign_in_flow=""' in cookie_header(response, "sign_in_flow")
    assert client.get("/api/me").json() == ADA


def test_callback_redirects_only_to_our_own_paths(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    state = start(client)
    location = come_back(client, state, provider.approve(state, "s-new"))

    assert location.startswith("/")
    assert not location.startswith("//")
    for leaked in ("code", "state", "id_token"):
        assert leaked not in parse_qs(urlsplit(location).query)


@pytest.mark.parametrize("failure", [IdentityRejectedError, ProviderUnavailableError])
def test_rejected_identity_redirects_to_failed(
    client: TestClient, provider: FakeIdentityProvider, failure: type[DomainError]
) -> None:
    state = start(client)
    code = provider.approve(state, "s-ada")
    provider.failure = failure

    assert come_back(client, state, code) == FAILED
    assert "session" not in client.cookies


def test_a_code_minted_for_another_sign_in_is_rejected(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider
) -> None:
    first, second = start(TestClient(app)), start(client)

    # A code for the first sign-in, brought back with the second one's state: the nonce and
    # PKCE verifier don't match, so the provider rejects it.
    assert come_back(client, second, provider.approve(first, "s-ada")) == FAILED


@pytest.mark.parametrize(
    "case", ["wrong state", "missing state", "reused state", "expired flow", "no flow cookie"]
)
def test_bad_state_never_exchanges_the_code(
    app: FastAPI,
    client: TestClient,
    provider: FakeIdentityProvider,
    clock: FakeClock,
    case: str,
) -> None:
    state = start(client)
    code = provider.approve(state, "s-ada")
    params = {"state": state, "code": code}
    caller = client
    if case == "wrong state":
        params["state"] = "not-the-state"
    elif case == "missing state":
        del params["state"]
    elif case == "reused state":
        flow_id = client.cookies["sign_in_flow"]
        come_back(client, state, code)
        client.cookies.set("sign_in_flow", flow_id, path="/api/auth")
    elif case == "expired flow":
        clock.advance(timedelta(minutes=10, seconds=1))
    else:
        caller = TestClient(app)
    exchanges = provider.exchanges

    response = caller.get(CALLBACK, params=params, follow_redirects=False)

    assert response.headers["location"] == FAILED
    assert provider.exchanges == exchanges
    assert "session" not in response.cookies


@pytest.mark.parametrize("name", ["code", "state"])
def test_oversized_callback_parameters_fail(
    client: TestClient, provider: FakeIdentityProvider, name: str
) -> None:
    state = start(client)
    params = {"state": state, "code": provider.approve(state, "s-ada"), name: "x" * 513}

    response = client.get(CALLBACK, params=params, follow_redirects=False)

    assert response.headers["location"] == FAILED
    assert provider.exchanges == 0


def test_access_denied_redirects_to_cancelled(client: TestClient) -> None:
    state = start(client)

    response = client.get(
        CALLBACK, params={"state": state, "error": "access_denied"}, follow_redirects=False
    )

    assert response.headers["location"] == "/?sign_in=cancelled"


def test_other_provider_errors_redirect_to_failed(client: TestClient) -> None:
    state = start(client)

    response = client.get(
        CALLBACK, params={"state": state, "error": "server_error"}, follow_redirects=False
    )

    assert response.headers["location"] == FAILED


def test_storage_failure_on_callback_redirects_to_failed(
    client: TestClient, provider: FakeIdentityProvider, db_path: Path
) -> None:
    state = start(client)
    code = provider.approve(state, "s-ada")
    db_path.write_bytes(b"this is not a database" * 100)

    assert come_back(client, state, code) == FAILED


def test_storage_failure_on_start_redirects_to_failed(client: TestClient, db_path: Path) -> None:
    db_path.write_bytes(b"this is not a database" * 100)

    assert client.get(START, follow_redirects=False).headers["location"] == FAILED


# Callback, new person


def test_callback_for_a_new_subject_starts_a_pending_registration(
    client: TestClient, provider: FakeIdentityProvider, db_path: Path
) -> None:
    state = start(client)

    response = client.get(
        CALLBACK,
        params={"state": state, "code": provider.approve(state, "s-new")},
        follow_redirects=False,
    )

    assert response.headers["location"] == REGISTER
    pending = cookie_header(response, "pending_registration").lower()
    assert "httponly" in pending
    assert "samesite=strict" in pending
    assert "path=/api" in pending
    assert "max-age=600" in pending
    assert "session" not in response.cookies
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM members").fetchone() == (0,)
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone() == (0,)


def test_pending_registration_cap_fails_new_registrations(
    client: TestClient, provider: FakeIdentityProvider, db_path: Path, clock: FakeClock
) -> None:
    with Store(db_path).transaction() as tx:
        later = clock.now + timedelta(minutes=5)
        for n in range(MAX_PENDING_REGISTRATIONS):
            tx.add_pending_registration(
                PendingRegistration(f"t{n}", "google", f"s{n}", "", "/", later)
            )
    state = start(client)

    assert come_back(client, state, provider.approve(state, "s-new")) == FAILED


@pytest.mark.parametrize(
    ("google_name", "suggested"),
    [
        ("Ada Lovelace", "Ada Lovelace"),
        ("Zoë O'Brien-Smith", "Zoë O'Brien-Smith"),
        ("R2D2", ""),
        ("<b>Ada</b>", ""),
        ("A" * 51, ""),
        (None, ""),
    ],
)
def test_pending_registration_suggests_only_a_valid_name(
    client: TestClient, provider: FakeIdentityProvider, google_name: str | None, suggested: str
) -> None:
    state = start(client, return_to="/groups/4")
    come_back(client, state, provider.approve(state, "s-new", name=google_name))

    response = client.get(REGISTRATION)

    assert response.status_code == 200
    assert response.json() == {"display_name": suggested, "return_to": "/groups/4"}


def test_completing_registration_creates_a_linked_member(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider
) -> None:
    registered(client, provider)

    response = client.post(REGISTRATION, json=ADA)

    assert response.status_code == 201
    assert response.json() == ADA
    assert "samesite=strict" in cookie_header(response, "session").lower()
    assert 'pending_registration=""' in cookie_header(response, "pending_registration")
    assert client.get("/api/me").json() == ADA
    # Linked: signing in again with the same account finds the member.
    other = TestClient(app)
    state = start(other)
    assert come_back(other, state, provider.approve(state, "s-ada")) == "/"
    assert other.get("/api/me").json() == ADA


def test_taken_user_id_keeps_the_pending_registration(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider
) -> None:
    sign_up(TestClient(app), provider, "ada", subject="s-first")
    registered(client, provider, subject="s-second")

    taken = client.post(REGISTRATION, json={**ADA, "user_id": "ADA"})
    retry = client.post(REGISTRATION, json={**ADA, "user_id": "ada2"})

    assert taken.status_code == 409
    assert taken.json() == {"detail": "User ID already taken"}
    assert retry.status_code == 201


INVALID_REGISTRATIONS = [
    pytest.param({**ADA, "user_id": "ab"}, id="short user ID"),
    pytest.param({**ADA, "user_id": "1ada"}, id="user ID starts with a digit"),
    pytest.param({**ADA, "user_id": "<script>"}, id="markup user ID"),
    pytest.param({**ADA, "display_name": "R2D2"}, id="digits in name"),
    pytest.param({**ADA, "display_name": ""}, id="empty name"),
    pytest.param({**ADA, "display_name": "A" * 51}, id="long name"),
    pytest.param({k: v for k, v in ADA.items() if k != "mobile"}, id="missing mobile"),
    pytest.param({**ADA, "email": "ada@example.com"}, id="unknown field"),
    pytest.param({**ADA, "mobile": 919876543210}, id="mobile as a number"),
]


@pytest.mark.parametrize("body", INVALID_REGISTRATIONS)
def test_invalid_registration_is_refused(
    client: TestClient, provider: FakeIdentityProvider, body: dict[str, Any]
) -> None:
    registered(client, provider)

    response = client.post(REGISTRATION, json=body)

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request"}
    assert client.post(REGISTRATION, json=ADA).status_code == 201


@pytest.mark.parametrize(
    "mobile",
    [
        "09876543210",
        "+0123456789",
        "+91abc456789",
        "+1234567",
        "+1234567890123456",
        "+91 98765 43210 0000",
        "+91.9876543210",
        "+91 (987) 6543210",
        "",
    ],
)
def test_invalid_mobile_is_refused(
    client: TestClient, provider: FakeIdentityProvider, mobile: str
) -> None:
    registered(client, provider)

    response = client.post(REGISTRATION, json={**ADA, "mobile": mobile})

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request"}


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("+91 98765-43210", "+919876543210"),
        ("+44 7700 900123", "+447700900123"),
        ("+12345678", "+12345678"),
        ("+123456789012345", "+123456789012345"),
    ],
)
def test_mobile_is_stored_without_spaces_or_hyphens(
    client: TestClient, provider: FakeIdentityProvider, typed: str, stored: str
) -> None:
    registered(client, provider)

    response = client.post(REGISTRATION, json={**ADA, "mobile": typed})

    assert response.status_code == 201
    assert response.json()["mobile"] == stored
    assert client.get("/api/me").json()["mobile"] == stored


def test_two_members_may_share_a_mobile(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider
) -> None:
    sign_up(client, provider, "ada", mobile="+919876543210")
    sign_up(TestClient(app), provider, "bob", mobile="+919876543210")


@pytest.mark.parametrize("case", ["no pending registration", "expired", "used", "unknown"])
def test_missing_or_used_pending_registration_is_401(
    app: FastAPI,
    client: TestClient,
    provider: FakeIdentityProvider,
    clock: FakeClock,
    case: str,
) -> None:
    caller = client
    if case == "no pending registration":
        caller = TestClient(app)
    else:
        registered(client, provider)
    if case == "expired":
        clock.advance(timedelta(minutes=10))
    elif case == "used":
        token = client.cookies["pending_registration"]
        assert client.post(REGISTRATION, json=ADA).status_code == 201
        caller = TestClient(app, cookies={"pending_registration": token})
    elif case == "unknown":
        caller = TestClient(app, cookies={"pending_registration": "unknown"})

    for response in (
        caller.get(REGISTRATION),
        caller.post(REGISTRATION, json={**ADA, "user_id": "ada2"}),
    ):
        assert response.status_code == 401
        assert response.json() == {"detail": "Not signed in"}


def test_subject_linked_meanwhile_is_409(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider, db_path: Path
) -> None:
    second_tab = TestClient(app)
    registered(client, provider, subject="s-ada")
    registered(second_tab, provider, subject="s-ada")
    assert second_tab.post(REGISTRATION, json=ADA).status_code == 201

    response = client.post(REGISTRATION, json={**ADA, "user_id": "ada2"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Account already linked"}
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT user_id FROM members").fetchall() == [("ada",)]


def test_concurrent_registrations_create_one_member(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider, db_path: Path
) -> None:
    registered(client, provider)
    tabs = [TestClient(app, cookies=dict(client.cookies)) for _ in range(2)]
    start_together = threading.Barrier(len(tabs))
    statuses: list[int] = []

    def finish(tab: TestClient, user_id: str) -> None:
        start_together.wait()
        statuses.append(tab.post(REGISTRATION, json={**ADA, "user_id": user_id}).status_code)

    threads = [threading.Thread(target=finish, args=(tab, f"ada{n}")) for n, tab in enumerate(tabs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    for tab in tabs:
        tab.close()

    assert sorted(statuses) == [201, 401]
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM members").fetchone() == (1,)


def test_same_email_different_subjects_are_two_members(
    app: FastAPI, client: TestClient, provider: FakeIdentityProvider, db_path: Path
) -> None:
    # Identities carry no email, and neither does the stored link: two provider accounts are
    # two members, whatever addresses they share.
    sign_up(client, provider, "ada", subject="s-one", display_name="Ada")
    sign_up(TestClient(app), provider, "ada2", subject="s-two", display_name="Ada")

    with sqlite3.connect(db_path) as db:
        rows = db.execute("SELECT subject, user_id FROM identities ORDER BY user_id").fetchall()
    assert rows == [("s-one", "ada"), ("s-two", "ada2")]


def test_stores_no_email_name_or_tokens(
    client: TestClient, provider: FakeIdentityProvider, db_path: Path
) -> None:
    state = start(client)
    come_back(client, state, provider.approve(state, "s-ada", name="Augusta Ada King"))
    client.post(REGISTRATION, json=ADA)

    with sqlite3.connect(db_path) as db:
        identity_columns = [row[1] for row in db.execute("PRAGMA table_info(identities)")]
        member_columns = [row[1] for row in db.execute("PRAGMA table_info(members)")]
    stored = every_stored_value(db_path)
    assert identity_columns == ["provider", "subject", "user_id"]
    assert member_columns == ["user_id", "display_name", "mobile"]
    assert "Augusta Ada King" not in stored
    assert client.cookies["session"] not in stored


def test_unconfigured_provider_routes_are_not_found(app: FastAPI, client: TestClient) -> None:
    app.state.identity_provider = None

    assert client.get("/api/auth/providers").json() == {"providers": []}
    for response in (
        client.get(START, follow_redirects=False),
        client.get(CALLBACK, params={"state": "s", "code": "c"}, follow_redirects=False),
        client.get(REGISTRATION),
        client.post(REGISTRATION, json=ADA),
    ):
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}


def test_configured_provider_is_listed(client: TestClient) -> None:
    assert client.get("/api/auth/providers").json() == {"providers": ["google"]}
