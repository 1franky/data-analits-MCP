"""Replaceable persistence contract for metadata catalog snapshots."""

from abc import ABC, abstractmethod
from datetime import datetime

from app.models.catalog import CatalogRefreshRecord, CatalogSnapshot


class CatalogRepository(ABC):
    """Persist complete snapshots and refresh state without business rows."""

    @abstractmethod
    def initialize(self) -> None:
        """Create or migrate repository structures."""
        raise NotImplementedError

    @abstractmethod
    def mark_refresh_started(self, connection_id: str, started_at: datetime) -> None:
        """Record an in-progress refresh attempt."""
        raise NotImplementedError

    @abstractmethod
    def save_snapshot(
        self,
        snapshot: CatalogSnapshot,
        started_at: datetime,
        completed_at: datetime,
    ) -> None:
        """Atomically replace one valid snapshot and mark success."""
        raise NotImplementedError

    @abstractmethod
    def mark_refresh_failed(
        self,
        connection_id: str,
        started_at: datetime,
        completed_at: datetime,
        error_code: str,
        message: str,
    ) -> None:
        """Record failure without deleting the last valid snapshot."""
        raise NotImplementedError

    @abstractmethod
    def get_snapshot(self, connection_id: str) -> CatalogSnapshot | None:
        """Return the latest valid snapshot for one connection."""
        raise NotImplementedError

    @abstractmethod
    def list_snapshots(self) -> tuple[CatalogSnapshot, ...]:
        """Return all latest valid snapshots in stable order."""
        raise NotImplementedError

    @abstractmethod
    def get_refresh_record(self, connection_id: str) -> CatalogRefreshRecord | None:
        """Return the latest refresh attempt for one connection."""
        raise NotImplementedError
