"""MCP contract tests for LLM-assisted SQL generation tools."""

import json
from pathlib import Path

import pytest
from fastmcp import Client

import app.tools.generation as generation_tools
from app.tools.server import mcp
from tests.generation_fakes import build_generation_services


async def test_generation_tools_are_callable_and_structured_over_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generation, execution, provider, _audit_repository, adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )
    monkeypatch.setattr(generation_tools, "get_generation_service", lambda: generation)
    monkeypatch.setattr(generation_tools, "get_generation_execution_service", lambda: execution)

    provider.responses.append(
        json.dumps({"outcome": "generated", "sql": "SELECT id FROM productos"})
    )
    provider.responses.append(
        json.dumps({"outcome": "generated", "sql": "SELECT id, nombre FROM productos"})
    )

    async with Client(mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        generated = await client.call_tool(
            "generate_sql",
            {"connection_id": "postgres-demo", "question": "dame los ids de productos"},
        )
        executed = await client.call_tool(
            "generate_and_execute_query",
            {"connection_id": "postgres-demo", "question": "dame los productos"},
        )

    assert {"generate_sql", "generate_and_execute_query"}.issubset(tools)
    assert generated.data.outcome == "generated"
    assert generated.data.generated.sql == "SELECT id FROM productos"
    assert generated.data.contract_version == "1.0.0"
    assert executed.data.outcome == "generated"
    assert executed.data.execution.executed is True
    assert executed.data.execution.rows[0] == [1, "Laptop"]
    assert adapter.execute_calls == 1
