"""Outside (black-box) journeys: only what the user sees."""

from playwright.sync_api import Dialog, Page, expect


def test_shows_default_greeting(page: Page) -> None:
    page.goto("/")

    expect(page.get_by_role("heading", name="Hello, World!")).to_be_visible()


def test_shows_alert_when_backend_fails(page: Page) -> None:
    page.route("**/api/hello", lambda route: route.fulfill(status=500))

    page.goto("/")

    expect(page.get_by_role("alert")).to_contain_text("Could not load greeting")


def test_greets_entered_name(page: Page) -> None:
    page.goto("/")
    expect(page.get_by_role("heading", name="Hello, World!")).to_be_visible()

    page.get_by_label("Your name").fill("Ada")
    page.get_by_role("button", name="Greet").click()

    expect(page.get_by_role("heading", name="Hello, Ada!")).to_be_visible()


def test_rejects_markup_without_rendering_it(page: Page) -> None:
    dialogs: list[str] = []

    def dismiss(dialog: Dialog) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", dismiss)
    page.goto("/")
    expect(page.get_by_role("heading", name="Hello, World!")).to_be_visible()

    page.get_by_label("Your name").fill("<script>alert(1)</script>")
    page.get_by_role("button", name="Greet").click()

    expect(page.get_by_role("alert")).to_contain_text("Please enter a valid name")
    expect(page.locator("main script")).to_have_count(0)
    assert dialogs == []
