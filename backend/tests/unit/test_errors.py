import asyncio
import json

import pytest
from fastapi import Request

from backend.api.errors import domain_error, invalid_request
from backend.domain.errors import (
    AlreadyMemberError,
    DomainError,
    ForbiddenError,
    GroupNameTakenError,
    InvalidCredentialsError,
    LimitReachedError,
    NotFoundError,
    RequestAlreadyPendingError,
    StorageUnavailableError,
    UnauthenticatedError,
    UserIdTakenError,
)

REQUEST = Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def test_invalid_request_returns_generic_422() -> None:
    response = asyncio.run(invalid_request(REQUEST, ValueError("<script>")))

    assert response.status_code == 422
    assert json.loads(bytes(response.body)) == {"detail": "Invalid request"}


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (UserIdTakenError(), 409, "User ID already taken"),
        (GroupNameTakenError(), 409, "Group name already taken"),
        (RequestAlreadyPendingError(), 409, "Request already pending"),
        (AlreadyMemberError(), 409, "Already a member"),
        (LimitReachedError(), 409, "Limit reached"),
        (NotFoundError(), 404, "Not found"),
        (ForbiddenError(), 403, "Forbidden"),
        (InvalidCredentialsError(), 401, "Invalid user ID or password"),
        (UnauthenticatedError(), 401, "Not signed in"),
        (StorageUnavailableError("SELECT secret FROM members"), 503, "Service unavailable"),
        (DomainError("unmapped"), 500, "Internal server error"),
    ],
)
def test_domain_errors_map_to_fixed_responses(error: DomainError, status: int, detail: str) -> None:
    response = asyncio.run(domain_error(REQUEST, error))

    assert response.status_code == status
    assert json.loads(bytes(response.body)) == {"detail": detail}
