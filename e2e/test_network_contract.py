"""Inside (whitebox) checks: the exact requests the browser sends and what the backend returns.

Each test waits for the specific response it expects, then asserts every /api/ call made by then.
"""

from playwright.sync_api import Page, expect

from e2e.app import (
    form,
    load,
    load_signed_out,
    register,
    register_and_sign_in,
    sign_in,
    sign_out,
    unique_user_id,
)
from e2e.network import ApiTraffic, Signature

ME: Signature = ("GET", "/api/me", {})
REGISTER: Signature = ("POST", "/api/members", {})
SIGN_IN: Signature = ("POST", "/api/sign-in", {})
SIGN_OUT: Signature = ("POST", "/api/sign-out", {})


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

    sign_in(page, user_id, typed)
    expect(page.get_by_role("button", name="Sign out")).to_be_visible()
    # Read the sign-in response now: a reload discards response bodies.
    signed_in = traffic.api_calls()[-1]
    load(page)
    expect(page.get_by_role("button", name="Sign out")).to_be_visible()

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [ME, REGISTER, SIGN_IN, ME], traffic.describe()
    assert signed_in.request_json() == {"user_id": user_id, "password": typed}
    assert (signed_in.status, signed_in.json()) == (
        200,
        {"user_id": user_id, "display_name": "Ada"},
    )
    assert calls[3].status == 200
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
    assert [call.signature for call in calls] == [ME, REGISTER, SIGN_IN, SIGN_OUT], (
        traffic.describe()
    )
    assert (calls[3].status, calls[3].request_body) == (204, None)
