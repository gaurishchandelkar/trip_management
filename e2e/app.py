"""User actions shared by the outside and inside tests. Each waits for the call it causes."""

import uuid
from collections.abc import Callable
from urllib.parse import urlsplit

from playwright.sync_api import Locator, Page, Response, expect


def unique_user_id(prefix: str) -> str:
    # The E2E database lives for the whole session, so every test registers its own members.
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def api(method: str, path: str) -> Callable[[Response], bool]:
    def matches(response: Response) -> bool:
        return response.request.method == method and urlsplit(response.url).path == path

    return matches


def form(page: Page, name: str) -> Locator:
    return page.get_by_role("form", name=name)


def load(page: Page) -> None:
    """Opens the app and waits for the session check, which is always the first call."""
    with page.expect_response(api("GET", "/api/me")):
        page.goto("/")


def load_signed_out(page: Page) -> None:
    load(page)
    expect(form(page, "Sign in")).to_be_visible()


def register(page: Page, user_id: str, display_name: str) -> None:
    register_form = form(page, "Register")
    register_form.get_by_label("User ID").fill(user_id)
    register_form.get_by_label("Display name").fill(display_name)
    with page.expect_response(api("POST", "/api/members")):
        register_form.get_by_role("button", name="Register").click()


def sign_in(page: Page, user_id: str, entered: str = "anything") -> None:
    # Any non-empty password is accepted until real passwords arrive (spec D1).
    sign_in_form = form(page, "Sign in")
    sign_in_form.get_by_label("User ID").fill(user_id)
    sign_in_form.get_by_label("Password").fill(entered)
    with page.expect_response(api("POST", "/api/sign-in")):
        sign_in_form.get_by_role("button", name="Sign in").click()


def register_and_sign_in(page: Page, user_id: str, display_name: str) -> None:
    load_signed_out(page)
    register(page, user_id, display_name)
    expect(form(page, "Register").get_by_role("status")).to_contain_text("Registered")
    sign_in(page, user_id)
    expect(page.get_by_role("button", name="Sign out")).to_be_visible()


def sign_out(page: Page) -> None:
    with page.expect_response(api("POST", "/api/sign-out")):
        page.get_by_role("button", name="Sign out").click()
