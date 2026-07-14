"""Tests for the public MCP connection tool functions."""

import pytest
from fastmcp import Client

import app.tools.connections as connection_tools
from app.adapters.factory import AdapterFactory
from app.models.connections import ConnectionsConfig, ConnectionType
from app.services import ConnectionService
from app.tools.server import mcp
from tests.factories import make_connection_config
from tests.unit.test_adapter_factory import _CAPABILITIES, build_stub_adapter


def build_service() -> ConnectionService:
    """Build the real service with a deterministic in-memory adapter registry."""
    factory = AdapterFactory()
    factory.register(ConnectionType.POSTGRES, build_stub_adapter, _CAPABILITIES)
    return ConnectionService(
        config=ConnectionsConfig(connections=(make_connection_config(),)),
        adapter_factory=factory,
        environment={"POSTGRES_DEMO_PASSWORD": "unit-test-secret"},
    )


def test_list_connections_tool_returns_safe_public_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service()
    monkeypatch.setattr(connection_tools, "get_connection_service", lambda: service)

    result = connection_tools.list_connections()
    serialized = result[0].model_dump(mode="json")

    assert serialized["id"] == "postgres-demo"
    assert serialized["enabled"] is True
    assert "password" not in serialized
    assert "password_env" not in serialized
    assert "host" not in serialized
    assert "unit-test-secret" not in str(serialized)


def test_test_connection_tool_returns_normalized_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service()
    monkeypatch.setattr(connection_tools, "get_connection_service", lambda: service)

    result = connection_tools.test_connection("postgres-demo")

    assert result.connection_id == "postgres-demo"
    assert result.success is True
    assert result.latency_ms == 1.0
    assert result.error_code is None


def test_test_connection_tool_normalizes_unknown_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service()
    monkeypatch.setattr(connection_tools, "get_connection_service", lambda: service)

    result = connection_tools.test_connection("missing")

    assert result.success is False
    assert result.error_code == "CONNECTION_NOT_FOUND"


async def test_connection_tools_are_callable_over_mcp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service()
    monkeypatch.setattr(connection_tools, "get_connection_service", lambda: service)

    async with Client(mcp) as client:
        listed = await client.call_tool("list_connections", {})
        tested = await client.call_tool(
            "test_connection",
            {"connection_id": "postgres-demo"},
        )

    assert listed.data[0].id == "postgres-demo"
    assert "password" not in repr(listed.data[0])
    assert tested.data.success is True
    assert tested.data.connection_id == "postgres-demo"
