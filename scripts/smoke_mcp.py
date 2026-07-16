"""Exercise the public Sprint 4/5 MCP contract through Streamable HTTP."""

import argparse
import asyncio
import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from typing import Any

from fastmcp import Client

EXPECTED_TOOLS = {
    "describe_table",
    "execute_read_query",
    "explain_query",
    "generate_and_execute_query",
    "generate_report",
    "generate_sql",
    "get_connection_capabilities",
    "get_schema_cache_status",
    "health_check",
    "hello_world",
    "list_connections",
    "list_relationships",
    "list_schemas",
    "list_tables",
    "refresh_schema_cache",
    "search_catalog",
    "test_connection",
    "validate_sql",
}


def parse_args() -> argparse.Namespace:
    """Parse a target URL and configured connection identifier."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--connection-id", default="postgres-demo")
    return parser.parse_args()


def json_value(value: Any) -> Any:
    """Convert FastMCP/Pydantic result values into JSON-compatible data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    return value


async def smoke(url: str, connection_id: str) -> dict[str, Any]:
    """Call discovery, refresh and exploration tools through the network transport."""
    async with Client(url) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        missing = EXPECTED_TOOLS.difference(tool_names)
        if missing:
            raise RuntimeError(f"Faltan herramientas MCP: {', '.join(sorted(missing))}")

        health = await client.call_tool("health_check", {})
        connections = await client.call_tool("list_connections", {})
        refresh = await client.call_tool(
            "refresh_schema_cache",
            {"connection_id": connection_id},
        )
        schemas = await client.call_tool("list_schemas", {"connection_id": connection_id})
        tables = await client.call_tool(
            "list_tables",
            {"connection_id": connection_id, "schema": "public"},
        )
        description = await client.call_tool(
            "describe_table",
            {"connection_id": connection_id, "schema": "public", "table": "ventas"},
        )
        relationships = await client.call_tool(
            "list_relationships",
            {"connection_id": connection_id, "table": "ventas"},
        )

        if health.data.contract_version != "1.0.0" or health.data.status != "ok":
            raise RuntimeError("health_check no respeta el contrato MCP 1.0.0")
        if connection_id not in {connection.id for connection in connections.data}:
            raise RuntimeError(f"La conexión '{connection_id}' no aparece en list_connections")
        refresh_outcomes = {item.outcome for item in refresh.data}
        if not refresh_outcomes.intersection({"success", "already_running"}):
            raise RuntimeError(f"El refresh de metadata falló: {sorted(refresh_outcomes)}")
        if schemas.data.connection_id != connection_id:
            raise RuntimeError("list_schemas no identificó la conexión solicitada")
        if description.data.table.name != "ventas":
            raise RuntimeError("describe_table no devolvió public.ventas")
        if not relationships.data.relationships:
            raise RuntimeError("list_relationships no devolvió las FK de public.ventas")

    return {
        "transport": "streamable-http",
        "url": url,
        "tools_count": len(tool_names),
        "health": json_value(health.data),
        "connections": json_value(connections.data),
        "refresh": json_value(refresh.data),
        "schemas": json_value(schemas.data),
        "tables": json_value(tables.data),
        "description": json_value(description.data),
        "relationships": json_value(relationships.data),
    }


def main() -> None:
    """Run the asynchronous smoke test and print one reviewable JSON document."""
    args = parse_args()
    print(
        json.dumps(asyncio.run(smoke(args.url, args.connection_id)), indent=2, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
