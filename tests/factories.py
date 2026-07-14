"""Typed factories shared by unit and integration tests."""

from app.models.connections import ConnectionConfig


def make_connection_config(**overrides: object) -> ConnectionConfig:
    """Build a valid secret-free PostgreSQL declaration."""
    values: dict[str, object] = {
        "id": "postgres-demo",
        "name": "PostgreSQL Demo",
        "type": "postgres",
        "host": "postgres-lab",
        "port": 5432,
        "database": "demo",
        "username": "mcp_readonly",
        "password_env": "POSTGRES_DEMO_PASSWORD",
        "readonly": True,
        "enabled": True,
        "connect_timeout_seconds": 10,
        "query_timeout_seconds": 30,
        "max_rows": 500,
        "options": {"application_name": "data-platform-mcp", "sslmode": "disable"},
    }
    values.update(overrides)
    return ConnectionConfig.model_validate(values)
