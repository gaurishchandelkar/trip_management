from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import ROOT, create_app
from backend.storage.store import Store


def test_create_app_registers_api_routes(tmp_path: Path) -> None:
    paths = create_app(tmp_path / "trip.db").openapi()["paths"]

    assert {"/api/health", "/api/hello"} <= paths.keys()


def test_startup_creates_the_database_at_the_given_path(tmp_path: Path) -> None:
    path = tmp_path / "trip.db"

    with TestClient(create_app(path)):
        assert path.is_file()


def test_database_path_comes_from_trip_db_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRIP_DB_PATH", str(tmp_path / "configured.db"))

    store: Store = create_app().state.store

    assert store.path == tmp_path / "configured.db"


def test_database_path_defaults_to_the_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRIP_DB_PATH", raising=False)

    store: Store = create_app().state.store

    assert store.path.resolve() == ROOT / "trip.db"
