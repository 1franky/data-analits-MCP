"""Sprint 3 end-to-end security and read-query tests against PostgreSQL."""

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
        os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
        reason="set RUN_POSTGRES_INTEGRATION=1 with the PostgreSQL lab running",
    ),
]


def build_service(
    tmp_path: Path,
    policy: QueryPolicyConfig | None = None,
) -> tuple[QueryExecutionService, SqliteAuditRepository, ConnectionService]:
    """Build production query components against the Docker PostgreSQL lab."""
    connections = ConnectionService(
        config=ConnectionsConfig(connections=(make_connection_config(),)),
        adapter_factory=create_adapter_factory(),
        environment={"POSTGRES_DEMO_PASSWORD": os.environ["POSTGRES_DEMO_PASSWORD"]},
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
            v.cantidad * p.precio AS total,
            v.fecha
        FROM ventas AS v
        INNER JOIN clientes AS c ON c.id = v.cliente_id
        INNER JOIN productos AS p ON p.id = v.producto_id
        WHERE v.id >= %(minimum_id)s
        ORDER BY v.id
    """

    result = service.execute(
        "postgres-demo",
        sql,
        parameters={"minimum_id": 1},
    )
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
        "fecha",
    )
    assert result.rows[0][4] == "15000.00"
    assert isinstance(result.rows[0][6], str)
    assert audit.executed is True
    assert audit.row_count == 5
    assert sql not in audit.model_dump_json()


@pytest.mark.parametrize(
    ("sql", "expected_column"),
    [
        (
            """
            SELECT p.nombre, SUM(v.cantidad * p.precio) AS total_vendido
            FROM ventas AS v
            JOIN productos AS p ON p.id = v.producto_id
            GROUP BY p.nombre
            ORDER BY total_vendido DESC
            """,
            "total_vendido",
        ),
        (
            """
            WITH gasto AS (
                SELECT c.nombre, SUM(v.cantidad * p.precio) AS total
                FROM ventas AS v
                JOIN clientes AS c ON c.id = v.cliente_id
                JOIN productos AS p ON p.id = v.producto_id
                GROUP BY c.nombre
            )
            SELECT * FROM gasto WHERE total > 1000 ORDER BY total DESC
            """,
            "total",
        ),
        (
            """
            SELECT
                cliente_id,
                id AS venta_id,
                ROW_NUMBER() OVER (
                    PARTITION BY cliente_id ORDER BY cantidad DESC, id
                ) AS posicion
            FROM ventas
            ORDER BY cliente_id, posicion
            """,
            "posicion",
        ),
    ],
)
def test_complex_read_queries_execute(
    tmp_path: Path,
    sql: str,
    expected_column: str,
) -> None:
    service, _repository, _connections = build_service(tmp_path)

    result = service.execute("postgres-demo", sql)

    assert result.executed is True
    assert result.row_count > 0
    assert expected_column in result.columns


def test_row_and_serialized_byte_limits_are_enforced(tmp_path: Path) -> None:
    service, _repository, _connections = build_service(
        tmp_path,
        QueryPolicyConfig(global_max_rows=2, max_serialized_bytes=1_024),
    )

    rows_limited = service.execute("postgres-demo", "SELECT * FROM ventas ORDER BY id")
    bytes_limited = service.execute("postgres-demo", "SELECT repeat('x', 2000) AS payload")

    assert rows_limited.executed is True
    assert rows_limited.row_count == 2
    assert rows_limited.row_limit == 2
    assert rows_limited.truncated is True
    assert bytes_limited.executed is True
    assert bytes_limited.row_count == 0
    assert bytes_limited.truncated is True
    assert bytes_limited.serialized_bytes == 0


def test_delete_drop_multiple_and_write_cte_are_blocked_without_changes(
    tmp_path: Path,
) -> None:
    service, repository, _connections = build_service(tmp_path)
    before = service.execute("postgres-demo", "SELECT COUNT(*) AS total FROM ventas")

    blocked = (
        service.execute("postgres-demo", "DELETE FROM ventas"),
        service.execute("postgres-demo", "DROP TABLE ventas"),
        service.execute("postgres-demo", "SELECT 1; DROP TABLE ventas"),
        service.execute(
            "postgres-demo",
            "WITH borrado AS (DELETE FROM ventas RETURNING *) SELECT * FROM borrado",
        ),
    )
    after = service.execute("postgres-demo", "SELECT COUNT(*) AS total FROM ventas")

    assert before.rows == ((5,),)
    assert all(result.executed is False for result in blocked)
    assert after.rows == before.rows
    assert sum(record.blocked for record in repository.list_records()) == 4


def test_explain_uses_json_without_analyze(tmp_path: Path) -> None:
    service, _repository, _connections = build_service(tmp_path)

    result = service.explain(
        "postgres-demo",
        "SELECT * FROM ventas WHERE cliente_id = %(cliente_id)s",
        parameters={"cliente_id": 1},
    )

    assert result.explained is True
    assert result.analyze is False
    assert result.plan is not None
    assert result.message.endswith("sin ANALYZE.")


def test_adapter_timeout_and_binary_null_serialization(tmp_path: Path) -> None:
    service, _repository, connections = build_service(tmp_path)
    serialized = service.execute(
        "postgres-demo",
        "SELECT decode('DEADBEEF', 'hex') AS payload, NULL AS empty",
    )
    adapter = connections.get_adapter("postgres-demo")

    with pytest.raises(DatabaseOperationError) as raised:
        adapter.execute_read_query(
            "SELECT pg_sleep(2)",
            parameters=None,
            max_rows=1,
            timeout_seconds=1,
            max_serialized_bytes=1_024,
        )

    assert serialized.rows == (("base64:3q2+7w==", None),)
    assert raised.value.code == "QUERY_TIMEOUT"
