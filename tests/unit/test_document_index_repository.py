"""Tests for the SQLite indexed document metadata repository."""

from datetime import UTC, datetime
from pathlib import Path

from app.models.rag import DocumentMetadata
from app.repositories.sqlite_document_index import SqliteDocumentIndexRepository


def _metadata(**overrides: object) -> DocumentMetadata:
    values: dict[str, object] = {
        "document_id": "doc-1",
        "title": "Reglas de ventas",
        "source": "connection=postgres-demo/domain=ventas/reglas.md",
        "connection_id": "postgres-demo",
        "domain": "ventas",
        "document_type": "documentation",
        "version": None,
        "indexed_at": datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return DocumentMetadata.model_validate(values)


def test_upsert_and_get_by_source(tmp_path: Path) -> None:
    repository = SqliteDocumentIndexRepository(tmp_path / "documents.db")
    repository.initialize()

    repository.upsert_document(_metadata(), "hash-1", 3, "test-model", 8)

    summary = repository.get_document_by_source("connection=postgres-demo/domain=ventas/reglas.md")
    assert summary is not None
    assert summary.metadata.document_id == "doc-1"
    assert summary.content_hash == "hash-1"
    assert summary.chunk_count == 3


def test_upsert_replaces_existing_document(tmp_path: Path) -> None:
    repository = SqliteDocumentIndexRepository(tmp_path / "documents.db")
    repository.initialize()

    repository.upsert_document(_metadata(), "hash-1", 3, "test-model", 8)
    repository.upsert_document(_metadata(), "hash-2", 5, "test-model", 8)

    summary = repository.get_document_by_id("doc-1")
    assert summary is not None
    assert summary.content_hash == "hash-2"
    assert summary.chunk_count == 5


def test_list_documents_filters_by_connection_and_domain(tmp_path: Path) -> None:
    repository = SqliteDocumentIndexRepository(tmp_path / "documents.db")
    repository.initialize()
    repository.upsert_document(_metadata(), "hash-1", 1, "m", 8)
    repository.upsert_document(
        _metadata(document_id="doc-2", source="global.md", connection_id=None, domain=None),
        "hash-2",
        1,
        "m",
        8,
    )

    assert len(repository.list_documents()) == 2

    filtered = repository.list_documents(connection_id="postgres-demo")
    assert {doc.metadata.document_id for doc in filtered} == {"doc-1"}

    filtered_domain = repository.list_documents(domain="ventas")
    assert {doc.metadata.document_id for doc in filtered_domain} == {"doc-1"}


def test_delete_document_returns_whether_it_existed(tmp_path: Path) -> None:
    repository = SqliteDocumentIndexRepository(tmp_path / "documents.db")
    repository.initialize()
    repository.upsert_document(_metadata(), "hash-1", 1, "m", 8)

    assert repository.delete_document("doc-1") is True
    assert repository.delete_document("doc-1") is False
    assert repository.get_document_by_id("doc-1") is None


def test_list_sources_returns_every_known_source(tmp_path: Path) -> None:
    repository = SqliteDocumentIndexRepository(tmp_path / "documents.db")
    repository.initialize()
    repository.upsert_document(_metadata(), "hash-1", 1, "m", 8)

    assert repository.list_sources() == ("connection=postgres-demo/domain=ventas/reglas.md",)
