import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx2
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from backend.api import auth, groups, members
from backend.api.body_limit import BodySizeLimit
from backend.api.errors import domain_error, invalid_request
from backend.api.routes import router
from backend.domain.errors import DomainError
from backend.identity.config import google_settings
from backend.identity.oidc import OidcProvider
from backend.storage.store import Store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "trip.db"


def database_path() -> Path:
    configured = os.environ.get("TRIP_DB_PATH")
    return Path(configured) if configured else DEFAULT_DB_PATH


def create_app(db_path: Path | None = None) -> FastAPI:
    store = Store(db_path or database_path())
    # Google sign-in is on only when its client ID and secret are set (spec sso-registration).
    settings = google_settings(os.environ)
    http = httpx2.Client()
    provider = None if settings is None else OidcProvider("google", settings, http)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        store.create_schema()
        yield
        http.close()

    app = FastAPI(title="Trip Management", lifespan=lifespan)
    app.state.store = store
    app.state.identity_provider = provider
    app.add_middleware(BodySizeLimit)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.add_exception_handler(DomainError, domain_error)
    app.include_router(router)
    app.include_router(members.router)
    app.include_router(groups.router)
    app.include_router(auth.router)
    return app


app = create_app()
