"""Deterministic document adapter and service builder shared by Sprint 9 tests."""

from pathlib import Path
from threading import Event

from pydantic import JsonValue, SecretStr

from app.adapters.base import DocumentDatabaseAdapter
from app.adapters.document_factory import DocumentAdapterFactory
from app.adapters.factory import AdapterFactory
from app.exceptions import DatabaseOperationError
from app.models.audit import AuditConfig
from app.models.connections import (
    CollectionInfo,
    ConnectionCapabilities,
    ConnectionConfig,
    ConnectionsConfig,
    ConnectionTestResult,
    ConnectionType,
    QueryLanguage,
)
from app.models.document_query import AdapterDocumentResult
from app.models.query import QueryPolicyConfig
from app.repositories import SqliteAuditRepository
from app.services import (
    AuditService,
    ConnectionService,
    DocumentQueryExecutionService,
    DocumentQueryValidationService,
)
from tests.factories import make_connection_config

DOCUMENT_CAPABILITIES = ConnectionCapabilities(
    query_language=QueryLanguage.DOCUMENT,
    test_connection=True,
    list_collections=True,
    execute_find=True,
    execute_aggregation=True,
)


def make_mongo_connection_config(**overrides: object) -> ConnectionConfig:
    """Build a valid secret-free MongoDB declaration."""
    values: dict[str, object] = {
        "id": "mongodb-demo",
        "name": "MongoDB Demo",
        "type": "mongodb",
        "host": "mongo-lab",
        "port": 27017,
        "database": "demo",
        "username": "mcp_readonly",
        "password_env": "MONGO_DEMO_PASSWORD",
        "readonly": True,
        "enabled": True,
        "connect_timeout_seconds": 10,
        "query_timeout_seconds": 30,
        "max_rows": 500,
        "options": {},
    }
    values.update(overrides)
    return make_connection_config(**values)


class DocumentQueryStubAdapter(DocumentDatabaseAdapter):
    """Document adapter that records every invocation and can be forced to fail."""

    def __init__(self) -> None:
        self.find_calls = 0
        self.aggregate_calls = 0
        self.last_collection: str | None = None
        self.last_filter: dict[str, JsonValue] | None = None
        self.last_pipeline: list[dict[str, JsonValue]] | None = None
        self.fail = False
        self.started_event: Event | None = None
        self.release_event: Event | None = None

    @property
    def capabilities(self) -> ConnectionCapabilities:
        return DOCUMENT_CAPABILITIES

    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            connection_id="mongodb-demo",
            success=True,
            latency_ms=1.0,
            message="ok",
        )

    def list_collections(self) -> tuple[CollectionInfo, ...]:
        return (CollectionInfo(name="clientes"), CollectionInfo(name="ventas"))

    def execute_find(
        self,
        collection: str,
        filter: dict[str, JsonValue],
        projection: dict[str, JsonValue] | None,
        max_rows: int,
        timeout_seconds: int,
        max_serialized_bytes: int,
    ) -> AdapterDocumentResult:
        self.find_calls += 1
        self.last_collection = collection
        self.last_filter = filter
        if self.started_event is not None:
            self.started_event.set()
        if self.release_event is not None:
            self.release_event.wait(timeout=5)
        if self.fail:
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="No fue posible ejecutar la consulta find().",
            )
        return AdapterDocumentResult(
            documents=({"_id": 1, "nombre": "Ana"},),
            duration_ms=2.0,
            truncated=False,
            serialized_bytes=32,
        )

    def execute_aggregation(
        self,
        collection: str,
        pipeline: list[dict[str, JsonValue]],
        max_rows: int,
        timeout_seconds: int,
        max_serialized_bytes: int,
    ) -> AdapterDocumentResult:
        self.aggregate_calls += 1
        self.last_collection = collection
        self.last_pipeline = pipeline
        if self.started_event is not None:
            self.started_event.set()
        if self.release_event is not None:
            self.release_event.wait(timeout=5)
        if self.fail:
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="No fue posible ejecutar la agregación.",
            )
        return AdapterDocumentResult(
            documents=({"_id": 1, "total": 250},),
            duration_ms=3.0,
            truncated=False,
            serialized_bytes=24,
        )


def build_document_query_services(
    audit_path: Path,
    *,
    adapter: DocumentQueryStubAdapter | None = None,
    connection: ConnectionConfig | None = None,
    policy: QueryPolicyConfig | None = None,
) -> tuple[
    ConnectionService,
    DocumentQueryValidationService,
    DocumentQueryExecutionService,
    SqliteAuditRepository,
    DocumentQueryStubAdapter,
]:
    """Compose real services and SQLite audit around a deterministic document adapter."""
    selected_adapter = adapter or DocumentQueryStubAdapter()
    document_factory = DocumentAdapterFactory()

    def builder(_config: ConnectionConfig, _password: SecretStr) -> DocumentDatabaseAdapter:
        return selected_adapter

    document_factory.register(ConnectionType.MONGODB, builder, DOCUMENT_CAPABILITIES)
    connections = ConnectionService(
        config=ConnectionsConfig(connections=(connection or make_mongo_connection_config(),)),
        adapter_factory=AdapterFactory(),
        document_adapter_factory=document_factory,
        environment={"MONGO_DEMO_PASSWORD": "unit-test-secret"},
    )
    repository = SqliteAuditRepository(audit_path)
    repository.initialize()
    audit = AuditService(repository, AuditConfig())
    validator = DocumentQueryValidationService()
    execution = DocumentQueryExecutionService(
        connections=connections,
        validator=validator,
        audit=audit,
        policy=policy or QueryPolicyConfig(),
    )
    return connections, validator, execution, repository, selected_adapter
