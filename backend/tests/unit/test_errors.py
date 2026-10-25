import asyncio
import json

from fastapi import Request

from backend.api.errors import invalid_request


def test_invalid_request_returns_generic_422() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

    response = asyncio.run(invalid_request(request, ValueError("<script>")))

    assert response.status_code == 422
    assert json.loads(bytes(response.body)) == {"detail": "Invalid request"}
