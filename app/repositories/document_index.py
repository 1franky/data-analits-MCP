"""Replaceable persistence contract for indexed document metadata."""

from abc import ABC, abstractmethod

from app.models.rag import DocumentMetadata, IndexedDocumentSummary


class DocumentIndexRepository(ABC):
    """Persist indexing state and metadata for cached documents, without content."""

    @abstractmethod
    def initialize(self) -> None:
        """Create or migrate repository structures."""
        raise NotImplementedError

    @abstractmethod
    def upsert_document(
        self,
        metadata: DocumentMetadata,
        content_hash: str,
        chunk_count: int,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> None:
        """Replace one document's indexing state, keyed by its document_id."""
        raise NotImplementedError

    @abstractmethod
    def get_document_by_source(self, source: str) -> IndexedDocumentSummary | None:
        """Return the indexed state for one document, by its relative path."""
        raise NotImplementedError

    @abstractmethod
    def get_document_by_id(self, document_id: str) -> IndexedDocumentSummary | None:
        """Return the indexed state for one document, by its stable identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_documents(
        self,
        connection_id: str | None = None,
        domain: str | None = None,
    ) -> tuple[IndexedDocumentSummary, ...]:
        """List indexed documents, optionally filtered by connection and/or domain."""
        raise NotImplementedError

    @abstractmethod
    def list_sources(self) -> tuple[str, ...]:
        """Return every known document source path, for reconciling deletions."""
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: str) -> bool:
        """Remove one document's indexing state, returning whether it existed."""
        raise NotImplementedError
