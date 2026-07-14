"""Composition root for application services."""

import os
from functools import lru_cache
from pathlib import Path

from app.adapters.registry import create_adapter_factory
from app.config import ConnectionsConfigLoader
from app.services import ConnectionService


@lru_cache(maxsize=1)
def get_connection_service() -> ConnectionService:
    """Build and cache the validated connection service for this process."""
    config_path = Path(os.environ.get("CONNECTIONS_FILE", "connections.yaml"))
    config = ConnectionsConfigLoader(config_path).load()
    service = ConnectionService(
        config=config,
        adapter_factory=create_adapter_factory(),
        environment=os.environ,
    )
    service.validate_startup()
    return service
