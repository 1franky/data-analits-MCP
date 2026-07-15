"""Persistence contract for query audit events."""

from abc import ABC, abstractmethod

from app.models.audit import AuditRecord


class AuditRepository(ABC):
    """Append-only audit repository boundary."""

    @abstractmethod
    def initialize(self) -> None:
        """Create durable storage when needed."""
        raise NotImplementedError

    @abstractmethod
    def append(self, record: AuditRecord) -> None:
        """Persist one immutable audit event."""
        raise NotImplementedError

    @abstractmethod
    def list_records(self) -> tuple[AuditRecord, ...]:
        """Return records in insertion order for operational inspection and tests."""
        raise NotImplementedError
