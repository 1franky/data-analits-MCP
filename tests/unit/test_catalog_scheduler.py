"""Tests for periodic non-blocking catalog refresh scheduling."""

import asyncio
from pathlib import Path

from app.scheduler import CatalogScheduler
from tests.catalog_fakes import build_catalog_service


async def test_scheduler_refreshes_on_startup_and_periodically(tmp_path: Path) -> None:
    service, _repository, adapter = build_catalog_service(tmp_path / "catalog.db")
    scheduler = CatalogScheduler(
        service=service,
        interval_seconds=0.02,
        refresh_on_startup=True,
        enabled=True,
    )

    await scheduler.start()
    assert scheduler.running is True
    await asyncio.sleep(0.075)
    await scheduler.stop()

    assert adapter.refresh_calls >= 2
    assert scheduler.running is False


async def test_disabled_scheduler_never_refreshes(tmp_path: Path) -> None:
    service, _repository, adapter = build_catalog_service(tmp_path / "catalog.db")
    scheduler = CatalogScheduler(
        service=service,
        interval_seconds=0.01,
        refresh_on_startup=True,
        enabled=False,
    )

    await scheduler.start()
    await asyncio.sleep(0.025)
    await scheduler.stop()

    assert scheduler.running is False
    assert adapter.refresh_calls == 0
