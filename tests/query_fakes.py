"""Deterministic query adapter and service builder shared by Sprint 3 tests."""

from pathlib import Path
from threading import Event

from pydantic import SecretStr

from app.adapters.base import SqlDatabaseAdapter
from app.adapters.factory import AdapterFactory
from app.exceptions import DatabaseOperationError
from app.models.audit import AuditConfig
from app.models.connections import (
    ConnectionCapabilities,
    ConnectionConfig,
    ConnectionsConfig,
    ConnectionTestResult,
    ConnectionType,
    ProcedureInfo,
    QueryLanguage,
    SchemaInfo,
    TableDescription,
    TableInfo,
    TriggerInfo,
)
from app.models.query import (
    AdapterQueryPlan,
    AdapterQueryResult,
    QueryParameter,
    QueryPolicyConfig,
)
from app.repositories import SqliteAuditRepository
from app.services import (
    AuditService,
    ConnectionService,
    QueryExecutionService,
    QueryValidationService,
)
from tests.factories import make_connection_config

QUERY_CAPABILITIES = ConnectionCapabilities(
    query_language=QueryLanguage.SQL,
    execute_read_query=True,
    explain_query=True,
)


class QueryStubAdapter(SqlDatabaseAdapter):
    """Read adapter that records every invocation and can expose a barrier."""

    def __init__(self) -> None:
        self.execute_calls = 0
        self.explain_calls = 0
        self.last_sql: str | None = None
        self.last_parameters: dict[str, QueryParameter] | None = None
        self.last_max_rows: int | None = None
        self.last_timeout_seconds: int | None = None
        self.fail = False
        self.started_event: Event | None = None
        self.release_event: Event | None = None

    @property
    def capabilities(self) -> ConnectionCapabilities:
        return QUERY_CAPABILITIES

    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            connection_id="postgres-demo",
            success=True,
            latency_ms=1.0,
            message="ok",
        )

    def list_schemas(self) -> tuple[SchemaInfo, ...]:
        return ()

    def list_tables(self, schema: str | None = None) -> tuple[TableInfo, ...]:
        return ()

    def describe_table(self, schema: str, table: str) -> TableDescription:
        return TableDescription(
            schema=schema,
            name=table,
            columns=(),
            primary_key=(),
            foreign_keys=(),
        )

    def list_procedures(self, schema: str | None = None) -> tuple[ProcedureInfo, ...]:
        return ()

    def list_triggers(
        self,
        schema: str | None = None,
        table: str | None = None,
    ) -> tuple[TriggerInfo, ...]:
        return ()

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
        self.last_parameters = parameters
        self.last_max_rows = max_rows
        self.last_timeout_seconds = timeout_seconds
        if self.started_event is not None:
            self.started_event.set()
        if self.release_event is not None:
            self.release_event.wait(timeout=5)
        if self.fail:
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="No fue posible ejecutar la consulta.",
            )
        return AdapterQueryResult(
            columns=("id", "nombre"),
            rows=((1, "Laptop"), (2, "Mouse")),
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
        self.last_parameters = parameters
        self.last_timeout_seconds = timeout_seconds
        if self.fail:
            raise DatabaseOperationError(
                code="DATABASE_EXPLAIN_ERROR",
                message="No fue posible generar el plan.",
            )
        return AdapterQueryPlan(
            plan=[{"Plan": {"Node Type": "Seq Scan", "Relation Name": "productos"}}],
            duration_ms=1.5,
        )


def build_query_services(
    audit_path: Path,
    *,
    adapter: QueryStubAdapter | None = None,
    connection: ConnectionConfig | None = None,
    policy: QueryPolicyConfig | None = None,
) -> tuple[
    ConnectionService,
    QueryValidationService,
    QueryExecutionService,
    SqliteAuditRepository,
    QueryStubAdapter,
]:
    """Compose real services and SQLite audit around a deterministic adapter."""
    selected_adapter = adapter or QueryStubAdapter()
    factory = AdapterFactory()

    def builder(_config: ConnectionConfig, _password: SecretStr) -> SqlDatabaseAdapter:
        return selected_adapter

    factory.register(ConnectionType.POSTGRES, builder, QUERY_CAPABILITIES)
    connections = ConnectionService(
        config=ConnectionsConfig(connections=(connection or make_connection_config(),)),
        adapter_factory=factory,
        environment={"POSTGRES_DEMO_PASSWORD": "unit-test-secret"},
    )
    repository = SqliteAuditRepository(audit_path)
    repository.initialize()
    audit = AuditService(repository, AuditConfig())
    validator = QueryValidationService()
    execution = QueryExecutionService(
        connections=connections,
        validator=validator,
        audit=audit,
        policy=policy or QueryPolicyConfig(),
    )
    return connections, validator, execution, repository, selected_adapter
