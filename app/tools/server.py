"""FastMCP server and tool registry."""

from fastmcp import FastMCP

from app.tools.catalog import (
    get_schema_cache_status,
    refresh_schema_cache,
    search_catalog,
)
from app.tools.connections import list_connections, test_connection
from app.tools.hello import hello_world
from app.tools.query import execute_read_query, explain_query, validate_sql

mcp = FastMCP(
    name="Data Platform MCP",
    instructions=(
        "Herramientas seguras para explorar plataformas de datos. "
        "Sprint 3 permite validar SQL, ejecutar exclusivamente SELECT acotados y "
        "obtener EXPLAIN sin ANALYZE. DML y DDL nunca se ejecutan."
    ),
)
mcp.tool(name="hello_world")(hello_world)
mcp.tool(name="list_connections")(list_connections)
mcp.tool(name="test_connection")(test_connection)
mcp.tool(name="refresh_schema_cache")(refresh_schema_cache)
mcp.tool(name="get_schema_cache_status")(get_schema_cache_status)
mcp.tool(name="search_catalog")(search_catalog)
mcp.tool(name="validate_sql")(validate_sql)
mcp.tool(name="execute_read_query")(execute_read_query)
mcp.tool(name="explain_query")(explain_query)
