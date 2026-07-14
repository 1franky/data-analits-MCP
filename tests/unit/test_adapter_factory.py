"""Tests for registry-based adapter construction."""

from pydantic import SecretStr

from app.adapters.base import SqlDatabaseAdapter
from app.adapters.factory import AdapterFactory
from app.exceptions import AdapterNotAvailableError
from app.models.connections import (
    ConnectionCapabilities,
    ConnectionConfig,
    ConnectionTestResult,
    ConnectionType,
    QueryLanguage,
    SchemaInfo,
    TableDescription,
    TableInfo,
)
from tests.factories import make_connection_config

_CAPABILITIES = ConnectionCapabilities(query_language=QueryLanguage.SQL)


class StubAdapter(SqlDatabaseAdapter):
    """Minimal concrete adapter used to exercise the registry."""

    def __init__(self, connection_id: str, password: SecretStr) -> None:
        self.connection_id = connection_id
        self.password = password

    @property
    def capabilities(self) -> ConnectionCapabilities:
        return _CAPABILITIES

    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            connection_id=self.connection_id,
            success=True,
            latency_ms=1.0,
            message="ok",
        )

    def list_schemas(self) -> tuple[SchemaInfo, ...]:
        return ()

    def list_tables(self, schema: str | None = None) -> tuple[TableInfo, ...]:
        return ()

    def describe_table(self, schema: str, table: str) -> TableDescription:
        return TableDescription(
            schema=schema,
            name=table,
            columns=(),
            primary_key=(),
            foreign_keys=(),
        )


def build_stub_adapter(config: ConnectionConfig, password: SecretStr) -> SqlDatabaseAdapter:
    """Build a stub while keeping the production builder signature explicit."""
    return StubAdapter(config.id, password)


def test_factory_uses_registered_builder() -> None:
    factory = AdapterFactory()
    factory.register(ConnectionType.POSTGRES, build_stub_adapter, _CAPABILITIES)

    adapter = factory.create(make_connection_config(), SecretStr("unit-test-secret"))

    assert isinstance(adapter, StubAdapter)
    assert adapter.connection_id == "postgres-demo"
    assert adapter.password.get_secret_value() == "unit-test-secret"
    assert factory.capabilities_for(ConnectionType.POSTGRES) == _CAPABILITIES


def test_factory_rejects_unregistered_engine() -> None:
    factory = AdapterFactory()
    config = make_connection_config(type="sqlserver")

    try:
        factory.create(config, SecretStr("unit-test-secret"))
    except AdapterNotAvailableError as error:
        assert error.code == "ADAPTER_NOT_AVAILABLE"
    else:
        raise AssertionError("AdapterNotAvailableError was not raised")
