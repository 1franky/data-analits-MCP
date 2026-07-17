"""MCP tools for document indexing and semantic search."""

from typing import Annotated

from pydantic import Field

from app.container import get_document_index_service, get_document_search_service
from app.models.rag import (
    DeleteIndexedDocumentResult,
    ListIndexedDocumentsResult,
    RefreshDocumentIndexResult,
    SearchDocumentsResult,
)


def search_documents(
    query: Annotated[str, Field(min_length=1, max_length=2_000)],
    connection_id: str | None = None,
    domain: str | None = None,
    max_results: Annotated[int, Field(ge=1, le=100)] | None = None,
) -> SearchDocumentsResult:
    """Retrieve the most relevant cached document chunks for a query."""
    return get_document_search_service().search(query, connection_id, domain, max_results)


def list_indexed_documents(
    connection_id: str | None = None,
    domain: str | None = None,
) -> ListIndexedDocumentsResult:
    """List indexed documents, optionally restricted to connection and/or domain."""
    return get_document_index_service().list_documents(connection_id, domain)


def refresh_document_index(source: str | None = None) -> RefreshDocumentIndexResult:
    """Reindex a single file, or scan the documents directory completely."""
    return get_document_index_service().refresh(source)


def delete_indexed_document(document_id: str) -> DeleteIndexedDocumentResult:
    """Remove one document from the vector store and its cached metadata."""
    return get_document_index_service().delete_document(document_id)
