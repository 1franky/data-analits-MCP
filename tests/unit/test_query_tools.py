"""MCP contract tests for SQL validation, execution and explain tools."""

from pathlib import Path

import pytest
from fastmcp import Client

import app.tools.query as query_tools
from app.models.audit import AuditConfig
from app.services import AuditService
from app.tools.server import mcp
from tests.query_fakes import build_query_services


async def test_query_tools_are_callable_and_structured_over_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connections, validator, execution, repository, adapter = build_query_services(
        tmp_path / "audit.db"
    )
    audit = AuditService(repository, AuditConfig())
    monkeypatch.setattr(query_tools, "get_connection_service", lambda: connections)
    monkeypatch.setattr(query_tools, "get_query_validation_service", lambda: validator)
    monkeypatch.setattr(query_tools, "get_query_execution_service", lambda: execution)
    monkeypatch.setattr(query_tools, "get_audit_service", lambda: audit)

    async with Client(mcp) as client:
        tools = await client.list_tools()
        validated = await client.call_tool(
            "validate_sql",
            {"connection_id": "postgres-demo", "sql": "DELETE FROM ventas"},
        )
        executed = await client.call_tool(
            "execute_read_query",
            {
                "connection_id": "postgres-demo",
                "sql": "SELECT * FROM productos WHERE id >= %(minimum)s",
                "parameters": {"minimum": 1},
                "max_rows": 10,
            },
        )
        explained = await client.call_tool(
            "explain_query",
            {"connection_id": "postgres-demo", "sql": "SELECT * FROM productos"},
        )

    assert {"validate_sql", "execute_read_query", "explain_query"}.issubset(
        {tool.name for tool in tools}
    )
    assert validated.data.executable is False
    assert validated.data.statement_type == "DELETE"
    assert executed.data.executed is True
    assert executed.data.rows[0] == [1, "Laptop"]
    assert explained.data.explained is True
    assert explained.data.analyze is False
    assert adapter.execute_calls == 1
    assert adapter.explain_calls == 1
