"""Inside (whitebox) checks: the exact requests the browser sends and what the backend returns.

Each test waits for the specific response it expects, then asserts every /api/ call made by then.
"""

from collections.abc import Iterator
from typing import cast

import pytest
from playwright.sync_api import Browser, Page, expect

from e2e.app import (
    api,
    create_group,
    form,
    load,
    load_home,
    load_signed_out,
    open_group,
    register,
    register_and_sign_in,
    search_groups,
    section,
    sign_in,
    sign_out,
    unique_group_name,
    unique_user_id,
)
from e2e.network import ApiTraffic, Call, Signature

ME: Signature = ("GET", "/api/me", {})
REGISTER: Signature = ("POST", "/api/members", {})
SIGN_IN: Signature = ("POST", "/api/sign-in", {})
SIGN_OUT: Signature = ("POST", "/api/sign-out", {})
MY_GROUPS: Signature = ("GET", "/api/me/groups", {})
BROWSE: Signature = ("GET", "/api/groups", {})
CREATE: Signature = ("POST", "/api/groups", {})
HOME = [MY_GROUPS, BROWSE]


@pytest.fixture
def other_page(browser: Browser, base_url: str) -> Iterator[Page]:
    """A second member's browser. Its traffic isn't recorded: it only sets the scene."""
    context = browser.new_context(base_url=base_url)
    yield context.new_page()
    context.close()


def test_load_checks_the_session_once(page: Page, traffic: ApiTraffic) -> None:
    load_signed_out(page)

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [ME], traffic.describe()
    assert (calls[0].status, calls[0].json()) == (401, {"detail": "Not signed in"})


def test_backend_failure_checks_the_session_once(page: Page, traffic: ApiTraffic) -> None:
    page.route("**/api/me", lambda route: route.fulfill(status=500))

    load(page)
    expect(page.get_by_role("alert")).to_be_visible()

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [ME], traffic.describe()
    assert calls[0].status == 500


def test_register_sends_one_request(page: Page, traffic: ApiTraffic) -> None:
    user_id = unique_user_id("ada")
    load_signed_out(page)

    register(page, f"  {user_id.upper()} ", " Ada Lovelace ")
    expect(form(page, "Register").get_by_role("status")).to_be_visible()

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [ME, REGISTER], traffic.describe()
    assert calls[1].request_json() == {"user_id": user_id.upper(), "display_name": "Ada Lovelace"}
    assert (calls[1].status, calls[1].json()) == (
        201,
        {"user_id": user_id, "display_name": "Ada Lovelace"},
    )


def test_sign_in_sends_one_request_and_never_resends_the_password(
    page: Page, traffic: ApiTraffic
) -> None:
    user_id = unique_user_id("ada")
    typed = "never-sent-again"
    load_signed_out(page)
    register(page, user_id, "Ada")

    with (
        page.expect_response(api("GET", "/api/me/groups")),
        page.expect_response(api("GET", "/api/groups")),
    ):
        sign_in(page, user_id, typed)
    # Read the sign-in response now: a reload discards response bodies.
    signed_in = traffic.api_calls()[2]
    load_home(page)

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [ME, REGISTER, SIGN_IN, *HOME, ME, *HOME], (
        traffic.describe()
    )
    assert signed_in.request_json() == {"user_id": user_id, "password": typed}
    assert (signed_in.status, signed_in.json()) == (
        200,
        {"user_id": user_id, "display_name": "Ada"},
    )
    assert calls[5].status == 200
    for call in (*calls[:2], *calls[3:]):
        assert typed not in f"{call.url} {call.request_body} {call.body}"


def test_unregistered_sign_in_gets_generic_401(page: Page, traffic: ApiTraffic) -> None:
    load_signed_out(page)

    sign_in(page, unique_user_id("ghost"))
    expect(form(page, "Sign in").get_by_role("alert")).to_be_visible()

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [ME, SIGN_IN], traffic.describe()
    assert (calls[1].status, calls[1].json()) == (401, {"detail": "Invalid user ID or password"})


def test_sign_out_sends_one_request(page: Page, traffic: ApiTraffic) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada")

    sign_out(page)
    expect(form(page, "Sign in")).to_be_visible()

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [ME, REGISTER, SIGN_IN, *HOME, SIGN_OUT], (
        traffic.describe()
    )
    assert (calls[-1].status, calls[-1].request_body) == (204, None)


def test_sign_in_loads_my_groups_and_the_browse_list_once(page: Page, traffic: ApiTraffic) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada")

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [ME, REGISTER, SIGN_IN, *HOME], traffic.describe()
    assert (calls[3].status, calls[3].json()) == (200, [])
    assert calls[4].status == 200


def test_create_group_posts_once_then_reloads_my_groups(page: Page, traffic: ApiTraffic) -> None:
    name = unique_group_name("Goa")
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    before = len(traffic.api_calls())

    create_group(page, name, "Beach week")

    calls = traffic.api_calls()[before:]
    assert [call.signature for call in calls] == [CREATE, MY_GROUPS], traffic.describe()
    assert calls[0].request_json() == {"name": name, "description": "Beach week"}
    assert calls[0].status == 201
    created = _json_object(calls[0])
    assert {"name": name, "member_count": 1, "my_status": "owner"}.items() <= created.items()
    assert calls[1].json() == [created]


def test_browse_search_sends_one_query(page: Page, traffic: ApiTraffic) -> None:
    name = unique_group_name("Goa")
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    create_group(page, name)
    before = len(traffic.api_calls())

    search_groups(page, name.lower())
    expect(section(page, "Browse groups").get_by_role("button", name=name)).to_be_visible()

    calls = traffic.api_calls()[before:]
    assert [call.signature for call in calls] == [("GET", "/api/groups", {"q": [name.lower()]})], (
        traffic.describe()
    )
    assert _json_object(calls[0], 0)["name"] == name
    assert calls[0].json() == [_json_object(calls[0], 0)]


def _json_object(call: Call, index: int | None = None) -> dict[str, object]:
    """The response body as a JSON object, or one element of a JSON array body."""
    body = call.json()
    if index is not None:
        assert isinstance(body, list)
        body = cast(list[object], body)[index]
    assert isinstance(body, dict)
    return cast(dict[str, object], body)


def _owned_group(owner: Page) -> str:
    name = unique_group_name("Goa")
    register_and_sign_in(owner, unique_user_id("ada"), "Ada")
    create_group(owner, name)
    return name


def test_request_from_browse_posts_once(page: Page, other_page: Page, traffic: ApiTraffic) -> None:
    name = _owned_group(other_page)
    register_and_sign_in(page, unique_user_id("bob"), "Bob")
    search_groups(page, name)
    group_id = _json_object(traffic.api_calls()[-1], 0)["group_id"]
    before = len(traffic.api_calls())

    with page.expect_response(api("POST", f"/api/groups/{group_id}/join-requests")):
        section(page, "Browse groups").get_by_role("button", name=f"Request to join {name}").click()
    expect(section(page, "Browse groups").get_by_text("Request pending")).to_be_visible()

    calls = traffic.api_calls()[before:]
    path = f"/api/groups/{group_id}/join-requests"
    assert [call.signature for call in calls] == [("POST", path, {})], traffic.describe()
    assert calls[0].request_body is None
    assert calls[0].status == 201


def test_request_by_name_posts_the_name_once(
    page: Page, other_page: Page, traffic: ApiTraffic
) -> None:
    name = _owned_group(other_page)
    register_and_sign_in(page, unique_user_id("carol"), "Carol")
    before = len(traffic.api_calls())
    by_name = form(page, "Request to join")
    by_name.get_by_label("Group name").fill(f" {name.lower()} ")

    with page.expect_response(api("POST", "/api/join-requests")):
        by_name.get_by_role("button", name="Send request").click()
    expect(by_name.get_by_role("status")).to_be_visible()

    calls = traffic.api_calls()[before:]
    assert [call.signature for call in calls] == [("POST", "/api/join-requests", {})], (
        traffic.describe()
    )
    assert calls[0].request_json() == {"group_name": name.lower()}
    assert calls[0].status == 201
    assert _json_object(calls[0])["status"] == "pending"


def test_approve_posts_once_then_reloads_the_group(
    page: Page, other_page: Page, traffic: ApiTraffic
) -> None:
    name = _owned_group(page)
    register_and_sign_in(other_page, unique_user_id("bob"), "Bob")
    search_groups(other_page, name)
    with other_page.expect_response(lambda r: r.url.endswith("/join-requests")):
        section(other_page, "Browse groups").get_by_role(
            "button", name=f"Request to join {name}"
        ).click()
    open_group(page, "My groups", name)
    opened = traffic.api_calls()[-1]
    group_id = _json_object(opened)["group_id"]
    pending = _json_object(opened)["pending_requests"]
    assert isinstance(pending, list)
    request_id = cast(list[dict[str, object]], pending)[0]["request_id"]
    before = len(traffic.api_calls())

    with page.expect_response(api("GET", f"/api/groups/{group_id}")):
        section(page, "Pending requests").get_by_role("button", name="Approve Bob").click()
    expect(section(page, "Members")).to_contain_text("Bob")

    calls = traffic.api_calls()[before:]
    approve_path = f"/api/join-requests/{request_id}/approve"
    assert [call.signature for call in calls] == [
        ("POST", approve_path, {}),
        ("GET", f"/api/groups/{group_id}", {}),
    ], traffic.describe()
    assert (calls[0].status, calls[0].request_body) == (200, None)
    assert _json_object(calls[0]) == {
        "request_id": request_id,
        "group_id": group_id,
        "status": "approved",
    }
    reloaded = _json_object(calls[1])
    assert reloaded["member_count"] == 2
    assert reloaded["pending_requests"] == []
