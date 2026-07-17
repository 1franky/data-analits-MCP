"""Use case: retrieve relevant document chunks for a natural-language query."""

from collections.abc import Mapping
from time import perf_counter

from pydantic import SecretStr

from app.exceptions import RagNotConfiguredError, RagRequestError, SecretNotConfiguredError
from app.models.rag import EmbeddingProviderConfig, RagConfig, SearchDocumentsResult
from app.rag.embeddings.registry import EmbeddingProviderFactory
from app.repositories.vector_store import VectorStoreRepository
from app.services.audit import AuditService


class DocumentSearchService:
    """Retrieve the most relevant cached document chunks for a natural-language query."""

    def __init__(
        self,
        config: RagConfig,
        vector_store: VectorStoreRepository,
        embedding_provider_factory: EmbeddingProviderFactory,
        environment: Mapping[str, str],
        audit: AuditService,
    ) -> None:
        self._config = config
        self._vector_store = vector_store
        self._audit = audit
        self._provider = None
        if config.enabled:
            if config.embedding_provider is None:
                raise RagNotConfiguredError()
            api_key = self._secret_for(config.embedding_provider, environment)
            self._provider = embedding_provider_factory.create(config.embedding_provider, api_key)

    def search(
        self,
        query: str,
        connection_id: str | None = None,
        domain: str | None = None,
        max_results: int | None = None,
    ) -> SearchDocumentsResult:
        """Embed the query, retrieve the closest chunks and flag mixed origins."""
        if not self._config.enabled or self._provider is None:
            raise RagNotConfiguredError()
        normalized_query = query.strip()
        if not normalized_query:
            raise RagRequestError(
                code="RAG_QUERY_EMPTY",
                message="La búsqueda de documentos no puede estar vacía.",
            )

        limit = max_results or self._config.max_search_results
        if not 1 <= limit <= 100:
            raise RagRequestError(
                code="RAG_RESULT_LIMIT_ERROR",
                message="max_results debe estar entre 1 y 100.",
            )

        started_at = perf_counter()
        embedding_result = self._provider.embed((normalized_query,))
        query_vector = embedding_result.vectors[0]
        matches = self._vector_store.search(query_vector, connection_id, domain, limit)
        duration_ms = (perf_counter() - started_at) * 1_000

        connections_in_results = tuple(
            dict.fromkeys(match.metadata.connection_id for match in matches)
        )
        distinct_non_null = {value for value in connections_in_results if value is not None}
        mixed_connections_warning = connection_id is None and len(distinct_non_null) > 1

        self._audit.record_document_search(
            tool_name="search_documents",
            connection_id=connection_id,
            query=normalized_query,
            match_count=len(matches),
            duration_ms=duration_ms,
        )

        message = (
            "Los resultados combinan documentos de más de una conexión sin filtro explícito."
            if mixed_connections_warning
            else "Búsqueda completada."
        )
        return SearchDocumentsResult(
            query=normalized_query,
            connection_id=connection_id,
            domain=domain,
            matches=matches,
            connections_in_results=connections_in_results,
            mixed_connections_warning=mixed_connections_warning,
            message=message,
        )

    @staticmethod
    def _secret_for(
        provider: EmbeddingProviderConfig,
        environment: Mapping[str, str],
    ) -> SecretStr:
        secret = environment.get(provider.api_key_env)
        if secret is None or not secret.strip():
            raise SecretNotConfiguredError(provider.api_key_env)
        return SecretStr(secret)
