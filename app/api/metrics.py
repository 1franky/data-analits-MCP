"""Prometheus metrics exposition endpoint."""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["administration"])


@router.get("/metrics", summary="Export Prometheus metrics")
async def metrics() -> Response:
    """Return the current process metrics in Prometheus text exposition format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
