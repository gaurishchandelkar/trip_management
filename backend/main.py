import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from backend.api.errors import invalid_request
from backend.api.routes import router
from backend.storage.store import Store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "trip.db"


def database_path() -> Path:
    configured = os.environ.get("TRIP_DB_PATH")
    return Path(configured) if configured else DEFAULT_DB_PATH


def create_app(db_path: Path | None = None) -> FastAPI:
    store = Store(db_path or database_path())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        store.create_schema()
        yield

    app = FastAPI(title="Trip Management", lifespan=lifespan)
    app.state.store = store
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.include_router(router)
    return app


app = create_app()
