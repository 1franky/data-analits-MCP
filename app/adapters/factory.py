"""Registry-based adapter construction without engine conditionals."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import SecretStr

from app.adapters.base import SqlDatabaseAdapter
from app.exceptions import AdapterNotAvailableError
from app.models.connections import ConnectionCapabilities, ConnectionConfig, ConnectionType

AdapterBuilder = Callable[[ConnectionConfig, SecretStr], SqlDatabaseAdapter]


@dataclass(frozen=True, slots=True)
class AdapterRegistration:
    """Builder and public capabilities registered for an engine."""

    builder: AdapterBuilder
    capabilities: ConnectionCapabilities


class AdapterFactory:
    """Create adapters through an explicit engine registry."""

    def __init__(self) -> None:
        self._registrations: dict[ConnectionType, AdapterRegistration] = {}

    def register(
        self,
        connection_type: ConnectionType,
        builder: AdapterBuilder,
        capabilities: ConnectionCapabilities,
    ) -> None:
        """Register or replace one engine adapter."""
        self._registrations[connection_type] = AdapterRegistration(builder, capabilities)

    def supports(self, connection_type: ConnectionType) -> bool:
        """Return whether an adapter is registered for an engine."""
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
    ) -> SqlDatabaseAdapter:
        """Construct the registered adapter for a validated declaration."""
        registration = self._registrations.get(config.type)
        if registration is None:
            raise AdapterNotAvailableError(config.type.value)
        return registration.builder(config, password)
