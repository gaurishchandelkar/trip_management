from backend.main import create_app


def test_create_app_registers_api_routes() -> None:
    paths = create_app().openapi()["paths"]

    assert {"/api/health", "/api/hello"} <= paths.keys()
