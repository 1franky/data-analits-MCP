"""Pure ASGI middleware assigning a request id and logging request completion."""

import logging
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.context import request_id_var

_logger = logging.getLogger("app.access")


class RequestContextMiddleware:
    """Assign a per-request correlation id and log completion, without buffering."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = str(uuid4())
        token = request_id_var.set(request_id)
        started_at = perf_counter()
        status_holder: dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = MutableHeaders(scope=message)
                headers.append("x-request-id", request_id)
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        except Exception:
            _logger.exception(
                "request_failed",
                extra={"method": scope.get("method"), "path": scope.get("path")},
            )
            raise
        finally:
            _logger.info(
                "request_completed",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_holder.get("status"),
                    "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                },
            )
            request_id_var.reset(token)
