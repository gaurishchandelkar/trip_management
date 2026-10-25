from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_clock
from backend.main import create_app

type SignedIn = Callable[[str], TestClient]


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2027, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "trip.db"


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def app(db_path: Path, clock: FakeClock) -> FastAPI:
    app = create_app(db_path)
    app.dependency_overrides[get_clock] = lambda: clock
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # The context manager runs the lifespan, which creates the schema.
    with TestClient(app) as client:
        yield client


@pytest.fixture
def signed_in(app: FastAPI, client: TestClient) -> Iterator[SignedIn]:
    """Registers and signs in a member, each with their own cookie jar."""
    clients: list[TestClient] = []

    def sign_in(user_id: str) -> TestClient:
        member = TestClient(app)
        clients.append(member)
        display_name = user_id.capitalize()
        register = member.post(
            "/api/members", json={"user_id": user_id, "display_name": display_name}
        )
        assert register.status_code == 201, register.text
        response = member.post("/api/sign-in", json={"user_id": user_id, "password": "x"})
        assert response.status_code == 200, response.text
        return member

    yield sign_in
    for member in clients:
        member.close()
