"""Configuration and transport models for database connections."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.audit import AuditConfig
from app.models.query import QueryPolicyConfig

ConnectionOptionValue = str | int | bool


class CatalogConfig(BaseModel):
    """Validated catalog refresh, expiry and filtering policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    refresh_interval_minutes: Annotated[int, Field(ge=1, le=10_080)] = 60
    refresh_on_startup: bool = True
    stale_after_minutes: Annotated[int, Field(ge=1, le=43_200)] = 120
    excluded_schemas: tuple[str, ...] = ("information_schema", "pg_catalog")
    include_table_patterns: tuple[str, ...] = ("*",)
    exclude_table_patterns: tuple[str, ...] = ()

    @field_validator(
        "excluded_schemas",
        "include_table_patterns",
        "exclude_table_patterns",
    )
    @classmethod
    def normalize_catalog_filters(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize filter entries and reject blanks or duplicates."""
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("los filtros del catálogo no pueden estar vacíos")
        if len(set(normalized)) != len(normalized):
            raise ValueError("los filtros del catálogo no pueden estar duplicados")
        return normalized

    @model_validator(mode="after")
    def require_include_pattern(self) -> Self:
        """Ensure an enabled catalog has at least one inclusion pattern."""
        if self.enabled and not self.include_table_patterns:
            raise ValueError("un catálogo habilitado requiere include_table_patterns")
        return self


class ConnectionType(StrEnum):
    """Known engine identifiers accepted by configuration."""

    POSTGRES = "postgres"
    SQLSERVER = "sqlserver"
    MARIADB = "mariadb"
    INFORMIX = "informix"
    MONGODB = "mongodb"
    ORACLE = "oracle"


class QueryLanguage(StrEnum):
    """Query language families exposed by adapters."""

    SQL = "sql"
    DOCUMENT = "document"


class ConnectionCapabilities(BaseModel):
    """Capabilities that an adapter can currently fulfill."""

    model_config = ConfigDict(frozen=True)

    query_language: QueryLanguage
    test_connection: bool = True
    list_schemas: bool = False
    list_tables: bool = False
    describe_table: bool = False
    primary_keys: bool = False
    foreign_keys: bool = False
    execute_read_query: bool = False
    explain_query: bool = False


class ConnectionConfig(BaseModel):
    """Validated, secret-free connection declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=63,
            pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$",
        ),
    ]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    type: ConnectionType
    host: Annotated[str, Field(min_length=1, max_length=255)]
    port: Annotated[int, Field(ge=1, le=65535)]
    database: Annotated[str, Field(min_length=1, max_length=128)]
    username: Annotated[str, Field(min_length=1, max_length=128)]
    password_env: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")]
    readonly: bool = True
    enabled: bool = True
    connect_timeout_seconds: Annotated[int, Field(ge=1, le=300)] = 10
    query_timeout_seconds: Annotated[int, Field(ge=1, le=3600)] = 30
    max_rows: Annotated[int, Field(ge=1, le=10_000)] = 500
    options: dict[str, ConnectionOptionValue] = Field(default_factory=dict)

    @field_validator("name", "host", "database", "username")
    @classmethod
    def strip_non_empty_values(cls, value: str) -> str:
        """Normalize display and connection fields without accepting blanks."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("el valor no puede estar vacío")
        return normalized

    @field_validator("options")
    @classmethod
    def reject_sensitive_options(
        cls,
        options: dict[str, ConnectionOptionValue],
    ) -> dict[str, ConnectionOptionValue]:
        """Keep secrets and core connection fields out of engine options."""
        reserved = {
            "database",
            "dbname",
            "conninfo",
            "connection_string",
            "dsn",
            "host",
            "passfile",
            "password",
            "port",
            "sslpassword",
            "user",
            "username",
            "uri",
        }
        invalid = reserved.intersection(key.lower() for key in options)
        if invalid:
            names = ", ".join(sorted(invalid))
            raise ValueError(f"options contiene campos reservados: {names}")
        return options

    @model_validator(mode="after")
    def require_readonly_for_enabled_connection(self) -> Self:
        """Reject enabled write-capable declarations at the configuration boundary."""
        if self.enabled and not self.readonly:
            raise ValueError("una conexión habilitada debe declarar readonly=true")
        return self


class ConnectionsConfig(BaseModel):
    """Root YAML model with duplicate ID validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connections: tuple[ConnectionConfig, ...]
    catalog: CatalogConfig = Field(default_factory=CatalogConfig)
    query: QueryPolicyConfig = Field(default_factory=QueryPolicyConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)

    @field_validator("connections")
    @classmethod
    def reject_duplicate_ids(
        cls,
        connections: tuple[ConnectionConfig, ...],
    ) -> tuple[ConnectionConfig, ...]:
        """Ensure each connection has one stable identifier."""
        ids = [connection.id for connection in connections]
        duplicates = sorted(
            {connection_id for connection_id in ids if ids.count(connection_id) > 1}
        )
        if duplicates:
            raise ValueError(f"IDs de conexión duplicados: {', '.join(duplicates)}")
        return connections


class ConnectionSummary(BaseModel):
    """Public connection representation that can never include credentials."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    type: ConnectionType
    database: str
    enabled: bool
    readonly: bool
    capabilities: ConnectionCapabilities | None


class ConnectionTestResult(BaseModel):
    """Normalized result returned by connectivity checks."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    success: bool
    latency_ms: float
    error_code: str | None = None
    message: str


class SchemaInfo(BaseModel):
    """Database schema metadata."""

    model_config = ConfigDict(frozen=True)

    name: str


class TableInfo(BaseModel):
    """Basic table metadata."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, serialize_by_alias=True)

    schema_name: str = Field(alias="schema")
    name: str
    kind: Literal["table", "partitioned_table"]


class ColumnInfo(BaseModel):
    """Column metadata returned by a SQL adapter."""

    model_config = ConfigDict(frozen=True)

    ordinal_position: int
    name: str
    data_type: str
    nullable: bool
    default: str | None
    description: str | None = None


class ForeignKeyInfo(BaseModel):
    """Normalized foreign key metadata, including composite keys."""

    model_config = ConfigDict(frozen=True)

    name: str
    columns: tuple[str, ...]
    referenced_schema: str
    referenced_table: str
    referenced_columns: tuple[str, ...]


class TableDescription(BaseModel):
    """Detailed metadata for one visible table."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, serialize_by_alias=True)

    schema_name: str = Field(alias="schema")
    name: str
    description: str | None = None
    columns: tuple[ColumnInfo, ...]
    primary_key: tuple[str, ...]
    foreign_keys: tuple[ForeignKeyInfo, ...]
