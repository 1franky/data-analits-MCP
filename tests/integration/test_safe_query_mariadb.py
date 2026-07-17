"""Sprint 9 end-to-end security and read-query tests against MariaDB."""

import os
from pathlib import Path

import pytest

from app.adapters.registry import create_adapter_factory
from app.exceptions import DatabaseOperationError
from app.models.audit import AuditConfig
from app.models.connections import ConnectionsConfig
from app.models.query import QueryPolicyConfig
from app.repositories import SqliteAuditRepository
from app.services import (
    AuditService,
    ConnectionService,
    QueryExecutionService,
    QueryValidationService,
)
from tests.factories import make_connection_config

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_MARIADB_INTEGRATION") != "1",
        reason="set RUN_MARIADB_INTEGRATION=1 with the MariaDB lab running",
    ),
]

_CONNECTION_ID = "mariadb-demo"


def build_service(
    tmp_path: Path,
    policy: QueryPolicyConfig | None = None,
) -> tuple[QueryExecutionService, SqliteAuditRepository, ConnectionService]:
    """Build production query components against the Docker MariaDB lab."""
    config = make_connection_config(
        id=_CONNECTION_ID,
        name="MariaDB Demo",
        type="mariadb",
        host="mariadb-lab",
        port=3306,
        database="demo",
        username="mcp_readonly",
        password_env="MARIADB_DEMO_PASSWORD",
        options={"charset": "utf8mb4"},
    )
    connections = ConnectionService(
        config=ConnectionsConfig(connections=(config,)),
        adapter_factory=create_adapter_factory(),
        environment={"MARIADB_DEMO_PASSWORD": os.environ["MARIADB_DEMO_PASSWORD"]},
    )
    repository = SqliteAuditRepository(tmp_path / "audit.db")
    repository.initialize()
    service = QueryExecutionService(
        connections=connections,
        validator=QueryValidationService(),
        audit=AuditService(repository, AuditConfig()),
        policy=policy or QueryPolicyConfig(),
    )
    return service, repository, connections


def test_join_parameter_serialization_and_audit(tmp_path: Path) -> None:
    service, repository, _connections = build_service(tmp_path)
    sql = """
        SELECT
            v.id AS venta_id,
            c.nombre AS cliente,
            p.nombre AS producto,
            v.cantidad,
            p.precio AS precio_unitario,
            v.cantidad * p.precio AS total
        FROM ventas AS v
        INNER JOIN clientes AS c ON c.id = v.cliente_id
        INNER JOIN productos AS p ON p.id = v.producto_id
        WHERE v.id >= :minimum_id
        ORDER BY v.id
    """

    result = service.execute(_CONNECTION_ID, sql, parameters={"minimum_id": 1})
    audit = repository.list_records()[0]

    assert result.executed is True
    assert result.row_count == 5
    assert result.columns == (
        "venta_id",
        "cliente",
        "producto",
        "cantidad",
        "precio_unitario",
        "total",
    )
    assert audit.executed is True
    assert audit.row_count == 5
    assert sql not in audit.model_dump_json()


def test_delete_drop_multiple_are_blocked_without_changes(tmp_path: Path) -> None:
    service, repository, _connections = build_service(tmp_path)
    before = service.execute(_CONNECTION_ID, "SELECT COUNT(*) AS total FROM ventas")

    blocked = (
        service.execute(_CONNECTION_ID, "DELETE FROM ventas"),
        service.execute(_CONNECTION_ID, "DROP TABLE ventas"),
        service.execute(_CONNECTION_ID, "SELECT 1; DROP TABLE ventas"),
    )
    after = service.execute(_CONNECTION_ID, "SELECT COUNT(*) AS total FROM ventas")

    assert before.rows == ((5,),)
    assert all(result.executed is False for result in blocked)
    assert after.rows == before.rows
    assert sum(record.blocked for record in repository.list_records()) == 3


def test_explain_uses_json_without_analyze(tmp_path: Path) -> None:
    service, _repository, _connections = build_service(tmp_path)

    result = service.explain(
        _CONNECTION_ID,
        "SELECT * FROM ventas WHERE cliente_id = :cliente_id",
        parameters={"cliente_id": 1},
    )

    assert result.explained is True
    assert result.analyze is False
    assert result.plan is not None


def test_adapter_timeout_is_enforced(tmp_path: Path) -> None:
    _service, _repository, connections = build_service(tmp_path)
    adapter = connections.get_adapter(_CONNECTION_ID)

    with pytest.raises(DatabaseOperationError) as raised:
        adapter.execute_read_query(
            "SELECT SLEEP(2)",
            parameters=None,
            max_rows=1,
            timeout_seconds=1,
            max_serialized_bytes=1_024,
        )

    assert raised.value.code == "QUERY_TIMEOUT"
