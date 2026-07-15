"""Versioned MCP contracts for discovery and cached database metadata."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.catalog import CatalogCacheStatus, CatalogRelationship
from app.models.connections import (
    ConnectionSummary,
    SchemaInfo,
    TableDescription,
)
from app.models.contracts import VersionedToolResponse


class McpHealthResponse(VersionedToolResponse):
    """Liveness and version information exposed through MCP."""

    status: Literal["ok"]
    service: str
    server_version: str


class ConnectionCapabilitiesResponse(VersionedToolResponse):
    """One safe connection declaration and its adapter capabilities."""

    connection_id: str
    connection: ConnectionSummary


class SchemaListResponse(VersionedToolResponse):
    """Visible schemas from one cached catalog snapshot."""

    connection_id: str
    schemas: tuple[SchemaInfo, ...]
    cache_status: CatalogCacheStatus


class TableSummary(BaseModel):
    """Compact table metadata for discovery lists."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, serialize_by_alias=True)

    schema_name: str = Field(alias="schema")
    name: str
    kind: Literal["table", "partitioned_table"]
    description: str | None = None
    column_count: int
    primary_key: tuple[str, ...]

    @classmethod
    def from_description(cls, table: TableDescription) -> "TableSummary":
        """Build a compact summary without losing the table kind."""
        return cls(
            schema=table.schema_name,
            name=table.name,
            kind=table.kind,
            description=table.description,
            column_count=len(table.columns),
            primary_key=table.primary_key,
        )


class TableListResponse(VersionedToolResponse):
    """Tables from one snapshot, optionally filtered by schema."""

    connection_id: str
    schema_filter: str | None
    tables: tuple[TableSummary, ...]
    cache_status: CatalogCacheStatus


class TableDescriptionResponse(VersionedToolResponse):
    """Detailed metadata for one cached table."""

    connection_id: str
    table: TableDescription
    cache_status: CatalogCacheStatus


class RelationshipListResponse(VersionedToolResponse):
    """Foreign-key relationships relevant to optional schema/table filters."""

    connection_id: str
    schema_filter: str | None
    table_filter: str | None
    relationships: tuple[CatalogRelationship, ...]
    cache_status: CatalogCacheStatus
