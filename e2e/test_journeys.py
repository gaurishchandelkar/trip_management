"""Outside (black-box) journeys: only what the user sees."""

from collections.abc import Iterator
from typing import Literal

import pytest
from playwright.sync_api import Browser, Dialog, Page, expect

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
    expect(section(ada, "My groups").get_by_role("button", name=name)).to_be_visible()

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
    by_name = form(carol, "Request to join")
    by_name.get_by_label("Group name").fill(name.lower())
    with carol.expect_response(api("POST", "/api/join-requests")):
        by_name.get_by_role("button", name="Send request").click()
    expect(by_name.get_by_role("status")).to_have_text("Request sent. The owner will decide.")

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
    by_name = form(page, "Request to join")
    by_name.get_by_label("Group name").fill(unique_group_name("Nowhere"))

    with page.expect_response(api("POST", "/api/join-requests")):
        by_name.get_by_role("button", name="Send request").click()

    expect(by_name.get_by_role("alert")).to_have_text("No group has that name.")


def test_taken_group_name_says_so(page: Page) -> None:
    name = unique_group_name("Goa")
    register_and_sign_in(page, unique_user_id("ada"), "Ada")
    create_group(page, name)
    create_form = form(page, "Create group")
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
