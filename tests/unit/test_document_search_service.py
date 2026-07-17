"""Tests for semantic document search."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.exceptions import RagNotConfiguredError, RagRequestError
from app.models.rag import DocumentChunk, DocumentMetadata, RagConfig
from tests.rag_fakes import FakeVectorStoreRepository, build_document_search_service


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


def _seed(
    vector_store: FakeVectorStoreRepository,
    document_id: str,
    text: str,
    vector: tuple[float, ...],
    **meta_overrides: object,
) -> None:
    metadata = _metadata(document_id=document_id, **meta_overrides)
    chunk = DocumentChunk(
        chunk_id=f"{document_id}:0",
        document_id=document_id,
        position=0,
        text=text,
        char_start=0,
        char_end=len(text),
    )
    vector_store.upsert_chunks(document_id, (chunk,), (vector,), metadata)


def test_search_returns_matches_with_score_and_origin(tmp_path: Path) -> None:
    vector_store = FakeVectorStoreRepository()
    service, provider, vector_store, _audit_repository = build_document_search_service(
        tmp_path / "audit.db",
        vector_store=vector_store,
    )
    query_vector = provider._vector_for("reglas de ventas")
    _seed(vector_store, "doc-1", "reglas de ventas", query_vector)

    result = service.search("reglas de ventas")

    assert len(result.matches) == 1
    assert result.matches[0].document_id == "doc-1"
    assert result.matches[0].score > 0.9
    assert result.matches[0].metadata.source == "connection=postgres-demo/domain=ventas/reglas.md"


def test_search_with_connection_filter_never_mixes(tmp_path: Path) -> None:
    vector_store = FakeVectorStoreRepository()
    service, provider, vector_store, _audit_repository = build_document_search_service(
        tmp_path / "audit.db",
        vector_store=vector_store,
    )
    vec_a = provider._vector_for("a")
    vec_b = provider._vector_for("b")
    _seed(vector_store, "doc-a", "a", vec_a, connection_id="postgres-demo")
    _seed(vector_store, "doc-b", "b", vec_b, connection_id="other-connection")

    result = service.search("a", connection_id="postgres-demo")

    assert {match.metadata.connection_id for match in result.matches} <= {"postgres-demo", None}
    assert result.mixed_connections_warning is False


def test_search_without_filter_flags_mixed_connections(tmp_path: Path) -> None:
    vector_store = FakeVectorStoreRepository()
    service, provider, vector_store, _audit_repository = build_document_search_service(
        tmp_path / "audit.db",
        vector_store=vector_store,
    )
    vec_query = provider._vector_for("query")
    _seed(vector_store, "doc-a", "query", vec_query, connection_id="postgres-demo")
    _seed(vector_store, "doc-b", "query", vec_query, connection_id="other-connection")

    result = service.search("query")

    assert result.mixed_connections_warning is True


def test_search_disabled_raises(tmp_path: Path) -> None:
    service, _provider, _vector_store, _audit_repository = build_document_search_service(
        tmp_path / "audit.db",
        rag_config=RagConfig(enabled=False),
    )
    with pytest.raises(RagNotConfiguredError):
        service.search("algo")


def test_search_empty_query_raises(tmp_path: Path) -> None:
    service, _provider, _vector_store, _audit_repository = build_document_search_service(
        tmp_path / "audit.db",
    )
    with pytest.raises(RagRequestError):
        service.search("   ")


def test_search_never_persists_query_text_in_audit(tmp_path: Path) -> None:
    vector_store = FakeVectorStoreRepository()
    service, provider, vector_store, audit_repository = build_document_search_service(
        tmp_path / "audit.db",
        vector_store=vector_store,
    )
    secret_query = "informacion confidencial de negocio"
    vec = provider._vector_for(secret_query)
    _seed(vector_store, "doc-1", "algo", vec)

    service.search(secret_query)

    records = audit_repository.list_records()
    assert records
    for record in records:
        assert secret_query not in record.model_dump_json()
