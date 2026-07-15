"""Typed SQL validation, execution and plan contracts."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue

QueryParameter = str | int | float | bool | None
SerializedValue = str | int | float | bool | None


class QueryPolicyConfig(BaseModel):
    """Global safety limits applied in addition to connection-specific limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    global_max_rows: Annotated[int, Field(ge=1, le=10_000)] = 1_000
    max_serialized_bytes: Annotated[int, Field(ge=1_024, le=100_000_000)] = 1_000_000
    max_concurrent_queries: Annotated[int, Field(ge=1, le=64)] = 4


class SqlStatementType(StrEnum):
    """Normalized statement families exposed through MCP and audit."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    MERGE = "MERGE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    COPY = "COPY"
    GRANT = "GRANT"
    REVOKE = "REVOKE"
    COMMAND = "COMMAND"
    MULTIPLE = "MULTIPLE"
    UNKNOWN = "UNKNOWN"


class ValidationIssue(BaseModel):
    """Stable machine-readable validation reason or warning."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str


class ReferencedObject(BaseModel):
    """Table-like object referenced by a parsed statement."""

    model_config = ConfigDict(frozen=True)

    schema_name: str | None = None
    name: str


class SqlValidationResult(BaseModel):
    """Complete result of parsing and applying the read-only policy."""

    model_config = ConfigDict(frozen=True)

    valid: bool
    read_only: bool
    executable: bool
    statement_type: SqlStatementType
    dialect: str
    multiple_statements: bool
    normalized_sql: str | None
    blocked_reasons: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]
    referenced_objects: tuple[ReferencedObject, ...]
    parameter_names: tuple[str, ...]


class PreparedReadQuery(BaseModel):
    """Validated SELECT rewritten with an enforced outer row limit."""

    model_config = ConfigDict(frozen=True)

    sql: str
    row_limit: int
    limit_reduced: bool


class AdapterQueryResult(BaseModel):
    """Serializable result returned by a SQL adapter after execution."""

    model_config = ConfigDict(frozen=True)

    columns: tuple[str, ...]
    rows: tuple[tuple[SerializedValue, ...], ...]
    duration_ms: float
    truncated: bool
    serialized_bytes: int


class AdapterQueryPlan(BaseModel):
    """Normalized plan returned by a SQL adapter."""

    model_config = ConfigDict(frozen=True)

    plan: JsonValue
    duration_ms: float


class QueryExecutionResult(BaseModel):
    """Structured outcome of the execute_read_query use case."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    executed: bool
    validation: SqlValidationResult
    executed_sql: str | None = None
    columns: tuple[str, ...] = ()
    rows: tuple[tuple[SerializedValue, ...], ...] = ()
    row_count: int = 0
    row_limit: int | None = None
    truncated: bool = False
    serialized_bytes: int = 0
    duration_ms: float = 0.0
    error_code: str | None = None
    message: str


class QueryPlanResult(BaseModel):
    """Structured outcome of a safe EXPLAIN request."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    explained: bool
    analyze: bool = False
    validation: SqlValidationResult
    explained_sql: str | None = None
    plan: JsonValue | None = None
    duration_ms: float = 0.0
    error_code: str | None = None
    message: str
