import pytest
from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hello_defaults_to_world(client: TestClient) -> None:
    response = client.get("/api/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}


@pytest.mark.parametrize("name", ["Ada", "Zoë", "Mary Jane", "Jean-Luc", "O'Brien", "A" * 50])
def test_hello_greets_valid_names(client: TestClient, name: str) -> None:
    response = client.get("/api/hello", params={"name": name})

    assert response.status_code == 200
    assert response.json() == {"message": f"Hello, {name}!"}


@pytest.mark.parametrize(
    "name", ["A" * 51, "<script>", "R2D2", "100%", " Ada", "Ada ", "", "Mary  Jane", "-Ada"]
)
def test_hello_rejects_invalid_names_without_echoing_input(client: TestClient, name: str) -> None:
    response = client.get("/api/hello", params={"name": name})

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request"}


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/missing").status_code == 404
