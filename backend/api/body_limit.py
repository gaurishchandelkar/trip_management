from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 4096


class BodySizeLimit:
    """Stops reading a request body past MAX_BODY_BYTES, whether or not Content-Length is set."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_BODY_BYTES:
                    # An HTTPException, because FastAPI turns any other error raised while it
                    # reads the body into a 400.
                    raise HTTPException(status_code=413, detail="Request too large")
            return message

        await self.app(scope, limited_receive, send)
