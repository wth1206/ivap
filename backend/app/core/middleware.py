"""HTTP middleware: request id, process time and access logging."""

import logging
import re
import time
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import reset_request_id, set_request_id

logger = logging.getLogger("app.access")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware:
    """Pure ASGI middleware.

    Using ASGI directly (instead of BaseHTTPMiddleware) keeps the request id
    available for both normal and error responses and avoids streaming issues.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id")
        request_id = incoming if incoming and _REQUEST_ID_PATTERN.match(incoming) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = set_request_id(request_id)
        started = time.perf_counter()
        status_code: int = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            client = scope.get("client")
            client_host = client[0] if client else "-"
            logger.info(
                "%s %s -> %s (%.2f ms) client=%s",
                scope.get("method", "-"),
                scope.get("path", "-"),
                status_code,
                elapsed_ms,
                client_host,
            )
            reset_request_id(token)


def add_request_id_header(response: Any, request_id: str) -> None:
    """Utility for handlers that build responses outside the middleware stack."""
    if request_id and request_id != "-":
        response.headers["X-Request-ID"] = request_id
