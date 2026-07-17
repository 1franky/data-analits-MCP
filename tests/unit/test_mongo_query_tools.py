"""MCP contract tests for MongoDB collection listing and bounded read tools."""

from pathlib import Path

import pytest
from fastmcp import Client

import app.tools.mongo_query as mongo_query_tools
from app.models.audit import AuditConfig
from app.services import AuditService
from app.tools.server import mcp
from tests.document_query_fakes import build_document_query_services


async def test_mongo_tools_are_callable_and_structured_over_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connections, validator, execution, repository, adapter = build_document_query_services(
        tmp_path / "audit.db"
    )
    audit = AuditService(repository, AuditConfig())
    monkeypatch.setattr(mongo_query_tools, "get_connection_service", lambda: connections)
    monkeypatch.setattr(
        mongo_query_tools, "get_document_query_validation_service", lambda: validator
    )
    monkeypatch.setattr(
        mongo_query_tools, "get_document_query_execution_service", lambda: execution
    )
    monkeypatch.setattr(mongo_query_tools, "get_audit_service", lambda: audit)

    async with Client(mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        collections = await client.call_tool(
            "list_mongo_collections", {"connection_id": "mongodb-demo"}
        )
        validated = await client.call_tool(
            "validate_mongo_query",
            {
                "connection_id": "mongodb-demo",
                "collection": "clientes",
                "operation": "find",
                "filter": {"nombre": "Ana"},
            },
        )
        blocked = await client.call_tool(
            "validate_mongo_query",
            {
                "connection_id": "mongodb-demo",
                "collection": "ventas",
                "operation": "aggregate",
                "pipeline": [{"$out": "otra"}],
            },
        )
        found = await client.call_tool(
            "execute_mongo_find",
            {
                "connection_id": "mongodb-demo",
                "collection": "clientes",
                "filter": {"nombre": "Ana"},
            },
        )
        aggregated = await client.call_tool(
            "execute_mongo_aggregate",
            {
                "connection_id": "mongodb-demo",
                "collection": "ventas",
                "pipeline": [{"$match": {"cliente_id": 1}}],
            },
        )

    assert {
        "list_mongo_collections",
        "validate_mongo_query",
        "execute_mongo_find",
        "execute_mongo_aggregate",
    }.issubset(tools)
    assert {item.name for item in collections.data.collections} == {"clientes", "ventas"}
    assert validated.data.executable is True
    assert blocked.data.executable is False
    assert found.data.executed is True
    assert found.data.contract_version == "1.0.0"
    assert aggregated.data.executed is True
    assert adapter.find_calls == 1
    assert adapter.aggregate_calls == 1
