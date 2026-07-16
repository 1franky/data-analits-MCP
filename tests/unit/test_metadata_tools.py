"""Tests for Sprint 4 metadata tools over the in-memory MCP transport."""

from pathlib import Path

import pytest
from fastmcp import Client

import app.tools.metadata as metadata_tools
from app.tools.server import mcp
from tests.catalog_fakes import build_catalog_service


async def test_metadata_tools_return_cached_structured_contracts_over_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _repository, _adapter = build_catalog_service(tmp_path / "catalog.db")
    service.refresh_connection("postgres-demo")
    monkeypatch.setattr(metadata_tools, "get_catalog_service", lambda: service)

    async with Client(mcp) as client:
        schemas = await client.call_tool("list_schemas", {"connection_id": "postgres-demo"})
        tables = await client.call_tool(
            "list_tables",
            {"connection_id": "postgres-demo", "schema": "public"},
        )
        description = await client.call_tool(
            "describe_table",
            {
                "connection_id": "postgres-demo",
                "schema": "public",
                "table": "clientes",
            },
        )
        relationships = await client.call_tool(
            "list_relationships",
            {"connection_id": "postgres-demo", "table": "ventas"},
        )

    assert schemas.data.contract_version == "1.0.0"
    assert schemas.data.connection_id == "postgres-demo"
    assert schemas.data.schemas[0].name == "public"
    assert {table.name for table in tables.data.tables} == {
        "clientes",
        "productos",
        "ventas",
    }
    assert description.data.table.unique_keys[0].name == "clientes_correo_key"
    assert relationships.data.relationships[0].cardinality == "many-to-one"
    assert relationships.data.relationships[0].source_columns == ["cliente_id"]


async def test_mcp_health_tool_is_versioned() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("health_check", {})

    assert result.data.contract_version == "1.0.0"
    assert result.data.status == "ok"
    assert result.data.server_version == "0.6.0"
