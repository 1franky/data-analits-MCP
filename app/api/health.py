"""Liveness endpoint for operators and container orchestrators."""

from fastapi import APIRouter

from app import __version__
from app.models.health import HealthResponse

router = APIRouter(tags=["administration"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Report process liveness",
)
async def health_check() -> HealthResponse:
    """Return liveness without depending on future external services."""
    return HealthResponse(
        status="ok",
        service="data-platform-mcp",
        version=__version__,
    )
