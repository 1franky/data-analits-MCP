"""Deterministic LLM provider and service builders shared by generation tests."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import SecretStr

from app.adapters.base import SqlDatabaseAdapter
from app.adapters.factory import AdapterFactory
from app.exceptions import DatabaseOperationError, DataPlatformError
from app.generation.provider import LlmProvider
from app.generation.registry import LlmProviderFactory
from app.models.audit import AuditConfig
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
from app.models.generation import (
    GenerationConfig,
    GenerationProviderConfig,
    LlmCompletionRequest,
    LlmCompletionResponse,
    LlmProviderType,
)
from app.models.query import (
    AdapterQueryPlan,
    AdapterQueryResult,
    QueryParameter,
    QueryPolicyConfig,
)
from app.models.reporting import ReportingConfig
from app.reporting.exporters.factory import create_report_exporter_factory
from app.reporting.service import ReportingService
from app.repositories import SqliteAuditRepository, SqliteCatalogRepository
from app.services import (
    AuditService,
    CatalogService,
    ConnectionService,
    GenerationExecutionService,
    GenerationService,
    QueryExecutionService,
    QueryValidationService,
)
from tests.factories import make_connection_config

GENERATION_CAPABILITIES = ConnectionCapabilities(
    query_language=QueryLanguage.SQL,
    list_schemas=True,
    list_tables=True,
    describe_table=True,
    primary_keys=True,
    foreign_keys=True,
    execute_read_query=True,
    explain_query=True,
)

PROVIDER_CONFIG = GenerationProviderConfig(
    type=LlmProviderType.OPENAI_COMPATIBLE,
    base_url="http://llm.invalid/v1",
    api_key_env="LLM_API_KEY",
    model="test-model",
)


class FakeLlmProvider(LlmProvider):
    """Provider returning pre-scripted completions or raising a scripted error."""

    def __init__(self) -> None:
        self.responses: list[str] = []
        self.calls: list[LlmCompletionRequest] = []
        self.error: DataPlatformError | None = None
        self.close_calls = 0

    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResponse:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        content = self.responses.pop(0) if self.responses else "{}"
        return LlmCompletionResponse(content=content, finish_reason="stop", duration_ms=1.0)

    def close(self) -> None:
        self.close_calls += 1


class GenerationStubAdapter(SqlDatabaseAdapter):
    """Metadata plus execution adapter with call tracking, for generation tests."""

    def __init__(self) -> None:
        self.execute_calls = 0
        self.explain_calls = 0
        self.last_sql: str | None = None
        self.fail = False
        self.columns: tuple[str, ...] = ("id", "nombre")
        self.rows: tuple[tuple[QueryParameter, ...], ...] = ((1, "Laptop"), (2, "Mouse"))
        self._tables = self._build_tables()

    @property
    def capabilities(self) -> ConnectionCapabilities:
        return GENERATION_CAPABILITIES

    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            connection_id="postgres-demo",
            success=True,
            latency_ms=1.0,
            message="ok",
        )

    def list_schemas(self) -> tuple[SchemaInfo, ...]:
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
        self.execute_calls += 1
        self.last_sql = sql
        if self.fail:
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="No fue posible ejecutar la consulta.",
            )
        return AdapterQueryResult(
            columns=self.columns,
            rows=self.rows,
            duration_ms=2.5,
            truncated=False,
            serialized_bytes=25,
        )

    def explain_read_query(
        self,
        sql: str,
        parameters: dict[str, QueryParameter] | None,
        timeout_seconds: int,
    ) -> AdapterQueryPlan:
        self.explain_calls += 1
        self.last_sql = sql
        return AdapterQueryPlan(plan=[{"Plan": {"Node Type": "Seq Scan"}}], duration_ms=1.0)

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


def build_generation_services(
    catalog_path: Path,
    audit_path: Path,
    *,
    generation_config: GenerationConfig | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[
    GenerationService,
    GenerationExecutionService,
    FakeLlmProvider,
    SqliteAuditRepository,
    GenerationStubAdapter,
    CatalogService,
]:
    """Compose real generation/execution services around deterministic fakes."""
    adapter = GenerationStubAdapter()
    adapter_factory = AdapterFactory()

    def adapter_builder(_config: ConnectionConfig, _password: SecretStr) -> SqlDatabaseAdapter:
        return adapter

    adapter_factory.register(ConnectionType.POSTGRES, adapter_builder, GENERATION_CAPABILITIES)
    connections = ConnectionService(
        config=ConnectionsConfig(connections=(make_connection_config(),)),
        adapter_factory=adapter_factory,
        environment={"POSTGRES_DEMO_PASSWORD": "unit-test-secret"},
    )

    catalog_repository = SqliteCatalogRepository(catalog_path)
    catalog_repository.initialize()
    catalog = CatalogService(
        connections=connections,
        repository=catalog_repository,
        config=CatalogConfig(),
        clock=clock or (lambda: datetime(2026, 7, 16, 12, 0, tzinfo=UTC)),
    )
    catalog.refresh_connection("postgres-demo")

    audit_repository = SqliteAuditRepository(audit_path)
    audit_repository.initialize()
    audit = AuditService(audit_repository, AuditConfig())

    validator = QueryValidationService()
    execution = QueryExecutionService(
        connections=connections,
        validator=validator,
        audit=audit,
        policy=QueryPolicyConfig(),
    )

    provider = FakeLlmProvider()
    provider_factory = LlmProviderFactory()
    provider_factory.register(
        LlmProviderType.OPENAI_COMPATIBLE,
        lambda _config, _api_key: provider,
    )

    config = generation_config or GenerationConfig(enabled=True, provider=PROVIDER_CONFIG)
    generation = GenerationService(
        connections=connections,
        catalog=catalog,
        provider_factory=provider_factory,
        validator=validator,
        config=config,
        environment={"LLM_API_KEY": "unit-test-llm-key"},
        audit=audit,
        clock=clock or (lambda: datetime(2026, 7, 16, 12, 0, tzinfo=UTC)),
    )
    generation_execution = GenerationExecutionService(generation=generation, execution=execution)

    return generation, generation_execution, provider, audit_repository, adapter, catalog


def build_reporting_services(
    catalog_path: Path,
    audit_path: Path,
    *,
    generation_config: GenerationConfig | None = None,
    reporting_config: ReportingConfig | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[
    ReportingService,
    FakeLlmProvider,
    SqliteAuditRepository,
    GenerationStubAdapter,
]:
    """Compose a real ReportingService around the same deterministic generation fakes."""
    effective_clock = clock or (lambda: datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    _generation, generation_execution, provider, audit_repository, adapter, _catalog = (
        build_generation_services(
            catalog_path,
            audit_path,
            generation_config=generation_config,
            clock=effective_clock,
        )
    )
    audit = AuditService(audit_repository, AuditConfig())
    reporting = ReportingService(
        generation_execution=generation_execution,
        exporter_factory=create_report_exporter_factory(),
        config=reporting_config or ReportingConfig(enabled=True),
        audit=audit,
        clock=effective_clock,
    )
    return reporting, provider, audit_repository, adapter
