"""Integration tests against the disposable Docker MariaDB laboratory."""

import os

import pymysql
import pytest
from pydantic import SecretStr

from app.adapters.mariadb import MariaDbAdapter
from tests.factories import make_connection_config

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_MARIADB_INTEGRATION") != "1",
        reason="set RUN_MARIADB_INTEGRATION=1 with the MariaDB lab running",
    ),
]


def build_adapter() -> MariaDbAdapter:
    """Create the adapter using only the lab secret supplied by the environment."""
    password = os.environ["MARIADB_DEMO_PASSWORD"]
    config = make_connection_config(
        id="mariadb-demo",
        name="MariaDB Demo",
        type="mariadb",
        host="mariadb-lab",
        port=3306,
        database="demo",
        username="mcp_readonly",
        password_env="MARIADB_DEMO_PASSWORD",
        options={"charset": "utf8mb4"},
    )
    return MariaDbAdapter(config, SecretStr(password))


def test_mariadb_connection_and_metadata_contract() -> None:
    adapter = build_adapter()

    connection_result = adapter.test_connection()
    schemas = adapter.list_schemas()
    tables = adapter.list_tables("demo")
    ventas = adapter.describe_table("demo", "ventas")

    assert connection_result.success is True
    assert connection_result.error_code is None
    assert "demo" in {schema.name for schema in schemas}
    assert {table.name for table in tables} == {"clientes", "productos", "ventas"}
    assert tuple(column.name for column in ventas.columns) == (
        "id",
        "cliente_id",
        "producto_id",
        "cantidad",
        "fecha",
    )
    assert ventas.primary_key == ("id",)
    assert ventas.description == "Ventas realizadas a clientes de productos del catálogo."
    assert ventas.columns[1].description == "Cliente que realizó la compra."
    assert {
        (
            foreign_key.columns,
            foreign_key.referenced_table,
            foreign_key.referenced_columns,
        )
        for foreign_key in ventas.foreign_keys
    } == {
        (("cliente_id",), "clientes", ("id",)),
        (("producto_id",), "productos", ("id",)),
    }


def test_mariadb_lists_demo_procedures_and_triggers() -> None:
    adapter = build_adapter()

    procedures = adapter.list_procedures("demo")
    triggers = adapter.list_triggers("demo", "ventas")

    procedure_names = {procedure.name for procedure in procedures}
    assert "resumen_ventas_cliente" in procedure_names
    summary = next(p for p in procedures if p.name == "resumen_ventas_cliente")
    assert "p_cliente_id" in summary.arguments
    assert summary.kind == "procedure"
    assert "resumen_ventas_cliente" in summary.definition

    trigger = next(t for t in triggers if t.name == "trg_ventas_actualiza_stock")
    assert trigger.table == "ventas"
    assert trigger.timing == "AFTER"
    assert trigger.events == ("INSERT",)
    assert "TRIGGER" in trigger.definition.upper()


def test_mariadb_execute_read_query_runs_real_select() -> None:
    adapter = build_adapter()

    result = adapter.execute_read_query(
        "SELECT id, nombre FROM clientes WHERE id = :minimum_id",
        {"minimum_id": 1},
        max_rows=10,
        timeout_seconds=10,
        max_serialized_bytes=1_000_000,
    )

    assert result.columns == ("id", "nombre")
    assert result.rows == ((1, "Juan Pérez"),)


def test_mariadb_lab_role_cannot_write() -> None:
    password = os.environ["MARIADB_DEMO_PASSWORD"]

    with pytest.raises(pymysql.err.OperationalError) as error_info:
        connection = pymysql.connect(
            host="mariadb-lab",
            port=3306,
            database="demo",
            user="mcp_readonly",
            password=password,
            connect_timeout=10,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO productos (nombre, precio, stock) VALUES (%s, %s, %s)",
                    ("blocked", 1, 1),
                )
            connection.commit()
        finally:
            connection.close()

    assert error_info.value.args[0] == 1142
