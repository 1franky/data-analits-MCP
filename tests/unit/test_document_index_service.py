"""Tests for document discovery, chunking, embedding and indexing."""

from pathlib import Path

import pytest

from app.exceptions import (
    DocumentNotFoundError,
    RagNotConfiguredError,
    UnsupportedDocumentFormatError,
)
from app.models.rag import DocumentIndexOutcome, RagConfig
from tests.rag_fakes import EMBEDDING_PROVIDER_CONFIG, build_document_index_service


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_refresh_indexes_new_documents(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    _write(
        documents_root,
        "connection=postgres-demo/domain=ventas/reglas.md",
        "Contenido de reglas de ventas.",
    )
    service, provider, _vector_store, _audit_repository, _repository = build_document_index_service(
        tmp_path / "documents.db", tmp_path / "audit.db", documents_root
    )

    result = service.refresh()

    assert result.indexed_count == 1
    assert result.entries[0].outcome is DocumentIndexOutcome.INDEXED
    assert len(provider.calls) == 1


def test_refresh_skips_unchanged_documents_without_recomputing_embeddings(
    tmp_path: Path,
) -> None:
    documents_root = tmp_path / "documents"
    _write(documents_root, "a.md", "contenido estable")
    service, provider, _vector_store, _audit_repository, _repository = build_document_index_service(
        tmp_path / "documents.db", tmp_path / "audit.db", documents_root
    )
    service.refresh()
    assert len(provider.calls) == 1

    result = service.refresh()

    assert result.unchanged_count == 1
    assert result.indexed_count == 0
    assert len(provider.calls) == 1


def test_refresh_reindexes_modified_documents(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    _write(documents_root, "a.md", "version uno")
    service, provider, _vector_store, _audit_repository, _repository = build_document_index_service(
        tmp_path / "documents.db", tmp_path / "audit.db", documents_root
    )
    service.refresh()
    _write(documents_root, "a.md", "version dos, con más contenido")

    result = service.refresh()

    assert result.indexed_count == 1
    assert len(provider.calls) == 2


def test_refresh_marks_missing_documents_as_removed(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    file_path = documents_root / "a.md"
    _write(documents_root, "a.md", "contenido")
    service, _provider, _vector_store, _audit_repository, _repository = (
        build_document_index_service(
            tmp_path / "documents.db", tmp_path / "audit.db", documents_root
        )
    )
    service.refresh()
    file_path.unlink()

    result = service.refresh()

    assert result.removed_count == 1
    assert result.entries[0].outcome is DocumentIndexOutcome.REMOVED


def test_refresh_single_source_reindexes_only_that_file(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    _write(documents_root, "a.md", "contenido a")
    _write(documents_root, "b.md", "contenido b")
    service, provider, _vector_store, _audit_repository, _repository = build_document_index_service(
        tmp_path / "documents.db", tmp_path / "audit.db", documents_root
    )

    result = service.refresh(source="a.md")

    assert len(result.entries) == 1
    assert result.entries[0].source == "a.md"
    assert len(provider.calls) == 1


def test_refresh_single_source_missing_file_raises(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    documents_root.mkdir()
    service, _provider, _vector_store, _audit_repository, _repository = (
        build_document_index_service(
            tmp_path / "documents.db", tmp_path / "audit.db", documents_root
        )
    )

    with pytest.raises(DocumentNotFoundError):
        service.refresh(source="missing.md")


def test_refresh_single_source_unsupported_extension_raises(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    _write(documents_root, "a.pdf", "not really a pdf")
    service, _provider, _vector_store, _audit_repository, _repository = (
        build_document_index_service(
            tmp_path / "documents.db", tmp_path / "audit.db", documents_root
        )
    )

    with pytest.raises(UnsupportedDocumentFormatError):
        service.refresh(source="a.pdf")


def test_disabled_config_raises_on_refresh(tmp_path: Path) -> None:
    service, _provider, _vector_store, _audit_repository, _repository = (
        build_document_index_service(
            tmp_path / "documents.db",
            tmp_path / "audit.db",
            tmp_path / "documents",
            rag_config=RagConfig(enabled=False),
        )
    )
    with pytest.raises(RagNotConfiguredError):
        service.refresh()


def test_document_too_large_is_marked_failed(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    _write(documents_root, "big.md", "x" * 2_000)
    service, _provider, _vector_store, _audit_repository, _repository = (
        build_document_index_service(
            tmp_path / "documents.db",
            tmp_path / "audit.db",
            documents_root,
            rag_config=RagConfig(
                enabled=True,
                documents_path=str(documents_root),
                embedding_provider=EMBEDDING_PROVIDER_CONFIG,
                max_document_bytes=1_024,
            ),
        )
    )

    result = service.refresh()

    assert result.failed_count == 1
    assert result.entries[0].error_code == "DOCUMENT_TOO_LARGE"


def test_delete_document_removes_from_repository_and_vector_store(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    _write(documents_root, "a.md", "contenido")
    service, _provider, vector_store, _audit_repository, _repository = build_document_index_service(
        tmp_path / "documents.db", tmp_path / "audit.db", documents_root
    )
    result = service.refresh()
    document_id = result.entries[0].document_id
    assert document_id is not None
    assert document_id in vector_store._entries

    delete_result = service.delete_document(document_id)

    assert delete_result.deleted is True
    assert document_id not in vector_store._entries


def test_delete_unknown_document_raises(tmp_path: Path) -> None:
    service, _provider, _vector_store, _audit_repository, _repository = (
        build_document_index_service(
            tmp_path / "documents.db", tmp_path / "audit.db", tmp_path / "documents"
        )
    )
    with pytest.raises(DocumentNotFoundError):
        service.delete_document("unknown")


def test_list_documents_reflects_indexed_state(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    _write(documents_root, "connection=postgres-demo/a.md", "contenido")
    service, _provider, _vector_store, _audit_repository, _repository = (
        build_document_index_service(
            tmp_path / "documents.db", tmp_path / "audit.db", documents_root
        )
    )
    service.refresh()

    result = service.list_documents()

    assert result.total == 1
    assert result.documents[0].metadata.connection_id == "postgres-demo"


def test_indexing_never_persists_document_content_in_audit(tmp_path: Path) -> None:
    documents_root = tmp_path / "documents"
    secret_content = "informacion confidencial sobre el negocio"
    _write(documents_root, "a.md", secret_content)
    service, _provider, _vector_store, audit_repository, _repository = build_document_index_service(
        tmp_path / "documents.db", tmp_path / "audit.db", documents_root
    )

    service.refresh()

    records = audit_repository.list_records()
    assert records
    for record in records:
        assert secret_content not in record.model_dump_json()
