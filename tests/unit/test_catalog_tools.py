"""Tests for catalog MCP tools and their structured contracts."""

from pathlib import Path

import pytest
from fastmcp import Client

import app.tools.catalog as catalog_tools
from app.tools.server import mcp
from tests.catalog_fakes import build_catalog_service


async def test_catalog_tools_are_callable_over_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _repository, _adapter = build_catalog_service(tmp_path / "catalog.db")
    monkeypatch.setattr(catalog_tools, "get_catalog_service", lambda: service)

    async with Client(mcp) as client:
        tools = await client.list_tools()
        refreshed = await client.call_tool(
            "refresh_schema_cache",
            {"connection_id": "postgres-demo"},
        )
        searched = await client.call_tool(
            "search_catalog",
            {"query": "correo", "connection_id": "postgres-demo"},
        )
        status = await client.call_tool(
            "get_schema_cache_status",
            {"connection_id": "postgres-demo"},
        )

    assert {
        "refresh_schema_cache",
        "search_catalog",
        "get_schema_cache_status",
    }.issubset({tool.name for tool in tools})
    assert refreshed.data[0].outcome == "success"
    assert searched.data.matches[0].table == "clientes"
    assert searched.data.cache_statuses[0].stale is False
    assert status.data[0].state == "success"
