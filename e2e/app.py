"""User actions shared by the outside and inside tests. Each waits for the call it causes."""

import uuid
from collections.abc import Callable
from urllib.parse import urlsplit

from playwright.sync_api import Locator, Page, Response, ViewportSize, expect


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


MOBILE = "+91 98765 43210"


def sign_in_panel(page: Page) -> Locator:
    return page.get_by_role("region", name="Sign in")


def google_link(page: Page) -> Locator:
    return page.get_by_role("link", name="Continue with Google")


def load_signed_out(page: Page, path: str = "/") -> None:
    """Opens the app without a session and waits until Continue with Google shows."""
    with page.expect_response(api("GET", "/api/auth/providers")):
        load(page, path)
    expect(google_link(page)).to_be_visible()


def google_account(subject: str) -> str:
    """The fake Google's account ID for a test person. Never shown by the app."""
    return f"google-{subject}"


def to_google(page: Page) -> None:
    """Presses Continue with Google and waits for the (fake) Google sign-in page."""
    google_link(page).click()
    expect(page.get_by_role("heading", name="Fake Google sign-in")).to_be_visible()


def google_continues(page: Page, subject: str, name: str = "") -> None:
    """Signs in at the fake Google. The browser comes back to the app, which loads afresh."""
    page.get_by_label("Account ID").fill(google_account(subject))
    page.get_by_label("Name").fill(name)
    with page.expect_response(api("GET", "/api/me")):
        page.get_by_role("button", name="Continue").click()


def finish_registering(
    page: Page, user_id: str, display_name: str, mobile: str = MOBILE
) -> Locator:
    """Fills in Finish registering and sends it. Returns the form, for checking messages."""
    registration = form(page, "Finish registering")
    registration.get_by_label("User ID").fill(user_id)
    registration.get_by_label("Display name").fill(display_name)
    registration.get_by_label("Mobile number").fill(mobile)
    with page.expect_response(api("POST", "/api/auth/registration")):
        registration.get_by_role("button", name="Finish registering").click()
    return registration


def sign_up(page: Page, user_id: str, display_name: str, mobile: str = MOBILE) -> None:
    """From the signed-out screen: Google, then Finish registering. Ends on the home screen."""
    to_google(page)
    with page.expect_response(api("GET", "/api/auth/registration")):
        google_continues(page, user_id, display_name)
    expect(form(page, "Finish registering")).to_be_visible()
    # Registering signs in and opens home, which loads my groups and the browse list.
    with (
        page.expect_response(api("GET", "/api/me/groups")),
        page.expect_response(api("GET", "/api/groups")),
    ):
        finish_registering(page, user_id, display_name, mobile)
    expect(page.get_by_role("button", name="Sign out")).to_be_visible()


def sign_in_with_google(page: Page, user_id: str) -> None:
    """A registered person signs in again. The app reloads at the address they were on."""
    to_google(page)
    google_continues(page, user_id)
    expect(page.get_by_role("button", name="Sign out")).to_be_visible()


def register_and_sign_in(page: Page, user_id: str, display_name: str) -> None:
    load_signed_out(page)
    sign_up(page, user_id, display_name)


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


def open_dialog(page: Page, button: str, form_name: str) -> Locator:
    """Opens a home-screen dialog and returns its form. The header button comes first."""
    page.get_by_role("button", name=button, exact=True).first.click()
    dialog_form = form(page, form_name)
    expect(dialog_form).to_be_visible()
    return dialog_form


def create_group(page: Page, name: str, description: str = "") -> None:
    create_form = open_dialog(page, "New group", "Create group")
    create_form.get_by_label("Name").fill(name)
    create_form.get_by_label("Description").fill(description)
    with page.expect_response(api("GET", "/api/me/groups")):
        create_form.get_by_role("button", name="Create group").click()
    expect(page.get_by_role("status")).to_have_text(f"Created {name}.")


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


PHONE: ViewportSize = {"width": 360, "height": 740}


def sideways_overflow(page: Page) -> int:
    """How many pixels the page is wider than the viewport: 0 when nothing scrolls sideways."""
    return page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )


def small_targets(page: Page, minimum: int = 44) -> list[str]:
    """Visible buttons, links and fields under the minimum touch target in either direction.

    Only what's reachable: with a modal dialog open, the page behind it can't be tapped.
    """
    return page.evaluate(
        """(minimum) => {
          const modal = document.querySelector("dialog[open]");
          return [...(modal ?? document).querySelectorAll("button, a, input")]
            .filter((element) => {
              const box = element.getBoundingClientRect();
              const shown = box.width > 0 && box.height > 0;
              return shown && (box.width < minimum || box.height < minimum);
            })
            .map((element) => {
              const box = element.getBoundingClientRect();
              const name = element.textContent.trim() || element.id;
              return `${name} (${box.width}x${box.height}px)`;
            });
        }""",
        minimum,
    )
