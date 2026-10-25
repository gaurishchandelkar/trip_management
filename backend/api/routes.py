from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.api.schemas import NAME_MAX_LENGTH, NAME_PATTERN
from backend.services.greeting import get_greeting

router = APIRouter(prefix="/api")


class HealthResponse(BaseModel):
    status: str


class GreetingResponse(BaseModel):
    message: str


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/hello")
def hello(
    name: Annotated[str | None, Query(max_length=NAME_MAX_LENGTH, pattern=NAME_PATTERN)] = None,
) -> GreetingResponse:
    return GreetingResponse(message=get_greeting(name).message)
