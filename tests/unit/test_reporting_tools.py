"""MCP contract tests for natural-language report generation."""

import json
from pathlib import Path

import pytest
from fastmcp import Client

import app.tools.reporting as reporting_tools
from app.tools.server import mcp
from tests.generation_fakes import build_reporting_services


async def test_generate_report_tool_is_callable_and_returns_inline_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporting, provider, _audit_repository, adapter = build_reporting_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    monkeypatch.setattr(reporting_tools, "get_reporting_service", lambda: reporting)
    provider.responses.append(
        json.dumps({"outcome": "generated", "sql": "SELECT id, nombre FROM productos"})
    )

    async with Client(mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        result = await client.call_tool(
            "generate_report",
            {
                "connection_id": "postgres-demo",
                "question": "dame las ventas del mes pasado",
                "format": "csv",
            },
        )

    assert "generate_report" in tools
    assert result.data.contract_version == "1.0.0"
    assert result.data.outcome == "generated"
    assert result.data.payload.format == "csv"
    assert result.data.payload.content_base64
    assert adapter.execute_calls == 1
