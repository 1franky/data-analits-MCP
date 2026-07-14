"""Tests for YAML loading and connection configuration validation."""

from pathlib import Path

import pytest

from app.config import ConnectionsConfigLoader
from app.exceptions import ConfigurationError

_VALID_YAML = """
connections:
  - id: postgres-demo
    name: PostgreSQL Demo
    type: postgres
    host: postgres-lab
    port: 5432
    database: demo
    username: mcp_readonly
    password_env: POSTGRES_DEMO_PASSWORD
    readonly: true
    enabled: true
    connect_timeout_seconds: 10
    query_timeout_seconds: 30
    max_rows: 500
    options:
      sslmode: disable
"""


def write_config(tmp_path: Path, content: str) -> Path:
    """Write a temporary configuration file for loader tests."""
    config_path = tmp_path / "connections.yaml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


def test_loader_parses_valid_connection_without_resolving_password(tmp_path: Path) -> None:
    config = ConnectionsConfigLoader(write_config(tmp_path, _VALID_YAML)).load()

    connection = config.connections[0]
    assert connection.id == "postgres-demo"
    assert connection.password_env == "POSTGRES_DEMO_PASSWORD"
    assert "password" not in connection.model_dump()


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    duplicate = _VALID_YAML + _VALID_YAML.split("connections:\n", maxsplit=1)[1]

    with pytest.raises(ConfigurationError, match="duplicados") as raised:
        ConnectionsConfigLoader(write_config(tmp_path, duplicate)).load()

    assert raised.value.code == "CONFIG_VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (_VALID_YAML.replace("type: postgres", "type: db2"), "Input should be"),
        (_VALID_YAML.replace("readonly: true", "readonly: false"), "readonly=true"),
        (
            _VALID_YAML.replace("sslmode: disable", "password: forbidden"),
            "campos reservados",
        ),
        (_VALID_YAML.replace("port: 5432", "port: 70000"), "less than or equal"),
    ],
)
def test_loader_rejects_invalid_declarations(
    tmp_path: Path,
    source: str,
    message: str,
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        ConnectionsConfigLoader(write_config(tmp_path, source)).load()


def test_loader_rejects_invalid_yaml_root(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as raised:
        ConnectionsConfigLoader(write_config(tmp_path, "- postgres-demo\n")).load()

    assert raised.value.code == "CONFIG_ROOT_ERROR"


def test_loader_reports_missing_file_without_os_error_details(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as raised:
        ConnectionsConfigLoader(tmp_path / "missing.yaml").load()

    assert raised.value.code == "CONFIG_READ_ERROR"
    assert "missing.yaml" in raised.value.message
