"""Replaceable persistence contract for chunk vectors and semantic search."""

from abc import ABC, abstractmethod

from app.models.rag import ChunkSearchMatch, DocumentChunk, DocumentMetadata


class VectorStoreRepository(ABC):
    """Store chunk embeddings and serve filtered semantic search."""

    @abstractmethod
    def initialize(self, dimensions: int) -> None:
        """Create or verify the underlying collection for a fixed vector size."""
        raise NotImplementedError

    @abstractmethod
    def upsert_chunks(
        self,
        document_id: str,
        chunks: tuple[DocumentChunk, ...],
        vectors: tuple[tuple[float, ...], ...],
        metadata: DocumentMetadata,
    ) -> None:
        """Replace the vectors for one document with a freshly embedded set."""
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """Remove every chunk vector belonging to one document."""
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_vector: tuple[float, ...],
        connection_id: str | None,
        domain: str | None,
        limit: int,
    ) -> tuple[ChunkSearchMatch, ...]:
        """Return the closest chunks, always including connection/domain-less documents."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release any transport resources held by the repository."""
        raise NotImplementedError
