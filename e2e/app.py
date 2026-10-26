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


def load(page: Page, path: str = "/") -> None:
    """Opens the app at a path and waits for the session check, which is always the first call."""
    with page.expect_response(api("GET", "/api/me")):
        page.goto(path)


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
    # Signing in opens the home view, which loads my groups and the browse list.
    with (
        page.expect_response(api("GET", "/api/me/groups")),
        page.expect_response(api("GET", "/api/groups")),
    ):
        sign_in(page, user_id)
    expect(page.get_by_role("button", name="Sign out")).to_be_visible()


def load_home(page: Page) -> None:
    """Opens the app with a session and waits for the session check and both home lists."""
    with (
        page.expect_response(api("GET", "/api/me/groups")),
        page.expect_response(api("GET", "/api/groups")),
    ):
        load(page)
    expect(page.get_by_role("button", name="Sign out")).to_be_visible()


def unique_group_name(prefix: str) -> str:
    return f"{prefix} {uuid.uuid4().hex[:10]}"


def create_group(page: Page, name: str, description: str = "") -> None:
    create_form = form(page, "Create group")
    create_form.get_by_label("Name").fill(name)
    create_form.get_by_label("Description").fill(description)
    with page.expect_response(api("GET", "/api/me/groups")):
        create_form.get_by_role("button", name="Create group").click()
    expect(create_form.get_by_role("status")).to_have_text(f"Created {name}.")


def search_groups(page: Page, term: str) -> None:
    search = page.get_by_role("search")
    search.get_by_label("Search by name").fill(term)
    with page.expect_response(api("GET", "/api/groups")):
        search.get_by_role("button", name="Search").click()


def section(page: Page, name: str) -> Locator:
    return page.get_by_role("region", name=name)


def open_group(page: Page, list_name: str, group_name: str) -> None:
    """Opens a group from "My groups" or "Browse groups" and waits for its detail."""
    with page.expect_response(lambda r: urlsplit(r.url).path.startswith("/api/groups/")):
        section(page, list_name).get_by_role("link", name=group_name, exact=True).click()
    expect(page.get_by_role("heading", name=group_name, level=2)).to_be_visible()


def group_path(page: Page) -> str:
    """The open group's address, such as /groups/12."""
    path = urlsplit(page.url).path
    assert path.startswith("/groups/"), page.url
    return path


def back_to_home(page: Page) -> None:
    """Uses the browser's Back button to return home, and waits for both home lists."""
    with (
        page.expect_response(api("GET", "/api/me/groups")),
        page.expect_response(api("GET", "/api/groups")),
    ):
        page.go_back()
    expect(section(page, "My groups")).to_be_visible()


def sign_out(page: Page) -> None:
    with page.expect_response(api("POST", "/api/sign-out")):
        page.get_by_role("button", name="Sign out").click()
