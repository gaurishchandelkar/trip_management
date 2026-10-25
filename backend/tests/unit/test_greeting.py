from backend.api.routes import health, hello
from backend.domain.greeting import Greeting, greeting_for
from backend.services.greeting import get_greeting


def test_greeting_defaults_to_world() -> None:
    assert greeting_for(None) == Greeting(message="Hello, World!")


def test_greeting_uses_name() -> None:
    assert greeting_for("Ada") == Greeting(message="Hello, Ada!")


def test_service_passes_name_through() -> None:
    assert get_greeting("Ada").message == "Hello, Ada!"
    assert get_greeting().message == "Hello, World!"


def test_hello_route_wraps_service_greeting() -> None:
    assert hello().message == "Hello, World!"


def test_health_route_reports_ok() -> None:
    assert health().status == "ok"
