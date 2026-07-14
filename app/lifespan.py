"""Application startup validation."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.container import get_connection_service


@asynccontextmanager
async def application_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration and secrets before accepting requests."""
    get_connection_service()
    yield
