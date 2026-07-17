"""Models returned by administrative health endpoints."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Stable response contract for the liveness endpoint."""

    status: Literal["ok"]
    service: str
    version: str


class ReadinessCheck(BaseModel):
    """One named readiness signal and its current state."""

    name: str
    ready: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    """Response contract for the readiness endpoint, distinct from liveness."""

    status: Literal["ready", "not_ready"]
    service: str
    version: str
    checks: tuple[ReadinessCheck, ...]
