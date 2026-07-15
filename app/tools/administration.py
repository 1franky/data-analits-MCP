"""Versioned administrative tools available through MCP."""

from app import __version__
from app.models.metadata import McpHealthResponse


def health_check() -> McpHealthResponse:
    """Report MCP process liveness and server/contract versions."""
    return McpHealthResponse(
        status="ok",
        service="data-platform-mcp",
        server_version=__version__,
    )
