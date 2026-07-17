"""Integration tests against a disposable Docker Qdrant instance."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.rag import DocumentChunk, DocumentMetadata
from app.repositories.qdrant_vector_store import QdrantVectorStoreRepository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_QDRANT_INTEGRATION") != "1",
        reason="set RUN_QDRANT_INTEGRATION=1 with the Qdrant lab running",
    ),
]

_DIMENSIONS = 8


def _vector(axis: int) -> tuple[float, ...]:
    """Build a unit vector along one axis, so COSINE distance actually discriminates."""
    return tuple(1.0 if index == axis else 0.0 for index in range(_DIMENSIONS))


def _metadata(connection_id: str | None = None, domain: str | None = None) -> DocumentMetadata:
    return DocumentMetadata(
        document_id="doc-1",
        title="Documento de prueba",
        source="doc-1.md",
        connection_id=connection_id,
        domain=domain,
        document_type="documentation",
        indexed_at=datetime.now(UTC),
    )


def _chunks(document_id: str, count: int) -> tuple[DocumentChunk, ...]:
    return tuple(
        DocumentChunk(
            chunk_id=f"{document_id}:{position}",
            document_id=document_id,
            position=position,
            text=f"chunk {position}",
            char_start=position * 10,
            char_end=position * 10 + 10,
        )
        for position in range(count)
    )


@pytest.fixture
def repository() -> Iterator[QdrantVectorStoreRepository]:
    url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
    collection_name = f"test_{uuid4().hex}"
    repo = QdrantVectorStoreRepository(url=url, collection_name=collection_name, timeout_seconds=10)
    repo.initialize(dimensions=_DIMENSIONS)
    try:
        yield repo
    finally:
        repo._client.delete_collection(collection_name)
        repo.close()


def test_initialize_is_idempotent_for_matching_dimensions(
    repository: QdrantVectorStoreRepository,
) -> None:
    repository.initialize(dimensions=_DIMENSIONS)


def test_upsert_then_search_returns_the_matching_chunk(
    repository: QdrantVectorStoreRepository,
) -> None:
    document_id = "doc-1"
    chunks = _chunks(document_id, 2)
    vectors = (_vector(0), _vector(1))

    repository.upsert_chunks(document_id, chunks, vectors, _metadata())
    matches = repository.search(_vector(0), connection_id=None, domain=None, limit=5)

    assert {match.chunk_id for match in matches} == {"doc-1:0", "doc-1:1"}
    best = max(matches, key=lambda match: match.score)
    assert best.chunk_id == "doc-1:0"


def test_upsert_chunks_replaces_previous_chunks_for_the_document(
    repository: QdrantVectorStoreRepository,
) -> None:
    document_id = "doc-1"
    repository.upsert_chunks(
        document_id, _chunks(document_id, 5), tuple(_vector(0) for _ in range(5)), _metadata()
    )

    repository.upsert_chunks(
        document_id, _chunks(document_id, 2), tuple(_vector(0) for _ in range(2)), _metadata()
    )

    matches = repository.search(_vector(0), connection_id=None, domain=None, limit=10)
    assert {match.chunk_id for match in matches} == {"doc-1:0", "doc-1:1"}


def test_search_filters_by_connection_but_always_includes_global_documents(
    repository: QdrantVectorStoreRepository,
) -> None:
    repository.upsert_chunks(
        "doc-scoped",
        _chunks("doc-scoped", 1),
        (_vector(0),),
        _metadata(connection_id="postgres-demo"),
    )
    repository.upsert_chunks(
        "doc-other",
        _chunks("doc-other", 1),
        (_vector(0),),
        _metadata(connection_id="other-connection"),
    )
    repository.upsert_chunks(
        "doc-global",
        _chunks("doc-global", 1),
        (_vector(0),),
        _metadata(connection_id=None),
    )

    matches = repository.search(_vector(0), connection_id="postgres-demo", domain=None, limit=10)

    document_ids = {match.document_id for match in matches}
    assert "doc-scoped" in document_ids
    assert "doc-global" in document_ids
    assert "doc-other" not in document_ids


def test_delete_document_removes_every_chunk(repository: QdrantVectorStoreRepository) -> None:
    document_id = "doc-1"
    repository.upsert_chunks(
        document_id, _chunks(document_id, 3), tuple(_vector(0) for _ in range(3)), _metadata()
    )

    repository.delete_document(document_id)

    matches = repository.search(_vector(0), connection_id=None, domain=None, limit=10)
    assert matches == ()
