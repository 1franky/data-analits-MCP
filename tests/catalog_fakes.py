"""Deterministic catalog adapters and service builders shared by tests."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from pydantic import SecretStr

from app.adapters.base import SqlDatabaseAdapter
from app.adapters.factory import AdapterFactory
from app.exceptions import DatabaseOperationError
from app.models.catalog import CatalogSnapshot
from app.models.connections import (
    CatalogConfig,
    ColumnInfo,
    ConnectionCapabilities,
    ConnectionConfig,
    ConnectionsConfig,
    ConnectionTestResult,
    ConnectionType,
    ForeignKeyInfo,
    QueryLanguage,
    SchemaInfo,
    TableDescription,
    TableInfo,
    UniqueKeyInfo,
)
from app.models.query import AdapterQueryPlan, AdapterQueryResult, QueryParameter
from app.repositories import SqliteCatalogRepository
from app.services import CatalogService, ConnectionService
from tests.factories import make_connection_config

CATALOG_CAPABILITIES = ConnectionCapabilities(
    query_language=QueryLanguage.SQL,
    list_schemas=True,
    list_tables=True,
    describe_table=True,
    primary_keys=True,
    foreign_keys=True,
)


class MutableClock:
    """Clock whose current time can be advanced by a test."""

    def __init__(self, current: datetime | None = None) -> None:
        self.current = current or datetime(2026, 7, 14, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current


class CatalogStubAdapter(SqlDatabaseAdapter):
    """Metadata adapter with optional failure and concurrency barriers."""

    def __init__(self) -> None:
        self.fail = False
        self.refresh_calls = 0
        self.started_event: Event | None = None
        self.release_event: Event | None = None
        self._tables = self._build_tables()

    @property
    def capabilities(self) -> ConnectionCapabilities:
        return CATALOG_CAPABILITIES

    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            connection_id="postgres-demo",
            success=True,
            latency_ms=1.0,
            message="ok",
        )

    def list_schemas(self) -> tuple[SchemaInfo, ...]:
        self.refresh_calls += 1
        if self.started_event is not None:
            self.started_event.set()
        if self.release_event is not None:
            self.release_event.wait(timeout=5)
        if self.fail:
            raise DatabaseOperationError(
                code="DATABASE_METADATA_ERROR",
                message="No fue posible recuperar metadata de PostgreSQL.",
            )
        return (SchemaInfo(name="public"),)

    def list_tables(self, schema: str | None = None) -> tuple[TableInfo, ...]:
        if schema not in {None, "public"}:
            return ()
        return tuple(
            TableInfo(schema=table.schema_name, name=table.name, kind="table")
            for table in self._tables
        )

    def describe_table(self, schema: str, table: str) -> TableDescription:
        return next(
            description
            for description in self._tables
            if description.schema_name == schema and description.name == table
        )

    def execute_read_query(
        self,
        sql: str,
        parameters: dict[str, QueryParameter] | None,
        max_rows: int,
        timeout_seconds: int,
        max_serialized_bytes: int,
    ) -> AdapterQueryResult:
        raise AssertionError("catalog tests must not execute business queries")

    def explain_read_query(
        self,
        sql: str,
        parameters: dict[str, QueryParameter] | None,
        timeout_seconds: int,
    ) -> AdapterQueryPlan:
        raise AssertionError("catalog tests must not explain business queries")

    @staticmethod
    def _build_tables() -> tuple[TableDescription, ...]:
        id_column = ColumnInfo(
            ordinal_position=1,
            name="id",
            data_type="integer",
            nullable=False,
            default=None,
            description="Identificador interno.",
        )
        clientes = TableDescription(
            schema="public",
            name="clientes",
            description="Clientes registrados en la plataforma comercial.",
            columns=(
                id_column,
                ColumnInfo(
                    ordinal_position=2,
                    name="correo",
                    data_type="character varying(150)",
                    nullable=False,
                    default=None,
                    description="Correo electrónico único del cliente.",
                ),
            ),
            primary_key=("id",),
            unique_keys=(UniqueKeyInfo(name="clientes_correo_key", columns=("correo",)),),
            foreign_keys=(),
        )
        productos = TableDescription(
            schema="public",
            name="productos",
            description="Productos disponibles para venta e inventario.",
            columns=(id_column,),
            primary_key=("id",),
            foreign_keys=(),
        )
        ventas = TableDescription(
            schema="public",
            name="ventas",
            description="Ventas realizadas a clientes de productos del catálogo.",
            columns=(
                id_column,
                ColumnInfo(
                    ordinal_position=2,
                    name="cliente_id",
                    data_type="integer",
                    nullable=False,
                    default=None,
                    description="Cliente que realizó la compra.",
                ),
            ),
            primary_key=("id",),
            foreign_keys=(
                ForeignKeyInfo(
                    name="ventas_cliente_id_fkey",
                    columns=("cliente_id",),
                    referenced_schema="public",
                    referenced_table="clientes",
                    referenced_columns=("id",),
                ),
            ),
        )
        return (clientes, productos, ventas)


def build_catalog_service(
    path: Path,
    adapter: CatalogStubAdapter | None = None,
    config: CatalogConfig | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[CatalogService, SqliteCatalogRepository, CatalogStubAdapter]:
    """Build a real service and SQLite repository around the deterministic adapter."""
    selected_adapter = adapter or CatalogStubAdapter()
    factory = AdapterFactory()

    def builder(_config: ConnectionConfig, _password: SecretStr) -> SqlDatabaseAdapter:
        return selected_adapter

    factory.register(ConnectionType.POSTGRES, builder, CATALOG_CAPABILITIES)
    connections = ConnectionService(
        config=ConnectionsConfig(connections=(make_connection_config(),)),
        adapter_factory=factory,
        environment={"POSTGRES_DEMO_PASSWORD": "unit-test-secret"},
    )
    repository = SqliteCatalogRepository(path)
    repository.initialize()
    service = CatalogService(
        connections=connections,
        repository=repository,
        config=config or CatalogConfig(),
        clock=clock,
    )
    return service, repository, selected_adapter


def snapshot_payload(snapshot: CatalogSnapshot) -> str:
    """Return serialized metadata for assertions that business rows are absent."""
    return snapshot.model_dump_json()
