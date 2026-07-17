"""Registry-based document adapter construction without engine conditionals."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import SecretStr

from app.adapters.base import DocumentDatabaseAdapter
from app.exceptions import AdapterNotAvailableError
from app.models.connections import ConnectionCapabilities, ConnectionConfig, ConnectionType

DocumentAdapterBuilder = Callable[[ConnectionConfig, SecretStr], DocumentDatabaseAdapter]


@dataclass(frozen=True, slots=True)
class DocumentAdapterRegistration:
    """Builder and public capabilities registered for a document engine."""

    builder: DocumentAdapterBuilder
    capabilities: ConnectionCapabilities


class DocumentAdapterFactory:
    """Create document adapters through an explicit engine registry."""

    def __init__(self) -> None:
        self._registrations: dict[ConnectionType, DocumentAdapterRegistration] = {}

    def register(
        self,
        connection_type: ConnectionType,
        builder: DocumentAdapterBuilder,
        capabilities: ConnectionCapabilities,
    ) -> None:
        """Register or replace one engine document adapter."""
        self._registrations[connection_type] = DocumentAdapterRegistration(builder, capabilities)

    def supports(self, connection_type: ConnectionType) -> bool:
        """Return whether a document adapter is registered for an engine."""
        return connection_type in self._registrations

    def capabilities_for(
        self,
        connection_type: ConnectionType,
    ) -> ConnectionCapabilities | None:
        """Return public adapter capabilities without constructing an adapter."""
        registration = self._registrations.get(connection_type)
        return registration.capabilities if registration is not None else None

    def create(
        self,
        config: ConnectionConfig,
        password: SecretStr,
    ) -> DocumentDatabaseAdapter:
        """Construct the registered document adapter for a validated declaration."""
        registration = self._registrations.get(config.type)
        if registration is None:
            raise AdapterNotAvailableError(config.type.value)
        return registration.builder(config, password)
