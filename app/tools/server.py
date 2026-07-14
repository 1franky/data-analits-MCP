"""FastMCP server and tool registry."""

from fastmcp import FastMCP

from app.tools.connections import list_connections, test_connection
from app.tools.hello import hello_world

mcp = FastMCP(
    name="Data Platform MCP",
    instructions=(
        "Herramientas seguras para explorar plataformas de datos. "
        "Sprint 1 permite descubrir conexiones y probar conectividad PostgreSQL; "
        "todavía no ejecuta consultas de negocio."
    ),
)
mcp.tool(name="hello_world")(hello_world)
mcp.tool(name="list_connections")(list_connections)
mcp.tool(name="test_connection")(test_connection)
