"""Use case: discover, chunk, embed and index documents from a read-only directory."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from pydantic import SecretStr

from app.exceptions import (
    DataPlatformError,
    DocumentNotFoundError,
    EmbeddingProviderError,
    RagNotConfiguredError,
    SecretNotConfiguredError,
    UnsupportedDocumentFormatError,
    VectorStoreError,
)
from app.models.rag import (
    DeleteIndexedDocumentResult,
    DocumentChunk,
    DocumentIndexEntryResult,
    DocumentIndexOutcome,
    DocumentMetadata,
    EmbeddingProviderConfig,
    ListIndexedDocumentsResult,
    RagConfig,
    RefreshDocumentIndexResult,
)
from app.rag.embeddings.registry import EmbeddingProviderFactory
from app.rag.ingestion.chunking import chunk_text
from app.rag.ingestion.parsers.factory import create_document_parser_factory
from app.rag.ingestion.parsers.registry import DocumentParserFactory
from app.rag.ingestion.path_metadata import PathDerivedMetadata, derive_metadata_from_path
from app.repositories.document_index import DocumentIndexRepository
from app.repositories.vector_store import VectorStoreRepository
from app.services.audit import AuditService

Clock = Callable[[], datetime]


class DocumentIndexService:
    """Discover, chunk, embed and index documents under a read-only directory."""

    def __init__(
        self,
        config: RagConfig,
        repository: DocumentIndexRepository,
        vector_store: VectorStoreRepository,
        embedding_provider_factory: EmbeddingProviderFactory,
        environment: Mapping[str, str],
        audit: AuditService,
        clock: Clock | None = None,
        parser_factory: DocumentParserFactory | None = None,
    ) -> None:
        self._config = config
        self._repository = repository
        self._vector_store = vector_store
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(UTC))
        self._parser_factory = parser_factory or create_document_parser_factory()
        self._provider = None
        if config.enabled:
            if config.embedding_provider is None:
                raise RagNotConfiguredError()
            api_key = self._secret_for(config.embedding_provider, environment)
            self._provider = embedding_provider_factory.create(config.embedding_provider, api_key)

    def refresh(self, source: str | None = None) -> RefreshDocumentIndexResult:
        """Reindex a single file, or scan documents_path completely when source is None."""
        if not self._config.enabled or self._provider is None:
            raise RagNotConfiguredError()

        started_at = self._clock()
        documents_root = Path(self._config.documents_path)
        entries: list[DocumentIndexEntryResult] = []

        if source is not None:
            file_path = documents_root / source
            extension = file_path.suffix.lower()
            if extension not in self._config.allowed_extensions:
                raise UnsupportedDocumentFormatError(extension)
            if not file_path.is_file():
                raise DocumentNotFoundError(source)
            entries.append(self._refresh_one(documents_root, source))
        else:
            discovered_sources: list[str] = []
            for file_path in self._discover_files(documents_root):
                relative_source = file_path.relative_to(documents_root).as_posix()
                discovered_sources.append(relative_source)
                entries.append(self._refresh_one(documents_root, relative_source))

            known_sources = set(self._repository.list_sources())
            for removed_source in sorted(known_sources - set(discovered_sources)):
                entries.append(self._remove_missing(removed_source))

        completed_at = self._clock()
        return RefreshDocumentIndexResult(
            started_at=started_at,
            completed_at=completed_at,
            entries=tuple(entries),
            indexed_count=self._count(entries, DocumentIndexOutcome.INDEXED),
            unchanged_count=self._count(entries, DocumentIndexOutcome.UNCHANGED),
            removed_count=self._count(entries, DocumentIndexOutcome.REMOVED),
            failed_count=self._count(entries, DocumentIndexOutcome.FAILED),
            message="Índice de documentos actualizado.",
        )

    def delete_document(self, document_id: str) -> DeleteIndexedDocumentResult:
        """Remove one document from the vector store and its cached metadata."""
        if not self._config.enabled:
            raise RagNotConfiguredError()
        existing = self._repository.get_document_by_id(document_id)
        if existing is None:
            raise DocumentNotFoundError(document_id)

        started_at = perf_counter()
        self._vector_store.delete_document(document_id)
        deleted = self._repository.delete_document(document_id)
        duration_ms = (perf_counter() - started_at) * 1_000
        self._audit.record_document_index(
            tool_name="delete_indexed_document",
            connection_id=existing.metadata.connection_id,
            document_type=existing.metadata.document_type,
            content_hash=existing.content_hash,
            outcome=DocumentIndexOutcome.REMOVED,
            chunk_count=0,
            duration_ms=duration_ms,
        )
        return DeleteIndexedDocumentResult(
            document_id=document_id,
            deleted=deleted,
            message="Documento eliminado del índice." if deleted else "El documento no existía.",
        )

    def list_documents(
        self,
        connection_id: str | None = None,
        domain: str | None = None,
    ) -> ListIndexedDocumentsResult:
        """List indexed documents, optionally filtered by connection and/or domain."""
        if not self._config.enabled:
            raise RagNotConfiguredError()
        documents = self._repository.list_documents(connection_id, domain)
        return ListIndexedDocumentsResult(documents=documents, total=len(documents))

    def _refresh_one(self, documents_root: Path, source: str) -> DocumentIndexEntryResult:
        started_at = perf_counter()
        file_path = documents_root / source
        extension = file_path.suffix.lower()
        path_metadata = derive_metadata_from_path(source)

        try:
            file_size = file_path.stat().st_size
        except OSError:
            return self._failed_entry(
                source,
                None,
                "DOCUMENT_NOT_FOUND",
                "El archivo ya no existe en disco.",
                started_at,
                path_metadata,
            )
        if file_size > self._config.max_document_bytes:
            return self._failed_entry(
                source,
                None,
                "DOCUMENT_TOO_LARGE",
                "El documento excede el tamaño máximo permitido.",
                started_at,
                path_metadata,
            )

        raw_bytes = file_path.read_bytes()
        try:
            parser = self._parser_factory.create(extension)
            text = parser.parse(raw_bytes)
        except (UnsupportedDocumentFormatError, DataPlatformError) as error:
            return self._failed_entry(
                source,
                None,
                error.code,
                error.message,
                started_at,
                path_metadata,
            )

        content_hash = sha256(text.encode("utf-8")).hexdigest()
        existing = self._repository.get_document_by_source(source)
        if existing is not None and existing.content_hash == content_hash:
            duration_ms = (perf_counter() - started_at) * 1_000
            self._audit.record_document_index(
                tool_name="refresh_document_index",
                connection_id=existing.metadata.connection_id,
                document_type=existing.metadata.document_type,
                content_hash=content_hash,
                outcome=DocumentIndexOutcome.UNCHANGED,
                chunk_count=existing.chunk_count,
                duration_ms=duration_ms,
            )
            return DocumentIndexEntryResult(
                source=source,
                document_id=existing.metadata.document_id,
                outcome=DocumentIndexOutcome.UNCHANGED,
                chunk_count=existing.chunk_count,
                message="El documento no cambió desde la última indexación.",
            )

        document_id = self._document_id_for(source)
        metadata = DocumentMetadata(
            document_id=document_id,
            title=path_metadata.title,
            source=source,
            connection_id=path_metadata.connection_id,
            domain=path_metadata.domain,
            document_type=path_metadata.document_type,
            version=path_metadata.version,
            indexed_at=self._clock(),
        )

        text_chunks = chunk_text(text, self._config.chunk_size, self._config.chunk_overlap)
        document_chunks = tuple(
            DocumentChunk(
                chunk_id=f"{document_id}:{position}",
                document_id=document_id,
                position=position,
                text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
            )
            for position, chunk in enumerate(text_chunks)
        )

        vectors: tuple[tuple[float, ...], ...] = ()
        embedding_model = ""
        embedding_dimensions = 0
        if document_chunks:
            assert self._provider is not None
            try:
                embeddings = self._provider.embed(tuple(chunk.text for chunk in document_chunks))
            except EmbeddingProviderError as error:
                return self._failed_entry(
                    source,
                    document_id,
                    error.code,
                    error.message,
                    started_at,
                    path_metadata,
                )
            if len(embeddings.vectors) != len(document_chunks):
                return self._failed_entry(
                    source,
                    document_id,
                    "EMBEDDING_PROVIDER_INVALID_RESPONSE",
                    "El proveedor de embeddings devolvió una cantidad de vectores inesperada.",
                    started_at,
                    path_metadata,
                )
            vectors = embeddings.vectors
            embedding_model = embeddings.model
            embedding_dimensions = embeddings.dimensions

        try:
            self._vector_store.upsert_chunks(document_id, document_chunks, vectors, metadata)
        except VectorStoreError as error:
            return self._failed_entry(
                source,
                document_id,
                error.code,
                error.message,
                started_at,
                path_metadata,
            )

        self._repository.upsert_document(
            metadata,
            content_hash,
            len(document_chunks),
            embedding_model,
            embedding_dimensions,
        )
        duration_ms = (perf_counter() - started_at) * 1_000
        self._audit.record_document_index(
            tool_name="refresh_document_index",
            connection_id=metadata.connection_id,
            document_type=metadata.document_type,
            content_hash=content_hash,
            outcome=DocumentIndexOutcome.INDEXED,
            chunk_count=len(document_chunks),
            duration_ms=duration_ms,
        )
        return DocumentIndexEntryResult(
            source=source,
            document_id=document_id,
            outcome=DocumentIndexOutcome.INDEXED,
            chunk_count=len(document_chunks),
            message="Documento indexado correctamente.",
        )

    def _remove_missing(self, source: str) -> DocumentIndexEntryResult:
        started_at = perf_counter()
        existing = self._repository.get_document_by_source(source)
        if existing is None:
            return DocumentIndexEntryResult(
                source=source,
                document_id=None,
                outcome=DocumentIndexOutcome.REMOVED,
                message="El documento ya no estaba indexado.",
            )
        self._vector_store.delete_document(existing.metadata.document_id)
        self._repository.delete_document(existing.metadata.document_id)
        duration_ms = (perf_counter() - started_at) * 1_000
        self._audit.record_document_index(
            tool_name="refresh_document_index",
            connection_id=existing.metadata.connection_id,
            document_type=existing.metadata.document_type,
            content_hash=existing.content_hash,
            outcome=DocumentIndexOutcome.REMOVED,
            chunk_count=0,
            duration_ms=duration_ms,
        )
        return DocumentIndexEntryResult(
            source=source,
            document_id=existing.metadata.document_id,
            outcome=DocumentIndexOutcome.REMOVED,
            message="Documento eliminado: ya no existe en disco.",
        )

    def _failed_entry(
        self,
        source: str,
        document_id: str | None,
        error_code: str,
        message: str,
        started_at: float,
        path_metadata: PathDerivedMetadata,
    ) -> DocumentIndexEntryResult:
        duration_ms = (perf_counter() - started_at) * 1_000
        self._audit.record_document_index(
            tool_name="refresh_document_index",
            connection_id=path_metadata.connection_id,
            document_type=path_metadata.document_type,
            content_hash=sha256(source.encode("utf-8")).hexdigest(),
            outcome=DocumentIndexOutcome.FAILED,
            chunk_count=0,
            duration_ms=duration_ms,
            error_code=error_code,
        )
        return DocumentIndexEntryResult(
            source=source,
            document_id=document_id,
            outcome=DocumentIndexOutcome.FAILED,
            error_code=error_code,
            message=message,
        )

    def _discover_files(self, documents_root: Path) -> list[Path]:
        if not documents_root.is_dir():
            return []
        allowed = set(self._config.allowed_extensions)
        return sorted(
            path
            for path in documents_root.rglob("*")
            if path.is_file() and path.suffix.lower() in allowed
        )

    @staticmethod
    def _count(
        entries: list[DocumentIndexEntryResult],
        outcome: DocumentIndexOutcome,
    ) -> int:
        return sum(1 for entry in entries if entry.outcome is outcome)

    @staticmethod
    def _document_id_for(source: str) -> str:
        return sha256(source.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _secret_for(
        provider: EmbeddingProviderConfig,
        environment: Mapping[str, str],
    ) -> SecretStr:
        secret = environment.get(provider.api_key_env)
        if secret is None or not secret.strip():
            raise SecretNotConfiguredError(provider.api_key_env)
        return SecretStr(secret)
