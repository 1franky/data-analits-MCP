"""Tests for refresh, search, expiry, failure retention and concurrency."""

from datetime import timedelta
from pathlib import Path
from threading import Event, Thread

import pytest

from app.exceptions import (
    CatalogRequestError,
    CatalogSnapshotNotFoundError,
    DatabaseObjectNotFoundError,
)
from app.models.catalog import (
    CardinalityInference,
    CatalogRefreshOutcome,
    CatalogRefreshState,
    RelationshipCardinality,
)
from app.models.connections import CatalogConfig, ForeignKeyInfo, TableDescription, UniqueKeyInfo
from app.services import CatalogService
from tests.catalog_fakes import CatalogStubAdapter, MutableClock, build_catalog_service


def test_refresh_and_search_include_descriptions_and_relationships(tmp_path: Path) -> None:
    service, _repository, _adapter = build_catalog_service(tmp_path / "catalog.db")

    refresh = service.refresh_connection("postgres-demo")
    by_description = service.search("correo electrónico", "postgres-demo")
    by_table = service.search("clientes", "postgres-demo")

    assert refresh.outcome is CatalogRefreshOutcome.SUCCESS
    assert refresh.schemas_count == 1
    assert refresh.tables_count == 3
    assert by_description.matches[0].table == "clientes"
    assert by_description.matches[0].matched_columns == ("correo",)
    assert by_table.matches[0].relationships[0].source_table == "ventas"
    assert by_table.cache_statuses[0].stale is False


def test_cached_metadata_exploration_returns_versioned_structured_models(
    tmp_path: Path,
) -> None:
    service, _repository, _adapter = build_catalog_service(tmp_path / "catalog.db")
    service.refresh_connection("postgres-demo")

    schemas = service.list_schemas("postgres-demo")
    tables = service.list_tables("postgres-demo", "public")
    description = service.describe_table("postgres-demo", "public", "clientes")
    relationships = service.list_relationships("postgres-demo", table="ventas")

    assert schemas.contract_version == "1.0.0"
    assert schemas.connection_id == "postgres-demo"
    assert tuple(schema.name for schema in schemas.schemas) == ("public",)
    assert schemas.cache_status.stale is False
    assert {table.name for table in tables.tables} == {"clientes", "productos", "ventas"}
    assert all(table.schema_name == "public" for table in tables.tables)
    assert description.table.unique_keys[0].columns == ("correo",)
    assert relationships.relationships[0].source_table == "ventas"
    assert relationships.relationships[0].target_table == "clientes"
    assert relationships.relationships[0].source_columns == ("cliente_id",)
    assert relationships.relationships[0].target_columns == ("id",)
    assert relationships.relationships[0].cardinality is RelationshipCardinality.MANY_TO_ONE
    assert (
        relationships.relationships[0].cardinality_inference
        is CardinalityInference.SOURCE_NOT_UNIQUE
    )


@pytest.mark.parametrize(
    ("primary_key", "unique_keys", "expected_inference"),
    [
        (("account_id",), (), CardinalityInference.SOURCE_PRIMARY_KEY),
        (
            ("id",),
            (UniqueKeyInfo(name="profile_account_key", columns=("account_id",)),),
            CardinalityInference.SOURCE_UNIQUE_KEY,
        ),
    ],
)
def test_relationship_cardinality_is_inferred_from_source_uniqueness(
    primary_key: tuple[str, ...],
    unique_keys: tuple[UniqueKeyInfo, ...],
    expected_inference: CardinalityInference,
) -> None:
    profile = TableDescription(
        schema="public",
        name="profiles",
        columns=(),
        primary_key=primary_key,
        unique_keys=unique_keys,
        foreign_keys=(
            ForeignKeyInfo(
                name="profiles_account_id_fkey",
                columns=("account_id",),
                referenced_schema="public",
                referenced_table="accounts",
                referenced_columns=("id",),
            ),
        ),
    )

    relationship = CatalogService._relationships((profile,))[0]

    assert relationship.cardinality is RelationshipCardinality.ONE_TO_ONE
    assert relationship.cardinality_inference is expected_inference


def test_metadata_exploration_requires_a_valid_snapshot(tmp_path: Path) -> None:
    service, _repository, _adapter = build_catalog_service(tmp_path / "catalog.db")

    with pytest.raises(CatalogSnapshotNotFoundError, match="refresh_schema_cache"):
        service.list_schemas("postgres-demo")


def test_metadata_exploration_rejects_blank_filters(tmp_path: Path) -> None:
    service, _repository, _adapter = build_catalog_service(tmp_path / "catalog.db")

    with pytest.raises(CatalogRequestError, match="schema"):
        service.list_tables("postgres-demo", "   ")


def test_describe_table_reports_the_requested_missing_object(tmp_path: Path) -> None:
    service, _repository, _adapter = build_catalog_service(tmp_path / "catalog.db")
    service.refresh_connection("postgres-demo")

    with pytest.raises(DatabaseObjectNotFoundError, match=r"public\.missing"):
        service.describe_table("postgres-demo", "public", "missing")


def test_refresh_all_updates_every_enabled_connection(tmp_path: Path) -> None:
    service, _repository, adapter = build_catalog_service(tmp_path / "catalog.db")

    results = service.refresh_all()

    assert tuple(result.connection_id for result in results) == ("postgres-demo",)
    assert tuple(result.outcome for result in results) == (CatalogRefreshOutcome.SUCCESS,)
    assert adapter.refresh_calls == 1


def test_cache_becomes_stale_after_configured_interval(tmp_path: Path) -> None:
    clock = MutableClock()
    service, _repository, _adapter = build_catalog_service(
        tmp_path / "catalog.db",
        config=CatalogConfig(stale_after_minutes=120),
        clock=clock,
    )
    service.refresh_connection("postgres-demo")

    assert service.get_cache_status("postgres-demo")[0].stale is False

    clock.current += timedelta(minutes=121)

    assert service.get_cache_status("postgres-demo")[0].stale is True


def test_failed_refresh_preserves_last_valid_snapshot(tmp_path: Path) -> None:
    adapter = CatalogStubAdapter()
    service, repository, _adapter = build_catalog_service(
        tmp_path / "catalog.db",
        adapter=adapter,
    )
    service.refresh_connection("postgres-demo")
    snapshot_before = repository.get_snapshot("postgres-demo")
    adapter.fail = True

    failed = service.refresh_connection("postgres-demo")
    snapshot_after = repository.get_snapshot("postgres-demo")
    status = service.get_cache_status("postgres-demo")[0]

    assert failed.outcome is CatalogRefreshOutcome.ERROR
    assert failed.error_code == "DATABASE_METADATA_ERROR"
    assert snapshot_after == snapshot_before
    assert status.state is CatalogRefreshState.ERROR
    assert status.has_snapshot is True


def test_concurrent_refresh_for_same_connection_is_rejected(tmp_path: Path) -> None:
    adapter = CatalogStubAdapter()
    adapter.started_event = Event()
    adapter.release_event = Event()
    service, _repository, _adapter = build_catalog_service(
        tmp_path / "catalog.db",
        adapter=adapter,
    )
    first_results: list[CatalogRefreshOutcome] = []

    def run_first_refresh() -> None:
        first_results.append(service.refresh_connection("postgres-demo").outcome)

    thread = Thread(target=run_first_refresh)
    thread.start()
    assert adapter.started_event.wait(timeout=5)

    second = service.refresh_connection("postgres-demo")
    adapter.release_event.set()
    thread.join(timeout=5)

    assert second.outcome is CatalogRefreshOutcome.ALREADY_RUNNING
    assert first_results == [CatalogRefreshOutcome.SUCCESS]
    assert adapter.refresh_calls == 1


def test_catalog_filters_tables_by_qualified_glob(tmp_path: Path) -> None:
    service, repository, _adapter = build_catalog_service(
        tmp_path / "catalog.db",
        config=CatalogConfig(exclude_table_patterns=("public.productos",)),
    )

    service.refresh_connection("postgres-demo")
    snapshot = repository.get_snapshot("postgres-demo")

    assert snapshot is not None
    assert {table.name for table in snapshot.tables} == {"clientes", "ventas"}


@pytest.mark.parametrize(("query", "limit"), [("   ", 20), ("clientes", 0), ("ventas", 101)])
def test_search_rejects_invalid_requests(tmp_path: Path, query: str, limit: int) -> None:
    service, _repository, _adapter = build_catalog_service(tmp_path / "catalog.db")

    with pytest.raises(CatalogRequestError):
        service.search(query, max_results=limit)
