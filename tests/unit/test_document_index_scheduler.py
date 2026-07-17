"""Tests for periodic non-blocking document index refresh scheduling."""

import asyncio
from pathlib import Path

from app.models.audit import AuditConfig
from app.models.rag import EmbeddingProviderType, RagConfig, RefreshDocumentIndexResult
from app.rag.embeddings.registry import EmbeddingProviderFactory
from app.repositories import SqliteAuditRepository, SqliteDocumentIndexRepository
from app.scheduler import DocumentIndexScheduler
from app.services import AuditService, DocumentIndexService
from tests.rag_fakes import (
    EMBEDDING_PROVIDER_CONFIG,
    FakeEmbeddingProvider,
    FakeVectorStoreRepository,
)


class _CountingDocumentIndexService(DocumentIndexService):
    """Subclass exposing a call counter for scheduler assertions."""

    refresh_calls: int = 0

    def refresh(self, source: str | None = None) -> RefreshDocumentIndexResult:
        self.refresh_calls += 1
        return super().refresh(source)


def _build_service(tmp_path: Path) -> _CountingDocumentIndexService:
    documents_root = tmp_path / "documents"
    documents_root.mkdir()
    provider = FakeEmbeddingProvider()
    provider_factory = EmbeddingProviderFactory()
    provider_factory.register(EmbeddingProviderType.OPENAI_COMPATIBLE, lambda _c, _k: provider)
    repository = SqliteDocumentIndexRepository(tmp_path / "documents.db")
    repository.initialize()
    audit_repository = SqliteAuditRepository(tmp_path / "audit.db")
    audit_repository.initialize()
    audit = AuditService(audit_repository, AuditConfig())
    config = RagConfig(
        enabled=True,
        documents_path=str(documents_root),
        embedding_provider=EMBEDDING_PROVIDER_CONFIG,
    )
    return _CountingDocumentIndexService(
        config=config,
        repository=repository,
        vector_store=FakeVectorStoreRepository(),
        embedding_provider_factory=provider_factory,
        environment={"EMBEDDING_API_KEY": "unit-test-embedding-key"},
        audit=audit,
    )


async def test_scheduler_refreshes_on_startup_and_periodically(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    scheduler = DocumentIndexScheduler(
        service=service,
        interval_seconds=0.02,
        refresh_on_startup=True,
        enabled=True,
    )

    await scheduler.start()
    assert scheduler.running is True
    for _ in range(100):
        if service.refresh_calls >= 2:
            break
        await asyncio.sleep(0.01)
    await scheduler.stop()

    assert service.refresh_calls >= 2
    assert scheduler.running is False


async def test_disabled_scheduler_never_refreshes(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    scheduler = DocumentIndexScheduler(
        service=service,
        interval_seconds=0.01,
        refresh_on_startup=True,
        enabled=False,
    )

    await scheduler.start()
    await asyncio.sleep(0.025)
    await scheduler.stop()

    assert scheduler.running is False
    assert service.refresh_calls == 0
