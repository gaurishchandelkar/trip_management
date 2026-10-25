from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from backend.api.errors import invalid_request
from backend.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Hyper Harness")
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.include_router(router)
    return app


app = create_app()
