"""MCP tools for connection discovery and connectivity checks."""

from app.container import get_connection_service
from app.models.connections import ConnectionSummary, ConnectionTestResult
from app.models.metadata import ConnectionCapabilitiesResponse


def list_connections() -> tuple[ConnectionSummary, ...]:
    """List configured connections and adapter capabilities without secrets."""
    return get_connection_service().list_connections()


def get_connection_capabilities(connection_id: str) -> ConnectionCapabilitiesResponse:
    """Return one connection and its adapter capability matrix without secrets."""
    summary = get_connection_service().get_connection_summary(connection_id)
    return ConnectionCapabilitiesResponse(
        connection_id=connection_id,
        connection=summary,
    )


def test_connection(connection_id: str) -> ConnectionTestResult:
    """Test an enabled connection using a bounded read-only operation."""
    return get_connection_service().test_connection(connection_id)
