"""Default document adapter registrations available in the running application."""

from app.adapters.document_factory import DocumentAdapterFactory
from app.adapters.mongodb import MongoDbAdapter
from app.models.connections import ConnectionType


def create_document_adapter_factory() -> DocumentAdapterFactory:
    """Create an isolated registry with all implemented document adapters."""
    factory = DocumentAdapterFactory()
    factory.register(
        connection_type=ConnectionType.MONGODB,
        builder=MongoDbAdapter,
        capabilities=MongoDbAdapter.CAPABILITIES,
    )
    return factory
