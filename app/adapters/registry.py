"""Default adapter registrations available in the running application."""

from app.adapters.factory import AdapterFactory
from app.adapters.mariadb import MariaDbAdapter
from app.adapters.postgres import PostgresAdapter
from app.models.connections import ConnectionType


def create_adapter_factory() -> AdapterFactory:
    """Create an isolated registry with all implemented adapters."""
    factory = AdapterFactory()
    factory.register(
        connection_type=ConnectionType.POSTGRES,
        builder=PostgresAdapter,
        capabilities=PostgresAdapter.CAPABILITIES,
    )
    factory.register(
        connection_type=ConnectionType.MARIADB,
        builder=MariaDbAdapter,
        capabilities=MariaDbAdapter.CAPABILITIES,
    )
    return factory
