"""Catalog integration test against the Docker PostgreSQL laboratory."""

import os
from pathlib import Path

import pytest

from app.adapters.registry import create_adapter_factory
from app.models.catalog import CatalogRefreshOutcome, RelationshipCardinality
from app.models.connections import CatalogConfig, ConnectionsConfig
from app.repositories import SqliteCatalogRepository
from app.services import CatalogService, ConnectionService
from tests.factories import make_connection_config

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
        reason="set RUN_POSTGRES_INTEGRATION=1 with the PostgreSQL lab running",
    ),
]


def test_catalog_refresh_search_and_persistence_with_postgres(tmp_path: Path) -> None:
    connections = ConnectionService(
        config=ConnectionsConfig(connections=(make_connection_config(),)),
        adapter_factory=create_adapter_factory(),
        environment={"POSTGRES_DEMO_PASSWORD": os.environ["POSTGRES_DEMO_PASSWORD"]},
    )
    repository = SqliteCatalogRepository(tmp_path / "catalog.db")
    repository.initialize()
    service = CatalogService(connections, repository, CatalogConfig())

    refreshed = service.refresh_connection("postgres-demo")
    search = service.search("correo electrónico", "postgres-demo")
    schemas = service.list_schemas("postgres-demo")
    tables = service.list_tables("postgres-demo", "public")
    description = service.describe_table("postgres-demo", "public", "clientes")
    relationships = service.list_relationships("postgres-demo", table="ventas")
    snapshot = repository.get_snapshot("postgres-demo")

    assert refreshed.outcome is CatalogRefreshOutcome.SUCCESS
    assert refreshed.tables_count == 3
    assert search.matches[0].table == "clientes"
    assert search.matches[0].matched_columns == ("correo",)
    assert tuple(schema.name for schema in schemas.schemas) == ("public",)
    assert {table.name for table in tables.tables} == {"clientes", "productos", "ventas"}
    assert description.table.unique_keys[0].columns == ("correo",)
    assert {relationship.target_table for relationship in relationships.relationships} == {
        "clientes",
        "productos",
    }
    assert all(
        relationship.cardinality is RelationshipCardinality.MANY_TO_ONE
        for relationship in relationships.relationships
    )
    assert snapshot is not None
    assert snapshot.schema_hash == refreshed.schema_hash
    assert "Juan Pérez" not in snapshot.model_dump_json()
