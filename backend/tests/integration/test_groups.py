import threading
import time
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response

from backend.domain.models import Member
from backend.storage.store import Store
from backend.tests.integration.conftest import SignedIn

NOT_FOUND = {"detail": "Not found"}
FORBIDDEN = {"detail": "Forbidden"}
LIMIT = {"detail": "Limit reached"}


def create(client: TestClient, name: str = "Goa 2027", description: str = "") -> Response:
    return client.post("/api/groups", json={"name": name, "description": description})


def create_id(client: TestClient, name: str = "Goa 2027") -> int:
    response = create(client, name)
    assert response.status_code == 201, response.text
    group_id: int = response.json()["group_id"]
    return group_id


def ask(client: TestClient, group_id: int) -> Response:
    return client.post(f"/api/groups/{group_id}/join-requests")


def ask_id(client: TestClient, group_id: int) -> int:
    response = ask(client, group_id)
    assert response.status_code == 201, response.text
    request_id: int = response.json()["request_id"]
    return request_id


def detail(client: TestClient, group_id: int) -> dict[str, Any]:
    response = client.get(f"/api/groups/{group_id}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def store_of(app: FastAPI) -> Store:
    store: Store = app.state.store
    return store


# Creating groups


def test_create_group_makes_the_creator_owner_and_sole_member(signed_in: SignedIn) -> None:
    ada = signed_in("ada")

    response = create(ada, description="Beach week")

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "group_id": body["group_id"],
        "name": "Goa 2027",
        "description": "Beach week",
        "owner_display_name": "Ada",
        "member_count": 1,
        "my_status": "owner",
    }


def test_description_is_optional(signed_in: SignedIn) -> None:
    response = signed_in("ada").post("/api/groups", json={"name": "Goa"})

    assert response.status_code == 201
    assert response.json()["description"] == ""


@pytest.mark.parametrize("name", ["Goa 2027", "Tom & Jerry's trip.", "Zoë, Ana - Lisboa", "2027"])
def test_group_names_allow_letters_digits_and_punctuation(signed_in: SignedIn, name: str) -> None:
    assert create(signed_in("ada"), name).status_code == 201


def test_a_taken_group_name_is_refused_ignoring_case(signed_in: SignedIn) -> None:
    create(signed_in("ada"))

    response = create(signed_in("bob"), "goa 2027")

    assert response.status_code == 409
    assert response.json() == {"detail": "Group name already taken"}


@pytest.mark.parametrize(
    "body",
    [
        {"name": ""},
        {"name": "G" * 61},
        {"name": " Goa"},
        {"name": "Goa "},
        {"name": "Goa  2027"},
        {"name": "Goa_2027"},
        {"name": "<b>"},
        {"name": "-Goa"},
        {"name": "Goa", "description": "d" * 201},
        {"name": "Goa", "description": "line\nbreak"},
        {"name": "Goa", "owner_id": "bob"},
        {},
    ],
)
def test_invalid_groups_are_refused(signed_in: SignedIn, body: dict[str, object]) -> None:
    response = signed_in("ada").post("/api/groups", json=body)

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request"}


def test_the_21st_owned_group_is_refused(signed_in: SignedIn) -> None:
    ada = signed_in("ada")
    for n in range(20):
        create_id(ada, f"Trip {n}")

    response = create(ada, "Trip 20")

    assert response.status_code == 409
    assert response.json() == LIMIT


# Browsing


def test_browse_shows_each_group_with_the_callers_status(signed_in: SignedIn) -> None:
    ada, bob, carol, dan = (signed_in(n) for n in ("ada", "bob", "carol", "dan"))
    goa = create_id(ada, "Goa")
    bob_joins = ask_id(bob, goa)
    ada.post(f"/api/join-requests/{bob_joins}/approve")
    ask_id(carol, goa)

    statuses = {
        name: client.get("/api/groups").json()
        for name, client in (("ada", ada), ("bob", bob), ("carol", carol), ("dan", dan))
    }

    expected = {"name": "Goa", "owner_display_name": "Ada", "member_count": 2}
    for listing in statuses.values():
        assert len(listing) == 1
        assert expected.items() <= listing[0].items()
    assert {name: listing[0]["my_status"] for name, listing in statuses.items()} == {
        "ada": "owner",
        "bob": "member",
        "carol": "pending",
        "dan": "none",
    }


def test_browse_search_matches_part_of_the_name_ignoring_case(signed_in: SignedIn) -> None:
    ada = signed_in("ada")
    for name in ("Goa 2027", "Ladakh", "Monsoon in GOA"):
        create_id(ada, name)

    response = ada.get("/api/groups", params={"q": "goa"})

    assert [g["name"] for g in response.json()] == ["Goa 2027", "Monsoon in GOA"]


@pytest.mark.parametrize("q", ["", "%", "a_b", "x" * 61])
def test_invalid_search_terms_are_refused(signed_in: SignedIn, q: str) -> None:
    assert signed_in("ada").get("/api/groups", params={"q": q}).status_code == 422


def test_browse_returns_at_most_50_groups_sorted_by_name(app: FastAPI, signed_in: SignedIn) -> None:
    viewer = signed_in("ada")
    with store_of(app).transaction() as tx:
        for n in range(60):
            owner = f"owner{n}"
            tx.add_member(Member(user_id=owner, display_name="Owner"))
            tx.add_group(f"Trip {n:02d}", "", owner)

    names = [g["name"] for g in viewer.get("/api/groups").json()]

    assert names == [f"Trip {n:02d}" for n in range(50)]


def test_my_groups_lists_only_groups_i_am_in(signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada, "Goa")
    create_id(ada, "Ladakh")
    ada.post(f"/api/join-requests/{ask_id(bob, goa)}/approve")

    assert [g["name"] for g in bob.get("/api/me/groups").json()] == ["Goa"]
    assert [g["name"] for g in ada.get("/api/me/groups").json()] == ["Goa", "Ladakh"]


# Asking to join


def test_asking_to_join_creates_a_pending_request(signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada)

    response = ask(bob, goa)

    assert response.status_code == 201
    assert response.json() == {
        "request_id": response.json()["request_id"],
        "group_id": goa,
        "status": "pending",
    }
    assert bob.get("/api/groups").json()[0]["my_status"] == "pending"


def test_asking_twice_is_refused(signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada)
    ask_id(bob, goa)

    response = ask(bob, goa)

    assert response.status_code == 409
    assert response.json() == {"detail": "Request already pending"}


def test_owners_and_members_cannot_ask(signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada)
    ada.post(f"/api/join-requests/{ask_id(bob, goa)}/approve")

    for client in (ada, bob):
        response = ask(client, goa)
        assert response.status_code == 409
        assert response.json() == {"detail": "Already a member"}


def test_asking_by_name_ignores_case(signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada, "Goa 2027")

    response = bob.post("/api/join-requests", json={"group_name": "goa 2027"})

    assert response.status_code == 201
    assert response.json()["group_id"] == goa


def test_asking_by_an_unknown_name_is_not_found(signed_in: SignedIn) -> None:
    response = signed_in("bob").post("/api/join-requests", json={"group_name": "Nowhere"})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_asking_by_name_rejects_invalid_names(signed_in: SignedIn) -> None:
    response = signed_in("bob").post("/api/join-requests", json={"group_name": "<script>"})

    assert response.status_code == 422


@pytest.mark.parametrize("group_id", ["999", "0", str(2**63), "abc"])
def test_asking_to_join_an_unknown_group(signed_in: SignedIn, group_id: str) -> None:
    response = signed_in("bob").post(f"/api/groups/{group_id}/join-requests")

    assert response.status_code == (404 if group_id == "999" else 422)


def test_the_21st_pending_request_is_refused(app: FastAPI, signed_in: SignedIn) -> None:
    bob = signed_in("bob")
    with store_of(app).transaction() as tx:
        tx.add_member(Member(user_id="owner", display_name="Owner"))
        group_ids = [tx.add_group(f"Trip {n}", "", "owner") for n in range(21)]
    for group_id in group_ids[:20]:
        ask_id(bob, group_id)

    response = ask(bob, group_ids[20])

    assert response.status_code == 409
    assert response.json() == LIMIT


# Group detail


def test_the_owner_sees_members_and_pending_requests(signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada)
    request_id = ask_id(bob, goa)

    body = detail(ada, goa)

    assert body["members"] == [{"user_id": "ada", "display_name": "Ada"}]
    assert body["pending_requests"] == [{"request_id": request_id, "display_name": "Bob"}]


def test_a_member_sees_members_but_not_requests(signed_in: SignedIn) -> None:
    ada, bob, carol = signed_in("ada"), signed_in("bob"), signed_in("carol")
    goa = create_id(ada)
    ada.post(f"/api/join-requests/{ask_id(bob, goa)}/approve")
    ask_id(carol, goa)

    body = detail(bob, goa)

    assert [m["user_id"] for m in body["members"]] == ["ada", "bob"]
    assert body["pending_requests"] is None


def test_a_non_member_sees_only_the_browse_details(signed_in: SignedIn) -> None:
    ada, carol = signed_in("ada"), signed_in("carol")
    goa = create_id(ada)

    body = detail(carol, goa)

    assert body["members"] is None
    assert body["pending_requests"] is None
    assert (body["name"], body["member_count"], body["my_status"]) == ("Goa 2027", 1, "none")


def test_an_unknown_group_is_not_found(signed_in: SignedIn) -> None:
    response = signed_in("ada").get("/api/groups/999")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


# Deciding


def test_approving_makes_the_requester_a_member(signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada)
    request_id = ask_id(bob, goa)

    response = ada.post(f"/api/join-requests/{request_id}/approve")

    assert response.status_code == 200
    assert response.json() == {"request_id": request_id, "group_id": goa, "status": "approved"}
    owner_view = detail(ada, goa)
    assert [m["user_id"] for m in owner_view["members"]] == ["ada", "bob"]
    assert owner_view["pending_requests"] == []
    assert detail(bob, goa)["my_status"] == "member"


def test_rejecting_leaves_the_requester_out_and_free_to_ask_again(signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada)
    request_id = ask_id(bob, goa)

    response = ada.post(f"/api/join-requests/{request_id}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert detail(bob, goa)["my_status"] == "none"
    assert ask(bob, goa).status_code == 201


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_only_the_owner_can_decide(signed_in: SignedIn, decision: str) -> None:
    ada, bob, carol = signed_in("ada"), signed_in("bob"), signed_in("carol")
    goa = create_id(ada)
    ada.post(f"/api/join-requests/{ask_id(bob, goa)}/approve")
    request_id = ask_id(carol, goa)

    for client in (bob, carol):
        response = client.post(f"/api/join-requests/{request_id}/{decision}")
        assert response.status_code == 403
        assert response.json() == FORBIDDEN
    assert detail(ada, goa)["pending_requests"] == [
        {"request_id": request_id, "display_name": "Carol"}
    ]


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_unknown_or_decided_requests_are_not_found(signed_in: SignedIn, decision: str) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    request_id = ask_id(bob, create_id(ada))
    ada.post(f"/api/join-requests/{request_id}/approve")

    for unknown in (request_id, 999):
        response = ada.post(f"/api/join-requests/{unknown}/{decision}")
        assert response.status_code == 404
        assert response.json() == NOT_FOUND


def test_concurrent_approvals_create_one_membership(app: FastAPI, signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada)
    request_id = ask_id(bob, goa)
    tabs = [TestClient(app, cookies=dict(ada.cookies)) for _ in range(2)]
    start = threading.Barrier(len(tabs))
    statuses: list[int] = []

    def approve(tab: TestClient) -> None:
        start.wait()
        statuses.append(tab.post(f"/api/join-requests/{request_id}/approve").status_code)

    threads = [threading.Thread(target=approve, args=(tab,)) for tab in tabs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [200, 404]
    assert detail(ada, goa)["member_count"] == 2


def test_approving_into_a_full_group_is_refused(app: FastAPI, signed_in: SignedIn) -> None:
    ada, bob = signed_in("ada"), signed_in("bob")
    goa = create_id(ada)
    request_id = ask_id(bob, goa)
    with store_of(app).transaction() as tx:
        for n in range(49):
            tx.add_member(Member(user_id=f"friend{n}", display_name="Friend"))
            tx.add_membership(goa, f"friend{n}")

    response = ada.post(f"/api/join-requests/{request_id}/approve")

    assert response.status_code == 409
    assert response.json() == LIMIT
    assert detail(ada, goa)["member_count"] == 50


# Sessions and performance


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/me/groups"),
        ("POST", "/api/groups"),
        ("GET", "/api/groups"),
        ("GET", "/api/groups/1"),
        ("POST", "/api/groups/1/join-requests"),
        ("POST", "/api/join-requests"),
        ("POST", "/api/join-requests/1/approve"),
        ("POST", "/api/join-requests/1/reject"),
    ],
)
def test_group_routes_need_a_session(client: TestClient, method: str, path: str) -> None:
    body = {"group_name": "Goa"} if path == "/api/join-requests" else {"name": "Goa"}

    response = client.request(method, path, json=body if method == "POST" else None)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not signed in"}


BUDGET_S = 0.2


def test_browse_search_and_detail_stay_fast_with_1000_groups(
    app: FastAPI, signed_in: SignedIn
) -> None:
    ada = signed_in("ada")
    with store_of(app).transaction() as tx:
        for n in range(1000):
            tx.add_member(Member(user_id=f"member{n}", display_name="Member"))
        for n in range(1000):
            group_id = tx.add_group(f"Trip {n:04d}", "", f"member{n}")
            tx.add_membership(group_id, f"member{(n + 1) % 1000}")
    target = ada.get("/api/groups", params={"q": "Trip 0500"}).json()[0]["group_id"]

    for path, params in (
        ("/api/groups", {}),
        ("/api/groups", {"q": "trip 09"}),
        (f"/api/groups/{target}", {}),
    ):
        started = time.perf_counter()
        response = ada.get(path, params=params)
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert elapsed < BUDGET_S, f"{path} {params} took {elapsed * 1000:.0f} ms"
