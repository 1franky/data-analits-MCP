"""Exercise the public Sprint 4-10 MCP contract through Streamable HTTP."""

import argparse
import asyncio
import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from typing import Any

import httpx
from fastmcp import Client

EXPECTED_TOOLS = {
    "delete_indexed_document",
    "describe_table",
    "execute_mongo_aggregate",
    "execute_mongo_find",
    "execute_read_query",
    "explain_database_object",
    "explain_query",
    "generate_and_execute_query",
    "generate_report",
    "generate_sql",
    "get_connection_capabilities",
    "get_schema_cache_status",
    "health_check",
    "hello_world",
    "list_connections",
    "list_indexed_documents",
    "list_mongo_collections",
    "list_procedures",
    "list_relationships",
    "list_schemas",
    "list_tables",
    "list_triggers",
    "refresh_document_index",
    "refresh_schema_cache",
    "search_documents",
    "search_catalog",
    "test_connection",
    "validate_mongo_query",
    "validate_sql",
}


def parse_args() -> argparse.Namespace:
    """Parse a target URL and configured connection identifier."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--connection-id", default="postgres-demo")
    parser.add_argument("--mariadb-connection-id", default="mariadb-demo")
    parser.add_argument("--mongo-connection-id", default="mongodb-demo")
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


async def check_rest_endpoints(base_url: str) -> dict[str, Any]:
    """Confirm GET /ready and GET /metrics respond over plain HTTP, outside the MCP transport."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as http_client:
        ready_response = await http_client.get("/ready")
        if ready_response.status_code != 200:
            raise RuntimeError(f"/ready respondió {ready_response.status_code}, se esperaba 200")
        ready_payload = ready_response.json()
        if ready_payload.get("status") != "ready":
            raise RuntimeError(f"/ready reportó estado inesperado: {ready_payload}")

        metrics_response = await http_client.get("/metrics")
        if metrics_response.status_code != 200:
            raise RuntimeError(f"/metrics respondió {metrics_response.status_code}, esperado 200")
        if "data_platform_query_requests_total" not in metrics_response.text:
            raise RuntimeError("/metrics no expuso data_platform_query_requests_total")

    content_type = metrics_response.headers.get("content-type")
    return {"ready": ready_payload, "metrics_content_type": content_type}


async def smoke(
    url: str,
    connection_id: str,
    mariadb_connection_id: str,
    mongo_connection_id: str,
) -> dict[str, Any]:
    """Call discovery, refresh and exploration tools through the network transport."""
    base_url = url.removesuffix("/mcp")
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
        mariadb_tables = await client.call_tool(
            "list_tables",
            {"connection_id": mariadb_connection_id, "schema": "demo"},
        )
        mariadb_query = await client.call_tool(
            "execute_read_query",
            {"connection_id": mariadb_connection_id, "sql": "SELECT * FROM ventas LIMIT 5"},
        )
        mongo_collections = await client.call_tool(
            "list_mongo_collections",
            {"connection_id": mongo_connection_id},
        )
        mongo_find = await client.call_tool(
            "execute_mongo_find",
            {"connection_id": mongo_connection_id, "collection": "ventas", "filter": {}},
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
        if not any(table.name == "ventas" for table in mariadb_tables.data.tables):
            raise RuntimeError("list_tables no devolvió demo.ventas en MariaDB")
        if not mariadb_query.data.rows:
            raise RuntimeError("execute_read_query no devolvió filas de MariaDB")
        mongo_collections_seen = mongo_collections.data.collections
        mongo_collection_names = {collection.name for collection in mongo_collections_seen}
        if "ventas" not in mongo_collection_names:
            raise RuntimeError("list_mongo_collections no devolvió la colección ventas")
        if not mongo_find.data.documents:
            raise RuntimeError("execute_mongo_find no devolvió documentos de MongoDB")

    rest_endpoints = await check_rest_endpoints(base_url)

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
        "mariadb_tables": json_value(mariadb_tables.data),
        "mariadb_query": json_value(mariadb_query.data),
        "mongo_collections": json_value(mongo_collections.data),
        "mongo_find": json_value(mongo_find.data),
        "rest_endpoints": rest_endpoints,
    }


def main() -> None:
    """Run the asynchronous smoke test and print one reviewable JSON document."""
    args = parse_args()
    result = asyncio.run(
        smoke(
            args.url,
            args.connection_id,
            args.mariadb_connection_id,
            args.mongo_connection_id,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
