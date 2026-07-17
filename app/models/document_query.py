"""Typed document (MongoDB) validation, execution and contract models."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, JsonValue

from app.models.connections import CollectionInfo
from app.models.contracts import VersionedToolResponse
from app.models.query import ValidationIssue


class DocumentOperationType(StrEnum):
    """Operation family exposed through MCP and audit."""

    FIND = "find"
    AGGREGATE = "aggregate"
    UNKNOWN = "unknown"


class DocumentQueryValidationResult(BaseModel):
    """Complete result of applying the document read-only operator policy."""

    model_config = ConfigDict(frozen=True)

    valid: bool
    executable: bool
    operation: DocumentOperationType
    collection: str
    blocked_reasons: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]


class AdapterDocumentResult(BaseModel):
    """Serializable result returned by a document adapter after execution."""

    model_config = ConfigDict(frozen=True)

    documents: tuple[JsonValue, ...]
    duration_ms: float
    truncated: bool
    serialized_bytes: int


class DocumentQueryExecutionResult(VersionedToolResponse):
    """Structured outcome of an execute_mongo_find/execute_mongo_aggregate use case."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    collection: str
    operation: DocumentOperationType
    executed: bool
    validation: DocumentQueryValidationResult
    documents: tuple[JsonValue, ...] = ()
    document_count: int = 0
    row_limit: int | None = None
    truncated: bool = False
    serialized_bytes: int = 0
    duration_ms: float = 0.0
    error_code: str | None = None
    message: str


class MongoCollectionListResponse(VersionedToolResponse):
    """List of collections visible in the cached-free, live document connection."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    collections: tuple[CollectionInfo, ...]
