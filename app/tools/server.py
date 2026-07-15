"""FastMCP server and tool registry."""

from fastmcp import FastMCP

from app import __version__
from app.tools.administration import health_check
from app.tools.catalog import (
    get_schema_cache_status,
    refresh_schema_cache,
    search_catalog,
)
from app.tools.connections import (
    get_connection_capabilities,
    list_connections,
    test_connection,
)
from app.tools.hello import hello_world
from app.tools.metadata import describe_table, list_relationships, list_schemas, list_tables
from app.tools.query import execute_read_query, explain_query, validate_sql

mcp = FastMCP(
    name="Data Platform MCP",
    version=__version__,
    strict_input_validation=True,
    instructions=(
        "Herramientas seguras para explorar plataformas de datos. "
        "Sprint 4 expone contratos versionados para conexiones, schemas, tablas, "
        "relaciones y consultas SELECT seguras. DML y DDL nunca se ejecutan."
    ),
)
mcp.tool(name="hello_world")(hello_world)
mcp.tool(name="health_check")(health_check)
mcp.tool(name="list_connections")(list_connections)
mcp.tool(name="get_connection_capabilities")(get_connection_capabilities)
mcp.tool(name="test_connection")(test_connection)
mcp.tool(name="refresh_schema_cache")(refresh_schema_cache)
mcp.tool(name="get_schema_cache_status")(get_schema_cache_status)
mcp.tool(name="search_catalog")(search_catalog)
mcp.tool(name="list_schemas")(list_schemas)
mcp.tool(name="list_tables")(list_tables)
mcp.tool(name="describe_table")(describe_table)
mcp.tool(name="list_relationships")(list_relationships)
mcp.tool(name="validate_sql")(validate_sql)
mcp.tool(name="execute_read_query")(execute_read_query)
mcp.tool(name="explain_query")(explain_query)


def main() -> None:
    """Run the same server over the local STDIO transport."""
    mcp.run()


if __name__ == "__main__":
    main()
