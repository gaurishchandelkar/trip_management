import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.tests.integration.conftest import SignedIn
from backend.tests.integration.test_auth import every_stored_value

PROFILE = "/api/me/profile"
OLD_MOBILE = "+919876543210"
INVALID = {"detail": "Invalid request"}


def save(client: TestClient, display_name: str = "Ada", mobile: str = OLD_MOBILE) -> Any:
    return client.post(PROFILE, json={"display_name": display_name, "mobile": mobile})


def owned_group_with(signed_in: SignedIn) -> tuple[TestClient, TestClient, int]:
    """Ada owns a group; Bob is a member of it and has a pending request for another."""
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = ada.post("/api/groups", json={"name": "Goa"}).json()["group_id"]
    request_id = bob.post(f"/api/groups/{goa}/join-requests").json()["request_id"]
    ada.post(f"/api/join-requests/{request_id}/approve")
    ladakh = ada.post("/api/groups", json={"name": "Ladakh"}).json()["group_id"]
    bob.post(f"/api/groups/{ladakh}/join-requests")
    return ada, bob, goa


def test_changing_the_mobile_returns_it_normalized(signed_in: SignedIn) -> None:
    ada = signed_in("ada")

    response = save(ada, mobile="+44 7700-900123")

    assert response.status_code == 200
    assert response.json() == {"user_id": "ada", "display_name": "Ada", "mobile": "+447700900123"}
    assert ada.get("/api/me").json()["mobile"] == "+447700900123"


def test_owner_sees_the_new_mobile_and_the_old_one_is_gone(
    signed_in: SignedIn, db_path: Path
) -> None:
    ada, bob, goa = owned_group_with(signed_in)
    # A number only Bob has, so its absence anywhere in the database means it's gone.
    assert save(bob, "Bob", "+44 7700 900111").status_code == 200
    assert "+447700900111" in every_stored_value(db_path)

    assert save(bob, "Bob", "+44 7700 900456").status_code == 200

    members = {m["user_id"]: m for m in ada.get(f"/api/groups/{goa}").json()["members"]}
    assert members["bob"]["mobile"] == "+447700900456"
    stored = every_stored_value(db_path)
    assert "+447700900456" in stored
    assert not any("900111" in str(value) for value in stored)


def test_changing_the_name_keeps_everything_else(signed_in: SignedIn) -> None:
    ada, bob, goa = owned_group_with(signed_in)
    session = bob.cookies["session"]
    my_groups_before = bob.get("/api/me/groups").json()

    assert save(bob, "Robert", OLD_MOBILE).status_code == 200

    members = ada.get(f"/api/groups/{goa}").json()["members"]
    assert {"user_id": "bob", "display_name": "Robert", "mobile": OLD_MOBILE} in members
    ladakh = next(g for g in ada.get("/api/me/groups").json() if g["name"] == "Ladakh")
    pending = ada.get(f"/api/groups/{ladakh['group_id']}").json()["pending_requests"]
    assert [(p["user_id"], p["display_name"]) for p in pending] == [("bob", "Robert")]
    assert bob.cookies["session"] == session
    assert bob.get("/api/me").json()["user_id"] == "bob"
    my_groups_after = bob.get("/api/me/groups").json()
    assert [g["group_id"] for g in my_groups_after] == [g["group_id"] for g in my_groups_before]


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"display_name": "R2D2", "mobile": OLD_MOBILE}, id="digits in name"),
        pytest.param({"display_name": "", "mobile": OLD_MOBILE}, id="empty name"),
        pytest.param({"display_name": "Ada", "mobile": "09876543210"}, id="no country code"),
        pytest.param({"display_name": "Ada", "mobile": "+91abc"}, id="letters in mobile"),
        pytest.param({"display_name": "Ada"}, id="missing mobile"),
        pytest.param({"mobile": OLD_MOBILE}, id="missing name"),
        pytest.param({"display_name": "Ada", "mobile": 919876543210}, id="mobile as a number"),
    ],
)
def test_invalid_profile_changes_nothing(signed_in: SignedIn, body: dict[str, Any]) -> None:
    ada = signed_in("ada")

    response = ada.post(PROFILE, json=body)

    assert response.status_code == 422
    assert response.json() == INVALID
    assert ada.get("/api/me").json() == {
        "user_id": "ada",
        "display_name": "Ada",
        "mobile": OLD_MOBILE,
    }


@pytest.mark.parametrize(
    "extra",
    [{"user_id": "eve"}, {"user_id": "ada"}, {"email": "ada@example.com"}],
)
def test_user_id_cannot_be_changed(signed_in: SignedIn, extra: dict[str, str]) -> None:
    ada = signed_in("ada")

    response = ada.post(PROFILE, json={"display_name": "Eve", "mobile": OLD_MOBILE, **extra})

    assert response.status_code == 422
    assert response.json() == INVALID
    assert ada.get("/api/me").json()["display_name"] == "Ada"


def test_a_body_over_4_kb_changes_nothing(signed_in: SignedIn) -> None:
    ada = signed_in("ada")

    response = save(ada, "A" * 5000)

    assert response.status_code == 413
    assert ada.get("/api/me").json()["display_name"] == "Ada"


def test_saving_unchanged_values_is_idempotent(signed_in: SignedIn) -> None:
    ada = signed_in("ada")

    first, second = save(ada), save(ada)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == ada.get("/api/me").json()


def test_profile_needs_a_session(client: TestClient) -> None:
    response = save(client)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not signed in"}


def test_concurrent_saves_leave_one_whole_profile(app: FastAPI, signed_in: SignedIn) -> None:
    ada = signed_in("ada")
    tabs = [TestClient(app, cookies=dict(ada.cookies)) for _ in range(2)]
    profiles = [("Augusta", "+447700900111"), ("Lovelace", "+447700900222")]
    start_together = threading.Barrier(len(tabs))
    statuses: list[int] = []

    def send(tab: TestClient, profile: tuple[str, str]) -> None:
        start_together.wait()
        statuses.append(save(tab, *profile).status_code)

    threads = [
        threading.Thread(target=send, args=pair) for pair in zip(tabs, profiles, strict=True)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    for tab in tabs:
        tab.close()

    me = ada.get("/api/me").json()
    assert statuses == [200, 200]
    assert (me["display_name"], me["mobile"]) in profiles
