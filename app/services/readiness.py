"""Cheap process readiness, reusing state already validated at startup."""

from typing import Literal

from app import __version__
from app.models.connections import ConnectionsConfig
from app.models.health import ReadinessCheck, ReadinessResponse
from app.repositories import AuditRepository
from app.scheduler import CatalogScheduler, DocumentIndexScheduler
from app.services.connections import ConnectionService


class ReadinessService:
    """Report readiness without opening new connections on every call."""

    def __init__(
        self,
        connections: ConnectionService,
        catalog_scheduler: CatalogScheduler,
        audit_repository: AuditRepository,
        config: ConnectionsConfig,
        document_index_scheduler: DocumentIndexScheduler | None = None,
    ) -> None:
        self._connections = connections
        self._catalog_scheduler = catalog_scheduler
        self._audit_repository = audit_repository
        self._config = config
        self._document_index_scheduler = document_index_scheduler

    def check(self) -> ReadinessResponse:
        """Aggregate cheap, already-known readiness signals into one response."""
        checks = [
            ReadinessCheck(name="connections", ready=True),
            ReadinessCheck(name="audit_repository", ready=True),
            ReadinessCheck(
                name="catalog_scheduler",
                ready=(not self._config.catalog.enabled) or self._catalog_scheduler.running,
            ),
        ]
        if self._config.rag.enabled and self._document_index_scheduler is not None:
            checks.append(
                ReadinessCheck(
                    name="document_index_scheduler",
                    ready=self._document_index_scheduler.running,
                )
            )
        status: Literal["ready", "not_ready"] = (
            "ready" if all(check.ready for check in checks) else "not_ready"
        )
        return ReadinessResponse(
            status=status,
            service="data-platform-mcp",
            version=__version__,
            checks=tuple(checks),
        )
