"""Combined FastAPI and FastMCP ASGI application."""

from fastapi import FastAPI
from fastmcp.utilities.lifespan import combine_lifespans

from app import __version__
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.lifespan import application_lifespan
from app.observability.logging import configure_logging
from app.observability.middleware import RequestContextMiddleware
from app.tools.server import mcp

configure_logging()

mcp_app = mcp.http_app(path="/mcp")

app = FastAPI(
    title="Data Platform MCP",
    description="Administrative API and Model Context Protocol server.",
    version=__version__,
    routes=[*mcp_app.routes],
    lifespan=combine_lifespans(application_lifespan, mcp_app.lifespan),
)
app.add_middleware(RequestContextMiddleware)
app.include_router(health_router)
app.include_router(metrics_router)
