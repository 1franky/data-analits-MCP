"""Application startup validation."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.container import (
    get_audit_repository,
    get_catalog_scheduler,
    get_connection_service,
    get_connections_config,
    get_generation_service,
    get_object_explanation_service,
)


@asynccontextmanager
async def application_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate dependencies and manage the background catalog scheduler."""
    get_connection_service()
    get_audit_repository()
    if get_connections_config().generation.enabled:
        get_generation_service()
        get_object_explanation_service()
    scheduler = get_catalog_scheduler()
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
