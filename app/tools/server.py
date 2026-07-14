"""FastMCP server and tool registry."""

from fastmcp import FastMCP

from app.tools.hello import hello_world

mcp = FastMCP(
    name="Data Platform MCP",
    instructions=(
        "Herramientas seguras para explorar plataformas de datos. "
        "Sprint 0 solo expone hello_world para verificar conectividad."
    ),
)
mcp.tool(name="hello_world")(hello_world)
