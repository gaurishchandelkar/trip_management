from fastapi import Request
from fastapi.responses import JSONResponse


async def invalid_request(_request: Request, _exc: Exception) -> JSONResponse:
    # Generic body: never echo user input back (docs/SECURITY_GUIDELINES.md).
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})
