"""Outside (black-box) journeys: only what the user sees."""

import re
import uuid
from collections.abc import Iterator
from typing import Literal
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Browser, Dialog, Page, Route, expect

from e2e.app import (
    PHONE,
    api,
    back_to_home,
    create_group,
    form,
    group_path,
    load,
    load_home,
    load_signed_out,
    open_dialog,
    open_group,
    register,
    register_and_sign_in,
    search_groups,
    section,
    sideways_overflow,
    sign_in,
    sign_out,
    small_targets,
    unique_group_name,
    unique_user_id,
)


@pytest.fixture
def other_page(browser: Browser, base_url: str) -> Iterator[Page]:
    """A second member's browser, with its own cookies."""
    context = browser.new_context(base_url=base_url)
    yield context.new_page()
    context.close()


def test_shows_sign_in_and_register_forms(page: Page) -> None:
    load_signed_out(page)

    sign_in_form = form(page, "Sign in")
    expect(sign_in_form.get_by_label("User ID")).to_be_visible()
    expect(sign_in_form.get_by_label("Password")).to_have_attribute("type", "password")
    expect(sign_in_form.get_by_text("Passwords aren't checked yet.")).to_be_visible()
    expect(form(page, "Register").get_by_label("Display name")).to_be_visible()


def test_shows_alert_when_backend_fails(page: Page) -> None:
    page.route("**/api/me", lambda route: route.fulfill(status=500))

    load(page)

    expect(page.get_by_role("alert")).to_contain_text("Something went wrong, please try again.")


def test_register_sign_in_and_see_display_name(page: Page) -> None:
    user_id = unique_user_id("ada")

    register_and_sign_in(page, user_id, "Ada Lovelace")

    expect(page.get_by_text("Signed in as Ada Lovelace")).to_be_visible()


def test_session_survives_a_reload(page: Page) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada Lovelace")

    load(page)

    expect(page.get_by_text("Signed in as Ada Lovelace")).to_be_visible()


def test_sign_out_returns_to_sign_in(page: Page) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada Lovelace")

    sign_out(page)

    expect(form(page, "Sign in")).to_be_visible()
    load(page)
    expect(form(page, "Sign in")).to_be_visible()


def test_unregistered_user_id_cannot_sign_in(page: Page) -> None:
    load_signed_out(page)

    sign_in(page, unique_user_id("ghost"))

    expect(form(page, "Sign in").get_by_role("alert")).to_contain_text(
        "No member has that user ID. Register first."
    )


def test_taken_user_id_cannot_register_again(page: Page) -> None:
    user_id = unique_user_id("ada")
    load_signed_out(page)
    register(page, user_id, "Ada")

    register(page, user_id.upper(), "Other")

    expect(form(page, "Register").get_by_role("alert")).to_have_text(
        "That user ID is already taken."
    )


def test_markup_in_a_display_name_is_never_rendered(page: Page) -> None:
    dialogs: list[str] = []

    def dismiss(dialog: Dialog) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", dismiss)
    load_signed_out(page)
    register_form = form(page, "Register")
    register_form.get_by_label("User ID").fill(unique_user_id("eve"))
    register_form.get_by_label("Display name").fill("<img src=x onerror=alert(1)>")
    register_form.get_by_role("button", name="Register").click()

    expect(register_form.get_by_role("alert")).to_contain_text("Display names are letters")
    expect(page.locator("main img")).to_have_count(0)
    assert dialogs == []


def test_owner_approves_a_member_who_found_the_group_by_browsing(
    page: Page, other_page: Page
) -> None:
    ada, bob = page, other_page
    name = unique_group_name("Goa")
    register_and_sign_in(ada, unique_user_id("ada"), "Ada")
    create_group(ada, name, "Beach week")
    expect(section(ada, "My groups").get_by_role("link", name=name)).to_be_visible()

    register_and_sign_in(bob, unique_user_id("bob"), "Bob")
    search_groups(bob, name)
    browse = section(bob, "Browse groups")
    expect(browse.get_by_text("by Ada, 1 member")).to_be_visible()
    with bob.expect_response(lambda r: r.url.endswith("/join-requests")):
        browse.get_by_role("button", name=f"Request to join {name}").click()
    expect(browse.get_by_text("Request pending")).to_be_visible()

    open_group(ada, "My groups", name)
    pending = section(ada, "Pending requests")
    expect(pending).to_contain_text("Bob")
    with ada.expect_response(lambda r: r.url.endswith("/approve")):
        pending.get_by_role("button", name="Approve Bob").click()
    expect(section(ada, "Members")).to_contain_text("Bob")
    expect(pending).to_contain_text("No pending requests.")

    load_home(bob)
    open_group(bob, "My groups", name)
    expect(section(bob, "Members")).to_contain_text("Ada")
    expect(section(bob, "Members")).to_contain_text("Bob")
    expect(section(bob, "Pending requests")).to_have_count(0)


def test_owner_rejects_a_request_made_by_name(page: Page, other_page: Page) -> None:
    ada, carol = page, other_page
    name = unique_group_name("Ladakh")
    register_and_sign_in(ada, unique_user_id("ada"), "Ada")
    create_group(ada, name)

    register_and_sign_in(carol, unique_user_id("carol"), "Carol")
    by_name = open_dialog(carol, "Join by name", "Request to join")
    by_name.get_by_label("Group name").fill(name.lower())
    with carol.expect_response(api("POST", "/api/join-requests")):
        by_name.get_by_role("button", name="Send request").click()
    expect(carol.get_by_role("status")).to_have_text("Request sent. The owner will decide.")

    open_group(ada, "My groups", name)
    with ada.expect_response(lambda r: r.url.endswith("/reject")):
        section(ada, "Pending requests").get_by_role("button", name="Reject Carol").click()
    expect(section(ada, "Pending requests")).to_contain_text("No pending requests.")
    expect(section(ada, "Members")).not_to_contain_text("Carol")

    load_home(carol)
    search_groups(carol, name)
    expect(
        section(carol, "Browse groups").get_by_role("button", name=f"Request to join {name}")
    ).to_be_visible()


def test_unknown_group_name_says_so(page: Page) -> None:
    register_and_sign_in(page, unique_user_id("bob"), "Bob")
    by_name = open_dialog(page, "Join by name", "Request to join")
    by_name.get_by_label("Group name").fill(unique_group_name("Nowhere"))

    with page.expect_response(api("POST", "/api/join-requests")):
        by_name.get_by_role("button", name="Send request").click()

    expect(by_name.get_by_role("alert")).to_have_text("No group has that name.")


def test_taken_group_name_says_so(page: Page) -> None:
    name = unique_group_name("Goa")
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    create_group(page, name)
    create_form = open_dialog(page, "New group", "Create group")
    create_form.get_by_label("Name").fill(name.upper())

    with page.expect_response(api("POST", "/api/groups")):
        create_form.get_by_role("button", name="Create group").click()

    expect(create_form.get_by_role("alert")).to_have_text("That group name is already taken.")


@pytest.mark.parametrize(
    ("scheme", "background", "text"),
    [
        ("light", "rgb(248, 250, 252)", "rgb(15, 23, 42)"),
        ("dark", "rgb(15, 23, 42)", "rgb(241, 245, 249)"),
    ],
)
def test_theme_follows_the_system_colour_scheme(
    page: Page, scheme: Literal["light", "dark"], background: str, text: str
) -> None:
    page.emulate_media(color_scheme=scheme)

    load_signed_out(page)

    expect(page.locator("body")).to_have_css("background-color", background)
    expect(page.locator("body")).to_have_css("color", text)


def _group_request(response_url: str) -> bool:
    return urlsplit(response_url).path.startswith("/api/groups/")


def test_shell_shows_the_brand_title_and_icon(page: Page) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada Lovelace")

    expect(page.get_by_role("banner").get_by_role("link", name="Caravan")).to_be_visible()
    expect(page).to_have_title("Groups · Caravan")
    expect(page.locator('meta[name="theme-color"]')).to_have_attribute("content", "#e8552f")
    icon = page.locator('link[rel="icon"]').get_attribute("href")
    assert icon == "/favicon.svg"
    assert page.request.get(icon).status == 200


def test_skip_link_moves_focus_to_the_main_content(page: Page) -> None:
    load_signed_out(page)

    page.keyboard.press("Tab")
    skip = page.get_by_role("link", name="Skip to content")
    expect(skip).to_be_focused()
    expect(skip).to_be_in_viewport()
    page.keyboard.press("Enter")

    expect(page.get_by_role("main")).to_be_focused()


def test_opening_a_group_gives_it_an_address_and_back_returns_home(page: Page) -> None:
    name = unique_group_name("Goa")
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    create_group(page, name)

    open_group(page, "My groups", name)
    expect(page).to_have_url(re.compile(r"/groups/[1-9][0-9]*$"))
    expect(page).to_have_title(f"{name} · Caravan")

    back_to_home(page)
    expect(page).to_have_url(re.compile(r"^[^?#]*//[^/]+/$"))
    expect(section(page, "My groups").get_by_role("link", name=name)).to_be_visible()
    expect(page).to_have_title("Groups · Caravan")


def test_a_group_address_opens_directly_and_survives_a_refresh(page: Page) -> None:
    name = unique_group_name("Goa")
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    create_group(page, name)
    open_group(page, "My groups", name)
    address = group_path(page)

    with page.expect_response(lambda r: _group_request(r.url)):
        load(page, address)
    expect(page.get_by_role("heading", name=name, level=2)).to_be_visible()

    with page.expect_response(lambda r: _group_request(r.url)):
        page.reload()
    expect(page.get_by_role("heading", name=name, level=2)).to_be_visible()


def test_signed_out_visitor_lands_on_the_group_after_signing_in(page: Page) -> None:
    name = unique_group_name("Goa")
    user_id = unique_user_id("ada")
    register_and_sign_in(page, user_id, "Ada")
    create_group(page, name)
    open_group(page, "My groups", name)
    address = group_path(page)
    sign_out(page)

    load(page, address)
    expect(form(page, "Sign in")).to_be_visible()
    with page.expect_response(lambda r: _group_request(r.url)):
        sign_in(page, user_id)

    expect(page.get_by_role("heading", name=name, level=2)).to_be_visible()
    assert urlsplit(page.url).path == address


@pytest.mark.parametrize("path", ["/nowhere", "/groups/abc"])
def test_unknown_address_shows_page_not_found(page: Page, path: str) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada")

    load(page, path)

    expect(page.get_by_role("heading", name="Page not found")).to_be_visible()
    expect(page).to_have_title("Page not found · Caravan")
    with (
        page.expect_response(api("GET", "/api/me/groups")),
        page.expect_response(api("GET", "/api/groups")),
    ):
        page.get_by_role("link", name="Go to your groups").click()
    expect(section(page, "My groups")).to_be_visible()


def test_missing_group_says_so(page: Page) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada")

    with page.expect_response(api("GET", "/api/groups/999999999")):
        load(page, "/groups/999999999")

    expect(page.get_by_role("alert")).to_have_text("That group no longer exists.")
    expect(page.get_by_role("link", name="Back to groups")).to_have_attribute("href", "/")


def test_closing_a_dialog_returns_focus_to_its_opener(page: Page) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    new_group = page.get_by_role("button", name="New group", exact=True).first
    join_by_name = page.get_by_role("button", name="Join by name", exact=True)

    create_form = open_dialog(page, "New group", "Create group")
    expect(create_form.get_by_label("Name")).to_be_focused()
    create_form.get_by_label("Name").fill("Never sent")
    page.keyboard.press("Escape")

    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(form(page, "Create group")).to_have_count(0)
    expect(new_group).to_be_focused()

    by_name = open_dialog(page, "Join by name", "Request to join")
    expect(by_name.get_by_label("Group name")).to_be_focused()
    by_name.get_by_role("button", name="Cancel").click()

    expect(form(page, "Request to join")).to_have_count(0)
    expect(join_by_name).to_be_focused()


def test_creating_a_group_returns_focus_to_new_group(page: Page) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    # A new member starts with the empty state's own New group button.
    section(page, "My groups").get_by_role("button", name="New group").click()
    create_form = form(page, "Create group")
    create_form.get_by_label("Name").fill(unique_group_name("Goa"))

    with page.expect_response(api("GET", "/api/me/groups")):
        create_form.get_by_role("button", name="Create group").click()

    # The empty state is gone with its button, so focus lands on the header's New group.
    expect(section(page, "My groups").get_by_role("listitem")).to_have_count(1)
    expect(page.get_by_role("button", name="New group", exact=True)).to_be_focused()

    create_group(page, unique_group_name("Ladakh"))
    expect(page.get_by_role("button", name="New group", exact=True)).to_be_focused()


def test_clear_search_shows_every_group_again(page: Page) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    create_group(page, unique_group_name("Goa"))
    search_groups(page, unique_group_name("Nowhere"))
    browse = section(page, "Browse groups")
    expect(browse.get_by_text("No groups found.")).to_be_visible()

    with page.expect_response(api("GET", "/api/groups")):
        browse.get_by_role("button", name="Clear search").click()

    expect(browse.get_by_label("Search by name")).to_have_value("")
    expect(browse.get_by_text("No groups found.")).to_have_count(0)
    expect(browse.get_by_role("listitem").first).to_be_visible()


def test_welcome_panel_sits_beside_the_forms_wide_and_above_them_narrow(page: Page) -> None:
    page.set_viewport_size({"width": 1280, "height": 900})
    load_signed_out(page)
    welcome = page.get_by_role("region", name="Plan trips together.")
    expect(welcome).to_contain_text("Caravan")

    panel, sign_in_box = welcome.bounding_box(), form(page, "Sign in").bounding_box()
    assert panel is not None and sign_in_box is not None
    assert panel["x"] + panel["width"] <= sign_in_box["x"], (panel, sign_in_box)
    assert panel["y"] < sign_in_box["y"] + sign_in_box["height"], (panel, sign_in_box)

    page.set_viewport_size({"width": 360, "height": 740})
    panel, sign_in_box = welcome.bounding_box(), form(page, "Sign in").bounding_box()
    assert panel is not None and sign_in_box is not None
    assert panel["y"] + panel["height"] <= sign_in_box["y"], (panel, sign_in_box)
    expect(form(page, "Sign in")).to_be_visible()
    expect(form(page, "Register")).to_be_visible()


def _long_group_name() -> str:
    # 60 characters, no spaces: the longest name a group can have, and the hardest to wrap.
    return f"Goa{uuid.uuid4().hex}{uuid.uuid4().hex}"[:60]


def test_no_screen_scrolls_sideways_on_a_phone(page: Page) -> None:
    page.set_viewport_size(PHONE)
    name = _long_group_name()
    load_signed_out(page)
    assert sideways_overflow(page) == 0

    register_and_sign_in(page, unique_user_id("ada"), "A" * 50)
    create_group(page, name, "x" * 200)
    assert sideways_overflow(page) == 0

    open_group(page, "My groups", name)
    expect(section(page, "Members")).to_contain_text("A" * 50)
    assert sideways_overflow(page) == 0

    load(page, "/nowhere")
    expect(page.get_by_role("heading", name="Page not found")).to_be_visible()
    assert sideways_overflow(page) == 0


def test_buttons_and_links_are_easy_to_tap_on_a_phone(page: Page) -> None:
    page.set_viewport_size(PHONE)
    name = unique_group_name("Goa")
    load_signed_out(page)
    assert small_targets(page) == []

    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    create_group(page, name, "Beach week")
    assert small_targets(page) == []

    open_dialog(page, "New group", "Create group")
    assert small_targets(page) == []
    page.keyboard.press("Escape")

    open_group(page, "My groups", name)
    assert small_targets(page) == []


def test_reduced_motion_stops_animation(page: Page) -> None:
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    page.emulate_media(reduced_motion="reduce")
    held: list[Route] = []

    # Hold my groups unanswered, so its loading skeleton stays on screen to inspect.
    # Playwright tags its handlers, so this has to be a plain function, not list.append.
    def hold(route: Route) -> None:
        held.append(route)

    page.route("**/api/me/groups", hold)

    load(page)
    skeleton = section(page, "My groups").locator(".skeleton").first
    expect(skeleton).to_be_visible()
    expect(skeleton).to_have_css("animation-name", "none")
    expect(page.get_by_role("button", name="New group", exact=True)).to_have_css(
        "transition-duration", "0s"
    )

    assert len(held) == 1, "my groups was never requested"
    with page.expect_response(api("GET", "/api/me/groups")):
        held[0].continue_()
    expect(skeleton).to_have_count(0)


def test_text_shows_in_a_system_font_when_the_web_font_fails(page: Page) -> None:
    aborted: list[str] = []

    def block(route: Route) -> None:
        aborted.append(route.request.url)
        route.abort()

    page.route("**/*.woff2", block)

    load_signed_out(page)

    sign_in_form = form(page, "Sign in")
    expect(sign_in_form).to_have_css("font-family", re.compile(r"Inter Variable.*system-ui"))
    expect(sign_in_form.get_by_role("heading", name="Sign in")).to_be_visible()
    expect(sign_in_form.get_by_label("User ID")).to_be_visible()
    expect(sign_in_form.get_by_role("button", name="Sign in")).to_be_visible()
    # The page did ask for the web font, and was refused: the text above is the fallback.
    assert aborted, "no web font was requested"
