"""Tests for the Prometheus metrics exposition endpoint."""

from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.query_fakes import build_query_services


async def test_metrics_endpoint_exposes_query_requests_total_after_execution(
    tmp_path: Path,
) -> None:
    _connections, _validator, execution, _repository, _adapter = build_query_services(
        tmp_path / "audit.db"
    )
    execution.execute("postgres-demo", "SELECT 1")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "data_platform_query_requests_total" in response.text
    assert 'engine="postgres"' in response.text
    assert 'operation="execute"' in response.text


async def test_metrics_endpoint_is_prometheus_text_format(tmp_path: Path) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
