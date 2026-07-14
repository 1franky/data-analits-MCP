"""MCP tools for connection discovery and connectivity checks."""

from app.container import get_connection_service
from app.models.connections import ConnectionSummary, ConnectionTestResult


def list_connections() -> tuple[ConnectionSummary, ...]:
    """List configured connections and adapter capabilities without secrets."""
    return get_connection_service().list_connections()


def test_connection(connection_id: str) -> ConnectionTestResult:
    """Test an enabled connection using a bounded read-only operation."""
    return get_connection_service().test_connection(connection_id)
