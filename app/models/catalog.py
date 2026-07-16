"""Typed snapshots, refresh state and catalog search contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.connections import ProcedureInfo, SchemaInfo, TableDescription, TriggerInfo


class CatalogRefreshState(StrEnum):
    """Persistent state of the most recent refresh attempt."""

    NEVER = "never"
    REFRESHING = "refreshing"
    SUCCESS = "success"
    ERROR = "error"


class CatalogRefreshOutcome(StrEnum):
    """Result returned by a manual or scheduled refresh request."""

    SUCCESS = "success"
    ERROR = "error"
    ALREADY_RUNNING = "already_running"
    DISABLED = "disabled"


class RelationshipCardinality(StrEnum):
    """Maximum source-to-target cardinality inferred from uniqueness metadata."""

    ONE_TO_ONE = "one-to-one"
    MANY_TO_ONE = "many-to-one"


class CardinalityInference(StrEnum):
    """Stable explanation of how relationship cardinality was inferred."""

    SOURCE_PRIMARY_KEY = "source_primary_key"
    SOURCE_UNIQUE_KEY = "source_unique_key"
    SOURCE_NOT_UNIQUE = "source_not_unique"


class CatalogSnapshot(BaseModel):
    """Atomic metadata-only snapshot for one connection."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    refreshed_at: datetime
    schema_hash: str
    schemas: tuple[SchemaInfo, ...]
    tables: tuple[TableDescription, ...]
    procedures: tuple[ProcedureInfo, ...] = ()
    triggers: tuple[TriggerInfo, ...] = ()


class CatalogRefreshRecord(BaseModel):
    """Repository representation of the latest refresh attempt."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    state: CatalogRefreshState
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    message: str | None = None


class CatalogRefreshResult(BaseModel):
    """Normalized refresh result safe to return through MCP."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    outcome: CatalogRefreshOutcome
    refreshed: bool
    started_at: datetime
    completed_at: datetime
    schema_hash: str | None = None
    schemas_count: int = 0
    tables_count: int = 0
    error_code: str | None = None
    message: str


class CatalogCacheStatus(BaseModel):
    """Observable cache freshness and last refresh state."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    state: CatalogRefreshState
    has_snapshot: bool
    stale: bool
    last_refreshed_at: datetime | None = None
    last_attempt_started_at: datetime | None = None
    last_attempt_completed_at: datetime | None = None
    schema_hash: str | None = None
    error_code: str | None = None
    message: str | None = None


class CatalogRelationship(BaseModel):
    """Foreign-key relationship with explicit source and target objects."""

    model_config = ConfigDict(frozen=True)

    name: str
    source_schema: str
    source_table: str
    source_columns: tuple[str, ...]
    target_schema: str
    target_table: str
    target_columns: tuple[str, ...]
    cardinality: RelationshipCardinality
    cardinality_inference: CardinalityInference


class CatalogSearchMatch(BaseModel):
    """One table match with relevant columns and relationships."""

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    connection_id: str
    schema_name: str = Field(alias="schema")
    table: str
    description: str | None = None
    matched_columns: tuple[str, ...]
    score: int
    relationships: tuple[CatalogRelationship, ...]


class CatalogSearchResponse(BaseModel):
    """Catalog matches plus cache freshness for the searched connections."""

    model_config = ConfigDict(frozen=True)

    query: str
    matches: tuple[CatalogSearchMatch, ...]
    cache_statuses: tuple[CatalogCacheStatus, ...]
