"""Tests for the liveness endpoint."""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_check_reports_service_liveness() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "data-platform-mcp",
        "version": "0.4.0",
    }
