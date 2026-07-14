"""Tests for refresh, search, expiry, failure retention and concurrency."""

from datetime import timedelta
from pathlib import Path
from threading import Event, Thread

import pytest

from app.exceptions import CatalogRequestError
from app.models.catalog import CatalogRefreshOutcome, CatalogRefreshState
from app.models.connections import CatalogConfig
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
