"""Per-request correlation identifier propagated through logging."""

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
