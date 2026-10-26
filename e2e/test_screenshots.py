"""Screenshots of each main screen, for reviewers (docs/specs/ci-screenshot-artifacts.md).

Not journeys: each capture asserts only that its screen loaded and which calls it made, then
saves an image. They run against their own servers and database (`screenshot_base_url`), so
every run pictures the same sample data. CI uploads the folder as the `ui-screenshots` artifact.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import pytest
from playwright.sync_api import (
    APIResponse,
    Browser,
    Page,
    Playwright,
    StorageState,
    expect,
)
from playwright.sync_api import Error as PlaywrightError

from e2e.app import api, form, section
from e2e.network import ApiTraffic, Signature

SCREENS = ("sign-in", "home", "new-group-dialog", "group", "not-found")
THEMES = ("light", "dark")
WIDTHS = (360, 1280)
OUT = Path(__file__).resolve().parent.parent / "test-results" / "screenshots"

ME: Signature = ("GET", "/api/me", {})
MY_GROUPS: Signature = ("GET", "/api/me/groups", {})
BROWSE: Signature = ("GET", "/api/groups", {})

# --color-bg in frontend/src/theme/tokens.css, as the browser reports it.
BACKGROUND = {"light": "rgb(248, 250, 252)", "dark": "rgb(15, 23, 42)"}


@dataclass(frozen=True)
class Showcase:
    """The sample data every screenshot shows."""

    base_url: str
    ada: StorageState
    goa_id: int


def _ok(response: APIResponse) -> APIResponse:
    assert response.ok, f"{response.url} -> {response.status} {response.text()}"
    return response


@pytest.fixture(scope="session")
def showcase(playwright: Playwright, screenshot_base_url: str) -> Iterator[Showcase]:
    """Ada owns Goa Getaway and Bob owns Ladakh Road Trip. Bob has asked to join Goa Getaway."""
    ada = playwright.request.new_context(base_url=screenshot_base_url)
    bob = playwright.request.new_context(base_url=screenshot_base_url)
    try:
        for member, user_id, name in ((ada, "ada", "Ada Lovelace"), (bob, "bob", "Bob Marley")):
            _ok(member.post("/api/members", data={"user_id": user_id, "display_name": name}))
            # Any non-empty password is accepted until real passwords arrive (spec D1).
            _ok(member.post("/api/sign-in", data={"user_id": user_id, "password": user_id}))
        ladakh = {
            "name": "Ladakh Road Trip",
            "description": "Bikes, high passes and too much chai.",
        }
        _ok(bob.post("/api/groups", data=ladakh))
        goa = {"name": "Goa Getaway", "description": "Beach week in December."}
        goa_id = cast(int, _ok(ada.post("/api/groups", data=goa)).json()["group_id"])
        _ok(bob.post(f"/api/groups/{goa_id}/join-requests"))
        yield Showcase(screenshot_base_url, ada.storage_state(), goa_id)
    finally:
        ada.dispose()
        bob.dispose()


def _loaded(page: Page, heading: str) -> None:
    """Waits until the screen is final: its heading shows, nothing is loading, fonts are in."""
    expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
    expect(page.get_by_text("Loading…")).to_have_count(0)
    page.evaluate("document.fonts.ready.then(() => true)")


def _sign_in(page: Page, _show: Showcase) -> list[Signature]:
    with page.expect_response(api("GET", "/api/me")):
        page.goto("/")
    _loaded(page, "Sign in")
    return [ME]


def _home(page: Page, _show: Showcase) -> list[Signature]:
    with (
        page.expect_response(api("GET", "/api/me/groups")),
        page.expect_response(api("GET", "/api/groups")),
    ):
        page.goto("/")
    _loaded(page, "Groups")
    expect(section(page, "My groups").get_by_role("link", name="Goa Getaway")).to_be_visible()
    expect(
        section(page, "Browse groups").get_by_role("link", name="Ladakh Road Trip")
    ).to_be_visible()
    return [ME, MY_GROUPS, BROWSE]


def _new_group_dialog(page: Page, show: Showcase) -> list[Signature]:
    _home(page, show)
    # A modal's backdrop covers the viewport, not the page. Make the viewport the page's full
    # height, so the full-page image is dimmed all the way down, as a member sees it.
    viewport = page.viewport_size
    assert viewport is not None
    height = cast(int, page.evaluate("document.documentElement.scrollHeight"))
    page.set_viewport_size({"width": viewport["width"], "height": max(viewport["height"], height)})
    page.get_by_role("button", name="New group", exact=True).click()
    _loaded(page, "Create group")
    expect(form(page, "Create group").get_by_label("Name")).to_be_focused()
    return [ME, MY_GROUPS, BROWSE]


def _group(page: Page, show: Showcase) -> list[Signature]:
    path = f"/api/groups/{show.goa_id}"
    with page.expect_response(api("GET", path)):
        page.goto(f"/groups/{show.goa_id}")
    _loaded(page, "Goa Getaway")
    expect(section(page, "Members")).to_contain_text("Ada Lovelace")
    expect(section(page, "Pending requests")).to_contain_text("Bob Marley")
    return [ME, ("GET", path, {})]


def _not_found(page: Page, _show: Showcase) -> list[Signature]:
    with page.expect_response(api("GET", "/api/me")):
        page.goto("/nowhere")
    _loaded(page, "Page not found")
    return [ME]


@dataclass(frozen=True)
class Capture:
    signed_in: bool
    # Loads the screen in a fresh state and returns the /api/ calls that loading it makes.
    load: Callable[[Page, Showcase], list[Signature]]


CAPTURES = {
    "sign-in": Capture(signed_in=False, load=_sign_in),
    "home": Capture(signed_in=True, load=_home),
    "new-group-dialog": Capture(signed_in=True, load=_new_group_dialog),
    "group": Capture(signed_in=True, load=_group),
    "not-found": Capture(signed_in=True, load=_not_found),
}


def test_every_screen_is_captured() -> None:
    # Written out, not derived from SCREENS: dropping a screen from both still fails here.
    expected = {"sign-in", "home", "new-group-dialog", "group", "not-found"}

    assert set(SCREENS) == expected
    assert set(CAPTURES) == expected


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("theme", THEMES)
def test_captures_every_screen(
    browser: Browser, showcase: Showcase, theme: Literal["light", "dark"], width: int
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    contexts = {
        signed_in: browser.new_context(
            base_url=showcase.base_url,
            viewport={"width": width, "height": 800},
            color_scheme=theme,
            reduced_motion="reduce",
            storage_state=showcase.ada if signed_in else None,
        )
        for signed_in in (False, True)
    }
    try:
        for screen in SCREENS:
            capture = CAPTURES[screen]
            page = contexts[capture.signed_in].new_page()
            traffic = ApiTraffic(page)
            try:
                expected = capture.load(page, showcase)
            # A failed expectation, or a response that never came: either way, no image.
            except (AssertionError, PlaywrightError) as error:
                pytest.fail(f"{screen} ({theme}, {width} px) didn't load: {error}")

            calls = [call.signature for call in traffic.api_calls()]
            assert calls == expected, f"{screen}: {traffic.describe()}"
            assert traffic.foreign_origins(showcase.base_url) == [], traffic.describe()
            expect(page.locator("body")).to_have_css("background-color", BACKGROUND[theme])

            path = OUT / f"{screen}-{theme}-{width}.png"
            page.screenshot(path=path, full_page=True, animations="disabled", caret="hide")
            assert path.stat().st_size > 0, path
            page.close()
    finally:
        for context in contexts.values():
            context.close()
