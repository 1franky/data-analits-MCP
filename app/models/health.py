"""Models returned by administrative health endpoints."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Stable response contract for the liveness endpoint."""

    status: Literal["ok"]
    service: str
    version: str
