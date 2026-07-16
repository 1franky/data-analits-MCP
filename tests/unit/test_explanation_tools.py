"""MCP contract tests for the LLM-assisted object explanation tool."""

import json
from pathlib import Path

import pytest
from fastmcp import Client

import app.tools.explanation as explanation_tools
from app.tools.server import mcp
from tests.generation_fakes import build_explanation_services


async def test_explain_database_object_is_callable_and_structured_over_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explanation, provider, _audit_repository, _adapter, _catalog = build_explanation_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    monkeypatch.setattr(explanation_tools, "get_object_explanation_service", lambda: explanation)
    provider.responses.append(
        json.dumps(
            {
                "purpose": "Calcula el resumen de ventas de un cliente.",
                "facts": ["Recibe p_cliente_id integer"],
                "inferences": [],
                "referenced_tables": ["ventas"],
                "risks": [],
            }
        )
    )

    async with Client(mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        result = await client.call_tool(
            "explain_database_object",
            {
                "connection_id": "postgres-demo",
                "schema": "public",
                "object_type": "procedure",
                "name": "resumen_ventas_cliente",
            },
        )

    assert "explain_database_object" in tools
    assert result.data.outcome == "explained"
    assert result.data.purpose == "Calcula el resumen de ventas de un cliente."
    assert result.data.contract_version == "1.0.0"
