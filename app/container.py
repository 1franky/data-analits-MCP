"""Composition root for application services."""

import os
from functools import lru_cache
from pathlib import Path

from app.adapters.registry import create_adapter_factory
from app.config import ConnectionsConfigLoader
from app.models.connections import ConnectionsConfig
from app.repositories import (
    AuditRepository,
    CatalogRepository,
    SqliteAuditRepository,
    SqliteCatalogRepository,
)
from app.scheduler import CatalogScheduler
from app.services import (
    AuditService,
    CatalogService,
    ConnectionService,
    QueryExecutionService,
    QueryValidationService,
)


@lru_cache(maxsize=1)
def get_connections_config() -> ConnectionsConfig:
    """Load and cache validated process configuration."""
    config_path = Path(os.environ.get("CONNECTIONS_FILE", "connections.yaml"))
    return ConnectionsConfigLoader(config_path).load()


@lru_cache(maxsize=1)
def get_connection_service() -> ConnectionService:
    """Build and cache the validated connection service for this process."""
    config = get_connections_config()
    service = ConnectionService(
        config=config,
        adapter_factory=create_adapter_factory(),
        environment=os.environ,
    )
    service.validate_startup()
    return service


@lru_cache(maxsize=1)
def get_catalog_repository() -> CatalogRepository:
    """Build and initialize the configured metadata repository."""
    database_path = Path(os.environ.get("CATALOG_DB_PATH", "data/catalog.db"))
    repository = SqliteCatalogRepository(database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_catalog_service() -> CatalogService:
    """Build the catalog service from shared process dependencies."""
    return CatalogService(
        connections=get_connection_service(),
        repository=get_catalog_repository(),
        config=get_connections_config().catalog,
    )


@lru_cache(maxsize=1)
def get_catalog_scheduler() -> CatalogScheduler:
    """Build the single process-wide catalog scheduler."""
    service = get_catalog_service()
    config = service.config
    return CatalogScheduler(
        service=service,
        interval_seconds=config.refresh_interval_minutes * 60,
        refresh_on_startup=config.refresh_on_startup,
        enabled=config.enabled,
    )


@lru_cache(maxsize=1)
def get_audit_repository() -> AuditRepository:
    """Build and initialize the append-only query audit repository."""
    database_path = Path(os.environ.get("AUDIT_DB_PATH", "data/audit.db"))
    repository = SqliteAuditRepository(database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_audit_service() -> AuditService:
    """Build the privacy-preserving process audit service."""
    return AuditService(
        repository=get_audit_repository(),
        config=get_connections_config().audit,
    )


@lru_cache(maxsize=1)
def get_query_validation_service() -> QueryValidationService:
    """Build the stateless parser-backed SQL validator."""
    return QueryValidationService()


@lru_cache(maxsize=1)
def get_query_execution_service() -> QueryExecutionService:
    """Build the bounded query execution and explain service."""
    return QueryExecutionService(
        connections=get_connection_service(),
        validator=get_query_validation_service(),
        audit=get_audit_service(),
        policy=get_connections_config().query,
    )
