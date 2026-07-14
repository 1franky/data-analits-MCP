"""MCP tools for metadata catalog refresh, status and search."""

from typing import Annotated

from pydantic import Field

from app.container import get_catalog_service
from app.models.catalog import (
    CatalogCacheStatus,
    CatalogRefreshResult,
    CatalogSearchResponse,
)


def refresh_schema_cache(
    connection_id: str | None = None,
) -> tuple[CatalogRefreshResult, ...]:
    """Refresh one connection, or every enabled connection when omitted."""
    service = get_catalog_service()
    if connection_id is None:
        return service.refresh_all()
    return (service.refresh_connection(connection_id),)


def get_schema_cache_status(
    connection_id: str | None = None,
) -> tuple[CatalogCacheStatus, ...]:
    """Return freshness and last refresh state for one or all connections."""
    return get_catalog_service().get_cache_status(connection_id)


def search_catalog(
    query: str,
    connection_id: str | None = None,
    max_results: Annotated[int, Field(ge=1, le=100)] = 20,
) -> CatalogSearchResponse:
    """Search cached tables, columns, descriptions and relationships."""
    return get_catalog_service().search(query, connection_id, max_results)
