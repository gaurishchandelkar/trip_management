"""Inside (whitebox) checks: the exact requests the browser sends and what the backend returns.

Each test waits for the specific response it expects, then asserts every /api/ call made by then.
"""

from playwright.sync_api import Page, Response, expect

from e2e.network import ApiTraffic, Signature

LOAD: Signature = ("GET", "/api/hello", {})


def _is_greeting(response: Response) -> bool:
    return response.url.split("?")[0].endswith("/api/hello")


def _load(page: Page) -> None:
    with page.expect_response(_is_greeting):
        page.goto("/")
    expect(page.get_by_role("heading", name="Hello, World!")).to_be_visible()


def _load_failing(page: Page) -> None:
    with page.expect_response(_is_greeting):
        page.goto("/")
    expect(page.get_by_role("alert")).to_contain_text("Could not load greeting")


def _greet(page: Page, name: str) -> None:
    _load(page)
    page.get_by_label("Your name").fill(name)
    with page.expect_response(lambda response: _is_greeting(response) and "name=" in response.url):
        page.get_by_role("button", name="Greet").click()


def test_load_requests_default_greeting_once(page: Page, traffic: ApiTraffic) -> None:
    _load(page)

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [LOAD], traffic.describe()
    assert (calls[0].status, calls[0].json()) == (200, {"message": "Hello, World!"})


def test_backend_failure_requests_greeting_once(page: Page, traffic: ApiTraffic) -> None:
    page.route("**/api/hello", lambda route: route.fulfill(status=500))

    _load_failing(page)

    calls = traffic.api_calls()
    assert [call.signature for call in calls] == [LOAD], traffic.describe()
    assert calls[0].status == 500


def test_greet_sends_trimmed_name_once(page: Page, traffic: ApiTraffic) -> None:
    _greet(page, "  Ada  ")
    expect(page.get_by_role("heading", name="Hello, Ada!")).to_be_visible()

    calls = traffic.api_calls()
    greet = ("GET", "/api/hello", {"name": ["Ada"]})
    assert [call.signature for call in calls] == [LOAD, greet], traffic.describe()
    assert (calls[1].status, calls[1].json()) == (200, {"message": "Hello, Ada!"})


def test_greet_sends_full_name_intact(page: Page, traffic: ApiTraffic) -> None:
    _greet(page, "Ada Lovelace")
    expect(page.get_by_role("heading", name="Hello, Ada Lovelace!")).to_be_visible()

    calls = traffic.api_calls()
    greet = ("GET", "/api/hello", {"name": ["Ada Lovelace"]})
    assert [call.signature for call in calls] == [LOAD, greet], traffic.describe()
    assert (calls[1].status, calls[1].json()) == (200, {"message": "Hello, Ada Lovelace!"})


def test_markup_gets_generic_422_without_echo(page: Page, traffic: ApiTraffic) -> None:
    markup = "<script>alert(1)</script>"
    _greet(page, markup)
    expect(page.get_by_role("alert")).to_contain_text("Please enter a valid name")

    calls = traffic.api_calls()
    greet = ("GET", "/api/hello", {"name": [markup]})
    assert [call.signature for call in calls] == [LOAD, greet], traffic.describe()
    assert (calls[1].status, calls[1].json()) == (422, {"detail": "Invalid request"})
    assert "script" not in (calls[1].body or "")
    assert "alert(1)" not in (calls[1].body or "")
