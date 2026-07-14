"""Unit tests for PostgreSQL adapter construction and safe failures."""

from pydantic import SecretStr

from app.adapters.postgres import PostgresAdapter
from app.exceptions import ConfigurationError
from tests.factories import make_connection_config


def test_postgres_adapter_rejects_wrong_engine_type() -> None:
    config = make_connection_config(type="sqlserver")

    try:
        PostgresAdapter(config, SecretStr("unit-test-secret"))
    except ConfigurationError as error:
        assert error.code == "POSTGRES_CONFIG_TYPE_ERROR"
    else:
        raise AssertionError("ConfigurationError was not raised")


def test_postgres_adapter_rejects_unknown_driver_options() -> None:
    config = make_connection_config(options={"unsafe_option": "value"})

    try:
        PostgresAdapter(config, SecretStr("unit-test-secret"))
    except ConfigurationError as error:
        assert error.code == "POSTGRES_OPTIONS_ERROR"
        assert "unsafe_option" in error.message
    else:
        raise AssertionError("ConfigurationError was not raised")


def test_failed_connection_result_never_exposes_password() -> None:
    config = make_connection_config(
        host="127.0.0.1",
        port=1,
        connect_timeout_seconds=1,
        options={"application_name": "data-platform-mcp", "sslmode": "disable"},
    )
    password = "secret-that-must-not-leak"

    result = PostgresAdapter(config, SecretStr(password)).test_connection()

    assert result.success is False
    assert result.error_code is not None
    assert password not in result.message
    assert password not in result.model_dump_json()
