"""Liveness and readiness endpoints for operators and container orchestrators."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import __version__
from app.container import get_readiness_service
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


@router.get(
    "/ready",
    summary="Report process readiness",
)
async def readiness_check() -> JSONResponse:
    """Return readiness derived from already-validated startup state."""
    response = get_readiness_service().check()
    status_code = 200 if response.status == "ready" else 503
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))
