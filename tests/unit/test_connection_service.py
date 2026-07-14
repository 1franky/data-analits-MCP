"""Tests for secret resolution and public connection contracts."""

import pytest
from pydantic import SecretStr

from app.adapters.factory import AdapterFactory
from app.adapters.registry import create_adapter_factory
from app.exceptions import AdapterNotAvailableError, ConfigurationError, SecretNotConfiguredError
from app.models.connections import ConnectionConfig, ConnectionsConfig, ConnectionType
from app.services import ConnectionService
from tests.factories import make_connection_config
from tests.unit.test_adapter_factory import _CAPABILITIES, StubAdapter


def build_factory(captured_passwords: list[str] | None = None) -> AdapterFactory:
    """Create a registry whose builder can expose secret resolution to the test."""
    factory = AdapterFactory()

    def builder(config: ConnectionConfig, password: SecretStr) -> StubAdapter:
        if captured_passwords is not None:
            captured_passwords.append(password.get_secret_value())
        return StubAdapter(config.id, password)

    factory.register(ConnectionType.POSTGRES, builder, _CAPABILITIES)
    return factory


def test_list_connections_never_contains_secret_fields() -> None:
    service = ConnectionService(
        config=ConnectionsConfig(connections=(make_connection_config(),)),
        adapter_factory=build_factory(),
        environment={"POSTGRES_DEMO_PASSWORD": "unit-test-secret"},
    )

    public_data = service.list_connections()[0].model_dump(mode="json")

    assert public_data["id"] == "postgres-demo"
    assert public_data["capabilities"]["list_schemas"] is False
    assert "password" not in public_data
    assert "password_env" not in public_data
    assert "host" not in public_data
    assert "username" not in public_data
    assert "unit-test-secret" not in str(public_data)


def test_service_resolves_secret_only_when_adapter_is_requested() -> None:
    captured_passwords: list[str] = []
    service = ConnectionService(
        config=ConnectionsConfig(connections=(make_connection_config(),)),
        adapter_factory=build_factory(captured_passwords),
        environment={"POSTGRES_DEMO_PASSWORD": "unit-test-secret"},
    )

    service.list_connections()
    assert captured_passwords == []

    adapter = service.get_adapter("postgres-demo")
    assert isinstance(adapter, StubAdapter)
    assert captured_passwords == ["unit-test-secret"]


def test_startup_rejects_missing_secret() -> None:
    service = ConnectionService(
        config=ConnectionsConfig(connections=(make_connection_config(),)),
        adapter_factory=build_factory(),
        environment={},
    )

    with pytest.raises(SecretNotConfiguredError):
        service.validate_startup()


def test_startup_rejects_enabled_engine_without_adapter() -> None:
    service = ConnectionService(
        config=ConnectionsConfig(connections=(make_connection_config(type="sqlserver"),)),
        adapter_factory=AdapterFactory(),
        environment={"POSTGRES_DEMO_PASSWORD": "unit-test-secret"},
    )

    with pytest.raises(AdapterNotAvailableError):
        service.validate_startup()


def test_startup_rejects_invalid_engine_options() -> None:
    service = ConnectionService(
        config=ConnectionsConfig(
            connections=(make_connection_config(options={"unsafe_option": "value"}),),
        ),
        adapter_factory=create_adapter_factory(),
        environment={"POSTGRES_DEMO_PASSWORD": "unit-test-secret"},
    )

    with pytest.raises(ConfigurationError, match="unsafe_option"):
        service.validate_startup()


def test_disabled_connection_is_listed_but_cannot_be_tested() -> None:
    service = ConnectionService(
        config=ConnectionsConfig(
            connections=(make_connection_config(enabled=False, readonly=False),),
        ),
        adapter_factory=build_factory(),
        environment={},
    )

    summary = service.list_connections()[0]
    result = service.test_connection("postgres-demo")

    assert summary.enabled is False
    assert result.success is False
    assert result.error_code == "CONNECTION_DISABLED"


def test_unknown_connection_returns_normalized_error() -> None:
    service = ConnectionService(
        config=ConnectionsConfig(connections=()),
        adapter_factory=build_factory(),
        environment={},
    )

    result = service.test_connection("missing")

    assert result.success is False
    assert result.error_code == "CONNECTION_NOT_FOUND"
