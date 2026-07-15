"""FastMCP server and tool registry."""

from fastmcp import FastMCP

from app.tools.catalog import (
    get_schema_cache_status,
    refresh_schema_cache,
    search_catalog,
)
from app.tools.connections import list_connections, test_connection
from app.tools.hello import hello_world

mcp = FastMCP(
    name="Data Platform MCP",
    instructions=(
        "Herramientas seguras para explorar plataformas de datos. "
        "Sprint 2 permite refrescar y buscar un catálogo de metadata PostgreSQL; "
        "todavía no ejecuta consultas de negocio."
    ),
)
mcp.tool(name="hello_world")(hello_world)
mcp.tool(name="list_connections")(list_connections)
mcp.tool(name="test_connection")(test_connection)
mcp.tool(name="refresh_schema_cache")(refresh_schema_cache)
mcp.tool(name="get_schema_cache_status")(get_schema_cache_status)
mcp.tool(name="search_catalog")(search_catalog)
