"""Unit tests for MariaDB adapter construction and safe failures."""

from pydantic import SecretStr

from app.adapters.mariadb import MariaDbAdapter
from app.exceptions import ConfigurationError
from app.models.connections import ConnectionConfig
from tests.factories import make_connection_config


def _mariadb_config(**overrides: object) -> ConnectionConfig:
    values: dict[str, object] = {
        "id": "mariadb-demo",
        "name": "MariaDB Demo",
        "type": "mariadb",
        "host": "mariadb-lab",
        "port": 3306,
        "database": "demo",
        "username": "mcp_readonly",
        "password_env": "MARIADB_DEMO_PASSWORD",
        "options": {"charset": "utf8mb4"},
    }
    values.update(overrides)
    return make_connection_config(**values)


def test_mariadb_adapter_rejects_wrong_engine_type() -> None:
    config = _mariadb_config(type="postgres", options={})

    try:
        MariaDbAdapter(config, SecretStr("unit-test-secret"))
    except ConfigurationError as error:
        assert error.code == "MARIADB_CONFIG_TYPE_ERROR"
    else:
        raise AssertionError("ConfigurationError was not raised")


def test_mariadb_adapter_rejects_unknown_driver_options() -> None:
    config = _mariadb_config(options={"unsafe_option": "value"})

    try:
        MariaDbAdapter(config, SecretStr("unit-test-secret"))
    except ConfigurationError as error:
        assert error.code == "MARIADB_OPTIONS_ERROR"
        assert "unsafe_option" in error.message
    else:
        raise AssertionError("ConfigurationError was not raised")


def test_mariadb_adapter_rejects_redundant_connect_timeout_option() -> None:
    config = _mariadb_config(options={"connect_timeout": 5})

    try:
        MariaDbAdapter(config, SecretStr("unit-test-secret"))
    except ConfigurationError as error:
        assert error.code == "MARIADB_OPTIONS_ERROR"
    else:
        raise AssertionError("ConfigurationError was not raised")


def test_failed_connection_result_never_exposes_password() -> None:
    config = _mariadb_config(host="127.0.0.1", port=1, connect_timeout_seconds=1)
    password = "secret-that-must-not-leak"

    result = MariaDbAdapter(config, SecretStr(password)).test_connection()

    assert result.success is False
    assert result.error_code is not None
    assert password not in result.message
    assert password not in result.model_dump_json()


def test_placeholder_translation_is_safe_for_pymysql() -> None:
    translated = MariaDbAdapter._translate_placeholders(
        "SELECT id FROM clientes WHERE id = :minimum_id AND nombre = :target_name"
    )

    assert translated == (
        "SELECT id FROM clientes WHERE id = %(minimum_id)s AND nombre = %(target_name)s"
    )
