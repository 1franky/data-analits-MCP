"""Typed contracts for document ingestion, embeddings and semantic search."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.contracts import VersionedToolResponse


class EmbeddingProviderType(StrEnum):
    """Known embedding provider implementations."""

    OPENAI_COMPATIBLE = "openai_compatible"


class EmbeddingProviderConfig(BaseModel):
    """Validated, secret-free declaration of one embedding provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: EmbeddingProviderType = EmbeddingProviderType.OPENAI_COMPATIBLE
    base_url: Annotated[str, Field(min_length=1, max_length=2048)]
    api_key_env: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")]
    model: Annotated[str, Field(min_length=1, max_length=128)]
    dimensions: Annotated[int, Field(ge=1, le=8_192)]
    timeout_seconds: Annotated[int, Field(ge=1, le=300)] = 30
    batch_size: Annotated[int, Field(ge=1, le=512)] = 64


class VectorStoreConfig(BaseModel):
    """Validated, secret-free declaration of the vector store connection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: Annotated[str, Field(min_length=1, max_length=2048)] = "http://qdrant:6333"
    collection_name: Annotated[str, Field(min_length=1, max_length=128)] = "documents"
    timeout_seconds: Annotated[int, Field(ge=1, le=300)] = 10
    api_key_env: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")] | None = None


class RagConfig(BaseModel):
    """Opt-in policy for document ingestion and semantic search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    documents_path: Annotated[str, Field(min_length=1, max_length=2048)] = "/app/documents"
    allowed_extensions: tuple[str, ...] = (".md", ".txt", ".sql", ".json", ".yaml", ".yml")
    chunk_size: Annotated[int, Field(ge=100, le=20_000)] = 1_000
    chunk_overlap: Annotated[int, Field(ge=0, le=5_000)] = 150
    max_document_bytes: Annotated[int, Field(ge=1_024, le=50_000_000)] = 5_000_000
    refresh_interval_minutes: Annotated[int, Field(ge=1, le=10_080)] = 60
    refresh_on_startup: bool = True
    max_search_results: Annotated[int, Field(ge=1, le=100)] = 20
    embedding_provider: EmbeddingProviderConfig | None = None
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)

    @model_validator(mode="after")
    def require_embedding_provider_when_enabled(self) -> Self:
        """Ensure an enabled RAG policy always declares its embedding provider."""
        if self.enabled and self.embedding_provider is None:
            raise ValueError("rag.enabled=true requiere declarar embedding_provider")
        return self

    @model_validator(mode="after")
    def require_overlap_smaller_than_chunk(self) -> Self:
        """Reject an overlap that would prevent chunking from making progress."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap debe ser menor que chunk_size")
        return self


class EmbeddingBatchResult(BaseModel):
    """Provider-agnostic embedding response for one batch of input texts."""

    model_config = ConfigDict(frozen=True)

    vectors: tuple[tuple[float, ...], ...]
    model: str
    dimensions: int
    duration_ms: float


class DocumentMetadata(BaseModel):
    """Descriptive metadata attached to one indexed document."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    title: str
    source: str
    connection_id: str | None = None
    domain: str | None = None
    document_type: Annotated[str, Field(min_length=1, max_length=64)] = "documentation"
    version: str | None = None
    indexed_at: datetime


class DocumentChunk(BaseModel):
    """One contiguous slice of a document's text, ready for embedding."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    position: int
    text: str
    char_start: int
    char_end: int


class DocumentIndexOutcome(StrEnum):
    """Terminal outcome of one document's indexing attempt."""

    INDEXED = "indexed"
    UNCHANGED = "unchanged"
    REMOVED = "removed"
    FAILED = "failed"


class IndexedDocumentSummary(BaseModel):
    """Cached indexing state for one document, without its content."""

    model_config = ConfigDict(frozen=True)

    metadata: DocumentMetadata
    content_hash: str
    chunk_count: int
    embedding_model: str
    embedding_dimensions: int


class DocumentIndexEntryResult(BaseModel):
    """Outcome of indexing one discovered source during a refresh."""

    model_config = ConfigDict(frozen=True)

    source: str
    document_id: str | None
    outcome: DocumentIndexOutcome
    chunk_count: int = 0
    error_code: str | None = None
    message: str


class RefreshDocumentIndexResult(VersionedToolResponse):
    """Structured outcome of the refresh_document_index use case."""

    model_config = ConfigDict(frozen=True)

    started_at: datetime
    completed_at: datetime
    entries: tuple[DocumentIndexEntryResult, ...]
    indexed_count: int
    unchanged_count: int
    removed_count: int
    failed_count: int
    message: str


class DeleteIndexedDocumentResult(VersionedToolResponse):
    """Structured outcome of the delete_indexed_document use case."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    deleted: bool
    error_code: str | None = None
    message: str


class ListIndexedDocumentsResult(VersionedToolResponse):
    """Structured outcome of the list_indexed_documents use case."""

    model_config = ConfigDict(frozen=True)

    documents: tuple[IndexedDocumentSummary, ...]
    total: int


class ChunkSearchMatch(BaseModel):
    """One retrieved chunk with its similarity score and document origin."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    chunk_id: str
    text: str
    score: float
    metadata: DocumentMetadata


class SearchDocumentsResult(VersionedToolResponse):
    """Structured outcome of the search_documents use case."""

    model_config = ConfigDict(frozen=True)

    query: str
    connection_id: str | None
    domain: str | None
    matches: tuple[ChunkSearchMatch, ...]
    connections_in_results: tuple[str | None, ...]
    mixed_connections_warning: bool
    message: str
