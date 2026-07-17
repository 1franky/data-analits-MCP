"""Contract tests for the stable Sprint 4 MCP surface."""

from fastmcp import Client

from app.models.contracts import MCP_CONTRACT_VERSION
from app.tools.server import mcp

EXPECTED_TOOLS = {
    "delete_indexed_document",
    "describe_table",
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
    "list_procedures",
    "list_relationships",
    "list_schemas",
    "list_tables",
    "list_triggers",
    "refresh_document_index",
    "refresh_schema_cache",
    "search_catalog",
    "search_documents",
    "test_connection",
    "validate_sql",
}

VERSIONED_TOOLS = {
    "describe_table": {"connection_id", "table", "cache_status"},
    "explain_database_object": {"connection_id", "schema", "object_type", "name", "outcome"},
    "generate_and_execute_query": {"connection_id", "question", "outcome"},
    "generate_report": {"connection_id", "question", "format", "outcome", "generated_at"},
    "generate_sql": {"connection_id", "question", "outcome"},
    "get_connection_capabilities": {"connection_id", "connection"},
    "health_check": {"status", "service", "server_version"},
    "list_procedures": {"connection_id", "schema_filter", "procedures", "cache_status"},
    "list_relationships": {
        "connection_id",
        "schema_filter",
        "table_filter",
        "relationships",
        "cache_status",
    },
    "list_schemas": {"connection_id", "schemas", "cache_status"},
    "list_tables": {"connection_id", "schema_filter", "tables", "cache_status"},
    "list_triggers": {
        "connection_id",
        "schema_filter",
        "table_filter",
        "triggers",
        "cache_status",
    },
    "search_documents": {
        "query",
        "connection_id",
        "domain",
        "matches",
        "mixed_connections_warning",
    },
    "list_indexed_documents": {"documents", "total"},
    "refresh_document_index": {"started_at", "completed_at", "entries", "indexed_count"},
    "delete_indexed_document": {"document_id", "deleted"},
}


async def test_public_tool_catalog_and_versioned_output_schemas_are_stable() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    tools_by_name = {tool.name: tool for tool in tools}
    assert set(tools_by_name) == EXPECTED_TOOLS

    for name, expected_fields in VERSIONED_TOOLS.items():
        output_schema = tools_by_name[name].outputSchema
        assert output_schema is not None
        properties = output_schema["properties"]
        assert properties["contract_version"]["const"] == MCP_CONTRACT_VERSION
        assert expected_fields.issubset(properties)


async def test_metadata_input_schemas_identify_connection_and_filters() -> None:
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert tools["list_schemas"].inputSchema["required"] == ["connection_id"]
    assert set(tools["describe_table"].inputSchema["required"]) == {
        "connection_id",
        "schema",
        "table",
    }
    relationship_properties = tools["list_relationships"].inputSchema["properties"]
    assert set(relationship_properties) == {"connection_id", "schema", "table"}
