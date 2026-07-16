"""Integration tests against the disposable Docker PostgreSQL laboratory."""

import os

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege, ReadOnlySqlTransaction
from pydantic import SecretStr

from app.adapters.postgres import PostgresAdapter
from tests.factories import make_connection_config

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
        reason="set RUN_POSTGRES_INTEGRATION=1 with the PostgreSQL lab running",
    ),
]


def build_adapter() -> PostgresAdapter:
    """Create the adapter using only the lab secret supplied by the environment."""
    password = os.environ["POSTGRES_DEMO_PASSWORD"]
    return PostgresAdapter(make_connection_config(), SecretStr(password))


def test_postgres_connection_and_metadata_contract() -> None:
    adapter = build_adapter()

    connection_result = adapter.test_connection()
    schemas = adapter.list_schemas()
    tables = adapter.list_tables("public")
    clientes = adapter.describe_table("public", "clientes")
    ventas = adapter.describe_table("public", "ventas")

    assert connection_result.success is True
    assert connection_result.error_code is None
    assert "public" in {schema.name for schema in schemas}
    assert {table.name for table in tables} == {"clientes", "productos", "ventas"}
    assert tuple(column.name for column in ventas.columns) == (
        "id",
        "cliente_id",
        "producto_id",
        "cantidad",
        "fecha",
    )
    assert ventas.primary_key == ("id",)
    assert ventas.kind == "table"
    assert clientes.unique_keys[0].name == "clientes_correo_key"
    assert clientes.unique_keys[0].columns == ("correo",)
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


def test_postgres_lists_demo_procedures_and_triggers() -> None:
    adapter = build_adapter()

    procedures = adapter.list_procedures("public")
    triggers = adapter.list_triggers("public", "ventas")

    procedure_names = {procedure.name for procedure in procedures}
    assert {"actualizar_stock_producto", "resumen_ventas_cliente"} <= procedure_names
    summary = next(p for p in procedures if p.name == "resumen_ventas_cliente")
    assert "p_cliente_id" in summary.arguments
    assert summary.kind == "function"
    assert "resumen_ventas_cliente" in summary.definition

    trigger = next(t for t in triggers if t.name == "trg_ventas_actualiza_stock")
    assert trigger.table == "ventas"
    assert trigger.timing == "AFTER"
    assert trigger.events == ("INSERT",)
    assert trigger.function_name == "actualizar_stock_producto"
    assert "CREATE TRIGGER" in trigger.definition


def test_postgres_lab_role_cannot_write() -> None:
    password = os.environ["POSTGRES_DEMO_PASSWORD"]

    with (
        pytest.raises((ReadOnlySqlTransaction, InsufficientPrivilege)),
        psycopg.connect(
            host="postgres-lab",
            port=5432,
            dbname="demo",
            user="mcp_readonly",
            password=password,
            connect_timeout=10,
        ) as connection,
    ):
        connection.execute(
            "INSERT INTO public.productos (nombre, precio, stock) VALUES (%s, %s, %s)",
            ("blocked", 1, 1),
        )
