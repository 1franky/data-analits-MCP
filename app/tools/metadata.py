"""MCP tools for versioned exploration of cached database metadata."""

from typing import Annotated

from pydantic import Field

from app.container import get_catalog_service
from app.models.metadata import (
    RelationshipListResponse,
    SchemaListResponse,
    TableDescriptionResponse,
    TableListResponse,
)

MetadataName = Annotated[str, Field(min_length=1, max_length=128)]


def list_schemas(connection_id: str) -> SchemaListResponse:
    """List visible schemas from the selected connection's cached snapshot."""
    return get_catalog_service().list_schemas(connection_id)


def list_tables(
    connection_id: str,
    schema: MetadataName | None = None,
) -> TableListResponse:
    """List cached tables, optionally restricted to one schema."""
    return get_catalog_service().list_tables(connection_id, schema)


def describe_table(
    connection_id: str,
    schema: MetadataName,
    table: MetadataName,
) -> TableDescriptionResponse:
    """Return columns, keys and comments for one cached table."""
    return get_catalog_service().describe_table(connection_id, schema, table)


def list_relationships(
    connection_id: str,
    schema: MetadataName | None = None,
    table: MetadataName | None = None,
) -> RelationshipListResponse:
    """List foreign keys whose source or target matches the optional filters."""
    return get_catalog_service().list_relationships(connection_id, schema, table)
