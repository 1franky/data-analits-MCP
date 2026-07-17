"""Deterministic embedding provider, vector store and service builders for RAG tests."""

from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.exceptions import DataPlatformError
from app.models.audit import AuditConfig
from app.models.rag import (
    ChunkSearchMatch,
    DocumentChunk,
    DocumentMetadata,
    EmbeddingBatchResult,
    EmbeddingProviderConfig,
    EmbeddingProviderType,
    RagConfig,
)
from app.rag.embeddings.provider import EmbeddingProvider
from app.rag.embeddings.registry import EmbeddingProviderFactory
from app.repositories import SqliteAuditRepository, SqliteDocumentIndexRepository
from app.repositories.vector_store import VectorStoreRepository
from app.services import AuditService, DocumentIndexService, DocumentSearchService

EMBEDDING_PROVIDER_CONFIG = EmbeddingProviderConfig(
    type=EmbeddingProviderType.OPENAI_COMPATIBLE,
    base_url="http://embeddings.invalid/v1",
    api_key_env="EMBEDDING_API_KEY",
    model="test-embedding-model",
    dimensions=8,
)


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic provider mapping text to a hash-derived vector."""

    def __init__(self, dimensions: int = 8) -> None:
        self.dimensions = dimensions
        self.calls: list[tuple[str, ...]] = []
        self.error: DataPlatformError | None = None
        self.close_calls = 0

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        self.calls.append(texts)
        if self.error is not None:
            raise self.error
        vectors = tuple(self._vector_for(text) for text in texts)
        return EmbeddingBatchResult(
            vectors=vectors,
            model="fake-embedding-model",
            dimensions=self.dimensions,
            duration_ms=1.0,
        )

    def close(self) -> None:
        self.close_calls += 1

    def _vector_for(self, text: str) -> tuple[float, ...]:
        digest = sha256(text.encode("utf-8")).digest()
        return tuple(digest[i % len(digest)] / 255.0 for i in range(self.dimensions))


class FakeVectorStoreRepository(VectorStoreRepository):
    """In-memory vector store using pure-Python cosine similarity."""

    def __init__(self) -> None:
        self._entries: dict[
            str, list[tuple[DocumentChunk, tuple[float, ...], DocumentMetadata]]
        ] = {}
        self.initialized_dimensions: int | None = None
        self.closed = False

    def initialize(self, dimensions: int) -> None:
        self.initialized_dimensions = dimensions

    def upsert_chunks(
        self,
        document_id: str,
        chunks: tuple[DocumentChunk, ...],
        vectors: tuple[tuple[float, ...], ...],
        metadata: DocumentMetadata,
    ) -> None:
        self._entries[document_id] = [
            (chunk, vector, metadata) for chunk, vector in zip(chunks, vectors, strict=True)
        ]

    def delete_document(self, document_id: str) -> None:
        self._entries.pop(document_id, None)

    def search(
        self,
        query_vector: tuple[float, ...],
        connection_id: str | None,
        domain: str | None,
        limit: int,
    ) -> tuple[ChunkSearchMatch, ...]:
        candidates: list[ChunkSearchMatch] = []
        for document_id, entries in self._entries.items():
            for chunk, vector, metadata in entries:
                if connection_id is not None and metadata.connection_id not in {
                    None,
                    connection_id,
                }:
                    continue
                if domain is not None and metadata.domain not in {None, domain}:
                    continue
                candidates.append(
                    ChunkSearchMatch(
                        document_id=document_id,
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        score=self._cosine(query_vector, vector),
                        metadata=metadata,
                    )
                )
        candidates.sort(key=lambda match: -match.score)
        return tuple(candidates[:limit])

    def close(self) -> None:
        self.closed = True

    @staticmethod
    def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
        dot = sum(x * y for x, y in zip(left, right, strict=True))
        norm_left = sum(x * x for x in left) ** 0.5
        norm_right = sum(y * y for y in right) ** 0.5
        if norm_left == 0 or norm_right == 0:
            return 0.0
        return float(dot / (norm_left * norm_right))


def build_document_index_service(
    documents_db_path: Path,
    audit_db_path: Path,
    documents_root: Path,
    *,
    rag_config: RagConfig | None = None,
    clock: Callable[[], datetime] | None = None,
    vector_store: FakeVectorStoreRepository | None = None,
) -> tuple[
    DocumentIndexService,
    FakeEmbeddingProvider,
    FakeVectorStoreRepository,
    SqliteAuditRepository,
    SqliteDocumentIndexRepository,
]:
    """Compose a real DocumentIndexService around deterministic fakes."""
    effective_clock = clock or (lambda: datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    provider = FakeEmbeddingProvider()
    provider_factory = EmbeddingProviderFactory()
    provider_factory.register(EmbeddingProviderType.OPENAI_COMPATIBLE, lambda _c, _k: provider)

    selected_vector_store = vector_store or FakeVectorStoreRepository()
    repository = SqliteDocumentIndexRepository(documents_db_path)
    repository.initialize()

    audit_repository = SqliteAuditRepository(audit_db_path)
    audit_repository.initialize()
    audit = AuditService(audit_repository, AuditConfig())

    config = rag_config or RagConfig(
        enabled=True,
        documents_path=str(documents_root),
        embedding_provider=EMBEDDING_PROVIDER_CONFIG,
    )
    service = DocumentIndexService(
        config=config,
        repository=repository,
        vector_store=selected_vector_store,
        embedding_provider_factory=provider_factory,
        environment={"EMBEDDING_API_KEY": "unit-test-embedding-key"},
        audit=audit,
        clock=effective_clock,
    )
    return service, provider, selected_vector_store, audit_repository, repository


def build_document_search_service(
    audit_db_path: Path,
    *,
    vector_store: FakeVectorStoreRepository | None = None,
    provider: FakeEmbeddingProvider | None = None,
    rag_config: RagConfig | None = None,
) -> tuple[
    DocumentSearchService,
    FakeEmbeddingProvider,
    FakeVectorStoreRepository,
    SqliteAuditRepository,
]:
    """Compose a real DocumentSearchService around deterministic fakes."""
    selected_vector_store = vector_store or FakeVectorStoreRepository()
    selected_provider = provider or FakeEmbeddingProvider()
    provider_factory = EmbeddingProviderFactory()
    provider_factory.register(
        EmbeddingProviderType.OPENAI_COMPATIBLE,
        lambda _c, _k: selected_provider,
    )

    audit_repository = SqliteAuditRepository(audit_db_path)
    audit_repository.initialize()
    audit = AuditService(audit_repository, AuditConfig())

    config = rag_config or RagConfig(enabled=True, embedding_provider=EMBEDDING_PROVIDER_CONFIG)
    service = DocumentSearchService(
        config=config,
        vector_store=selected_vector_store,
        embedding_provider_factory=provider_factory,
        environment={"EMBEDDING_API_KEY": "unit-test-embedding-key"},
        audit=audit,
    )
    return service, selected_provider, selected_vector_store, audit_repository
