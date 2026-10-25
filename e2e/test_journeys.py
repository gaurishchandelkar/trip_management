"""Outside (black-box) journeys: only what the user sees."""

from playwright.sync_api import Dialog, Page, expect

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
