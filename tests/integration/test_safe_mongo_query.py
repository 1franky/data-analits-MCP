"""Sprint 9 end-to-end security and read-query tests against MongoDB."""

import os
from pathlib import Path

import pytest

from app.adapters.document_registry import create_document_adapter_factory
from app.adapters.factory import AdapterFactory
from app.models.audit import AuditConfig
from app.models.connections import ConnectionsConfig
from app.models.query import QueryPolicyConfig
from app.repositories import SqliteAuditRepository
from app.services import (
    AuditService,
    ConnectionService,
    DocumentQueryExecutionService,
    DocumentQueryValidationService,
)
from tests.factories import make_connection_config

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_MONGODB_INTEGRATION") != "1",
        reason="set RUN_MONGODB_INTEGRATION=1 with the MongoDB lab running",
    ),
]

_CONNECTION_ID = "mongodb-demo"


def build_service(
    tmp_path: Path,
    policy: QueryPolicyConfig | None = None,
) -> tuple[DocumentQueryExecutionService, SqliteAuditRepository, ConnectionService]:
    """Build production document components against the Docker MongoDB lab."""
    config = make_connection_config(
        id=_CONNECTION_ID,
        name="MongoDB Demo",
        type="mongodb",
        host="mongo-lab",
        port=27017,
        database="demo",
        username="mcp_readonly",
        password_env="MONGO_DEMO_PASSWORD",
        options={"authSource": "demo"},
    )
    connections = ConnectionService(
        config=ConnectionsConfig(connections=(config,)),
        adapter_factory=AdapterFactory(),
        document_adapter_factory=create_document_adapter_factory(),
        environment={"MONGO_DEMO_PASSWORD": os.environ["MONGO_DEMO_PASSWORD"]},
    )
    repository = SqliteAuditRepository(tmp_path / "audit.db")
    repository.initialize()
    service = DocumentQueryExecutionService(
        connections=connections,
        validator=DocumentQueryValidationService(),
        audit=AuditService(repository, AuditConfig()),
        policy=policy or QueryPolicyConfig(),
    )
    return service, repository, connections


def test_valid_find_executes_and_is_audited_without_plain_text(tmp_path: Path) -> None:
    service, repository, _connections = build_service(tmp_path)

    result = service.execute_find(_CONNECTION_ID, "clientes", {"_id": {"$in": [1, 2, 3]}})
    audit = repository.list_records()[0]

    assert result.executed is True
    assert result.document_count == 3
    assert audit.executed is True
    assert "clientes" not in audit.model_dump_json() or audit.statement_type == "find"
    assert "Juan" not in audit.model_dump_json()


def test_out_and_merge_stages_are_blocked_without_reaching_the_adapter(tmp_path: Path) -> None:
    service, repository, connections = build_service(tmp_path)
    adapter = connections.get_document_adapter(_CONNECTION_ID)
    before_collections = {c.name for c in adapter.list_collections()}

    blocked = (
        service.execute_aggregate(_CONNECTION_ID, "ventas", [{"$out": "otra_coleccion"}]),
        service.execute_aggregate(_CONNECTION_ID, "ventas", [{"$merge": "otra_coleccion"}]),
        service.execute_find(_CONNECTION_ID, "ventas", {"$where": "function(){return true;}"}),
    )
    after_collections = {c.name for c in adapter.list_collections()}

    assert all(result.executed is False for result in blocked)
    assert after_collections == before_collections
    assert "otra_coleccion" not in after_collections
    assert sum(1 for record in repository.list_records() if record.blocked) == 3


def test_aggregate_with_lookup_returns_real_documents(tmp_path: Path) -> None:
    service, _repository, _connections = build_service(tmp_path)

    result = service.execute_aggregate(
        _CONNECTION_ID,
        "ventas",
        [
            {"$match": {"cliente_id": 1}},
            {"$group": {"_id": "$cliente_id", "total_ventas": {"$sum": 1}}},
        ],
    )

    assert result.executed is True
    assert result.document_count == 1


def test_adapter_row_limit_bounds_result_size(tmp_path: Path) -> None:
    service, _repository, _connections = build_service(tmp_path)

    result = service.execute_find(_CONNECTION_ID, "ventas", {}, max_rows=2)

    assert result.executed is True
    assert result.document_count <= 2
