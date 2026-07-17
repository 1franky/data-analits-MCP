"""Connection discovery, secret resolution and adapter orchestration."""

from collections.abc import Mapping

from pydantic import SecretStr

from app.adapters.base import DocumentDatabaseAdapter, SqlDatabaseAdapter
from app.adapters.document_factory import DocumentAdapterFactory
from app.adapters.factory import AdapterFactory
from app.exceptions import (
    AdapterNotAvailableError,
    ConnectionDisabledError,
    ConnectionNotFoundError,
    DataPlatformError,
    SecretNotConfiguredError,
)
from app.models.connections import (
    ConnectionConfig,
    ConnectionsConfig,
    ConnectionSummary,
    ConnectionTestResult,
)


class ConnectionService:
    """Provide secret-safe access to configured database connections."""

    def __init__(
        self,
        config: ConnectionsConfig,
        adapter_factory: AdapterFactory,
        environment: Mapping[str, str],
        document_adapter_factory: DocumentAdapterFactory | None = None,
    ) -> None:
        self._connections = {connection.id: connection for connection in config.connections}
        self._adapter_factory = adapter_factory
        self._document_adapter_factory = document_adapter_factory or DocumentAdapterFactory()
        self._environment = environment

    def validate_startup(self) -> None:
        """Fail startup when an enabled connection cannot be used safely."""
        for connection in self._connections.values():
            if not connection.enabled:
                continue
            secret = self._secret_for(connection)
            if self._adapter_factory.supports(connection.type):
                self._adapter_factory.create(connection, secret)
            elif self._document_adapter_factory.supports(connection.type):
                self._document_adapter_factory.create(connection, secret)
            else:
                raise AdapterNotAvailableError(connection.type.value)

    def list_connections(self) -> tuple[ConnectionSummary, ...]:
        """List declarations without resolving or exposing secrets."""
        return tuple(
            ConnectionSummary(
                id=connection.id,
                name=connection.name,
                type=connection.type,
                database=connection.database,
                enabled=connection.enabled,
                readonly=connection.readonly,
                capabilities=(
                    self._adapter_factory.capabilities_for(connection.type)
                    or self._document_adapter_factory.capabilities_for(connection.type)
                ),
            )
            for connection in sorted(self._connections.values(), key=lambda item: item.id)
        )

    def get_connection_summary(self, connection_id: str) -> ConnectionSummary:
        """Return one safe connection declaration without resolving secrets."""
        for summary in self.list_connections():
            if summary.id == connection_id:
                return summary
        raise ConnectionNotFoundError(connection_id)

    def test_connection(self, connection_id: str) -> ConnectionTestResult:
        """Test one enabled connection (SQL or document) and normalize domain failures."""
        try:
            connection = self.get_connection_config(connection_id)
            adapter = self._resolve_any_adapter(connection)
        except DataPlatformError as error:
            return ConnectionTestResult(
                connection_id=connection_id,
                success=False,
                latency_ms=0.0,
                error_code=error.code,
                message=error.message,
            )
        return adapter.test_connection()

    def get_adapter(self, connection_id: str) -> SqlDatabaseAdapter:
        """Resolve a validated connection and create its SQL adapter."""
        connection = self.get_connection_config(connection_id)
        password = self._secret_for(connection)
        return self._adapter_factory.create(connection, password)

    def get_document_adapter(self, connection_id: str) -> DocumentDatabaseAdapter:
        """Resolve a validated connection and create its document adapter."""
        connection = self.get_connection_config(connection_id)
        password = self._secret_for(connection)
        return self._document_adapter_factory.create(connection, password)

    def _resolve_any_adapter(
        self,
        connection: ConnectionConfig,
    ) -> SqlDatabaseAdapter | DocumentDatabaseAdapter:
        password = self._secret_for(connection)
        if self._adapter_factory.supports(connection.type):
            return self._adapter_factory.create(connection, password)
        if self._document_adapter_factory.supports(connection.type):
            return self._document_adapter_factory.create(connection, password)
        raise AdapterNotAvailableError(connection.type.value)

    def get_connection_config(self, connection_id: str) -> ConnectionConfig:
        """Return one enabled internal declaration without resolving its secret."""
        connection = self._connections.get(connection_id)
        if connection is None:
            raise ConnectionNotFoundError(connection_id)
        if not connection.enabled:
            raise ConnectionDisabledError(connection_id)
        return connection

    def _secret_for(self, connection: ConnectionConfig) -> SecretStr:
        secret = self._environment.get(connection.password_env)
        if secret is None or not secret.strip():
            raise SecretNotConfiguredError(connection.password_env)
        return SecretStr(secret)
