"""Tests for atomic SQLite catalog persistence."""

from datetime import UTC, datetime
from pathlib import Path

from app.models.catalog import CatalogRefreshState
from tests.catalog_fakes import build_catalog_service, snapshot_payload


def test_repository_round_trips_metadata_only_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "catalog.db"
    service, repository, _adapter = build_catalog_service(path)

    result = service.refresh_connection("postgres-demo")
    snapshot = repository.get_snapshot("postgres-demo")
    record = repository.get_refresh_record("postgres-demo")

    assert result.refreshed is True
    assert snapshot is not None
    assert record is not None
    assert record.state is CatalogRefreshState.SUCCESS
    assert {table.name for table in snapshot.tables} == {"clientes", "productos", "ventas"}
    serialized = snapshot_payload(snapshot)
    assert "Juan Pérez" not in serialized
    assert "Laptop" not in serialized


def test_repository_marks_interrupted_refresh_without_deleting_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "catalog.db"
    service, repository, _adapter = build_catalog_service(path)
    service.refresh_connection("postgres-demo")
    snapshot_before = repository.get_snapshot("postgres-demo")
    repository.mark_refresh_started(
        "postgres-demo",
        datetime(2026, 7, 14, 13, 0, tzinfo=UTC),
    )

    repository.initialize()

    snapshot_after = repository.get_snapshot("postgres-demo")
    record = repository.get_refresh_record("postgres-demo")
    assert snapshot_after == snapshot_before
    assert record is not None
    assert record.state is CatalogRefreshState.ERROR
    assert record.error_code == "REFRESH_INTERRUPTED"
