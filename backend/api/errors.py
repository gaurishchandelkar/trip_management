import logging

from fastapi import Request
from fastapi.responses import JSONResponse

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

logger = logging.getLogger(__name__)

# Fixed bodies only: never echo input, IDs or storage details (docs/SECURITY_GUIDELINES.md).
ERROR_RESPONSES: dict[type[DomainError], tuple[int, str]] = {
    UserIdTakenError: (409, "User ID already taken"),
    GroupNameTakenError: (409, "Group name already taken"),
    RequestAlreadyPendingError: (409, "Request already pending"),
    AlreadyMemberError: (409, "Already a member"),
    LimitReachedError: (409, "Limit reached"),
    NotFoundError: (404, "Not found"),
    ForbiddenError: (403, "Forbidden"),
    InvalidCredentialsError: (401, "Invalid user ID or password"),
    UnauthenticatedError: (401, "Not signed in"),
    StorageUnavailableError: (503, "Service unavailable"),
}
UNEXPECTED = (500, "Internal server error")


async def invalid_request(_request: Request, _exc: Exception) -> JSONResponse:
    # Generic body: never echo user input back (docs/SECURITY_GUIDELINES.md).
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})


async def domain_error(_request: Request, exc: Exception) -> JSONResponse:
    # The most specific mapped class wins, so InvalidCredentialsError beats UnauthenticatedError.
    status, detail = next(
        (ERROR_RESPONSES[cls] for cls in type(exc).__mro__ if cls in ERROR_RESPONSES), UNEXPECTED
    )
    if status == 503:
        logger.warning("storage unavailable", exc_info=exc)
    return JSONResponse(status_code=status, content={"detail": detail})
