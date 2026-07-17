"""Composition root for application services."""

import hashlib
import os
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr

from app.adapters.document_factory import DocumentAdapterFactory
from app.adapters.document_registry import create_document_adapter_factory
from app.adapters.registry import create_adapter_factory
from app.config import ConnectionsConfigLoader
from app.exceptions import RagNotConfiguredError
from app.generation.factory import create_llm_provider_factory
from app.generation.registry import LlmProviderFactory
from app.models.connections import ConnectionsConfig
from app.rag.embeddings.factory import create_embedding_provider_factory
from app.rag.embeddings.registry import EmbeddingProviderFactory
from app.reporting.exporters.factory import create_report_exporter_factory
from app.reporting.exporters.registry import ReportExporterFactory
from app.reporting.service import ReportingService
from app.repositories import (
    AuditRepository,
    CatalogRepository,
    DocumentIndexRepository,
    QdrantVectorStoreRepository,
    SqliteAuditRepository,
    SqliteCatalogRepository,
    SqliteDocumentIndexRepository,
    VectorStoreRepository,
)
from app.scheduler import CatalogScheduler, DocumentIndexScheduler
from app.services import (
    AuditService,
    CatalogService,
    ConnectionService,
    DocumentIndexService,
    DocumentQueryExecutionService,
    DocumentQueryValidationService,
    DocumentSearchService,
    GenerationExecutionService,
    GenerationService,
    ObjectExplanationService,
    QueryExecutionService,
    QueryValidationService,
)


@lru_cache(maxsize=1)
def get_connections_config() -> ConnectionsConfig:
    """Load and cache validated process configuration."""
    config_path = Path(os.environ.get("CONNECTIONS_FILE", "connections.yaml"))
    return ConnectionsConfigLoader(config_path).load()


@lru_cache(maxsize=1)
def get_document_adapter_factory() -> DocumentAdapterFactory:
    """Build the isolated registry of implemented document adapters."""
    return create_document_adapter_factory()


@lru_cache(maxsize=1)
def get_connection_service() -> ConnectionService:
    """Build and cache the validated connection service for this process."""
    config = get_connections_config()
    service = ConnectionService(
        config=config,
        adapter_factory=create_adapter_factory(),
        document_adapter_factory=get_document_adapter_factory(),
        environment=os.environ,
    )
    service.validate_startup()
    return service


@lru_cache(maxsize=1)
def get_catalog_repository() -> CatalogRepository:
    """Build and initialize the configured metadata repository."""
    database_path = Path(os.environ.get("CATALOG_DB_PATH", "data/catalog.db"))
    repository = SqliteCatalogRepository(database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_catalog_service() -> CatalogService:
    """Build the catalog service from shared process dependencies."""
    return CatalogService(
        connections=get_connection_service(),
        repository=get_catalog_repository(),
        config=get_connections_config().catalog,
    )


@lru_cache(maxsize=1)
def get_catalog_scheduler() -> CatalogScheduler:
    """Build the single process-wide catalog scheduler."""
    service = get_catalog_service()
    config = service.config
    return CatalogScheduler(
        service=service,
        interval_seconds=config.refresh_interval_minutes * 60,
        refresh_on_startup=config.refresh_on_startup,
        enabled=config.enabled,
    )


@lru_cache(maxsize=1)
def get_audit_repository() -> AuditRepository:
    """Build and initialize the append-only query audit repository."""
    database_path = Path(os.environ.get("AUDIT_DB_PATH", "data/audit.db"))
    repository = SqliteAuditRepository(database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_audit_service() -> AuditService:
    """Build the privacy-preserving process audit service."""
    return AuditService(
        repository=get_audit_repository(),
        config=get_connections_config().audit,
    )


@lru_cache(maxsize=1)
def get_query_validation_service() -> QueryValidationService:
    """Build the stateless parser-backed SQL validator."""
    return QueryValidationService()


@lru_cache(maxsize=1)
def get_query_execution_service() -> QueryExecutionService:
    """Build the bounded query execution and explain service."""
    return QueryExecutionService(
        connections=get_connection_service(),
        validator=get_query_validation_service(),
        audit=get_audit_service(),
        policy=get_connections_config().query,
    )


@lru_cache(maxsize=1)
def get_llm_provider_factory() -> LlmProviderFactory:
    """Build the isolated registry of implemented LLM providers."""
    return create_llm_provider_factory()


@lru_cache(maxsize=1)
def get_generation_service() -> GenerationService:
    """Build the natural-language SQL generation service."""
    return GenerationService(
        connections=get_connection_service(),
        catalog=get_catalog_service(),
        provider_factory=get_llm_provider_factory(),
        validator=get_query_validation_service(),
        config=get_connections_config().generation,
        environment=os.environ,
        audit=get_audit_service(),
    )


@lru_cache(maxsize=1)
def get_generation_execution_service() -> GenerationExecutionService:
    """Build the generation-then-execution orchestration service."""
    return GenerationExecutionService(
        generation=get_generation_service(),
        execution=get_query_execution_service(),
    )


@lru_cache(maxsize=1)
def get_object_explanation_service() -> ObjectExplanationService:
    """Build the natural-language database object explanation service."""
    return ObjectExplanationService(
        catalog=get_catalog_service(),
        provider_factory=get_llm_provider_factory(),
        config=get_connections_config().generation,
        environment=os.environ,
        audit=get_audit_service(),
    )


@lru_cache(maxsize=1)
def get_report_exporter_factory() -> ReportExporterFactory:
    """Build the isolated registry of implemented report exporters."""
    return create_report_exporter_factory()


@lru_cache(maxsize=1)
def get_reporting_service() -> ReportingService:
    """Build the natural-language report generation service."""
    return ReportingService(
        generation_execution=get_generation_execution_service(),
        exporter_factory=get_report_exporter_factory(),
        config=get_connections_config().reporting,
        audit=get_audit_service(),
    )


@lru_cache(maxsize=1)
def get_embedding_provider_factory() -> EmbeddingProviderFactory:
    """Build the isolated registry of implemented embedding providers."""
    return create_embedding_provider_factory()


@lru_cache(maxsize=1)
def get_document_index_repository() -> DocumentIndexRepository:
    """Build and initialize the indexed document metadata repository."""
    database_path = Path(os.environ.get("DOCUMENTS_DB_PATH", "data/documents.db"))
    repository = SqliteDocumentIndexRepository(database_path)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_vector_store_repository() -> VectorStoreRepository:
    """Build and initialize the Qdrant-backed vector store repository."""
    rag_config = get_connections_config().rag
    provider_config = rag_config.embedding_provider
    if provider_config is None:
        raise RagNotConfiguredError()
    fingerprint = hashlib.sha256(
        f"{provider_config.type}:{provider_config.model}:{provider_config.dimensions}".encode()
    ).hexdigest()[:16]
    collection_name = f"{rag_config.vector_store.collection_name}_{fingerprint}"
    api_key_env = rag_config.vector_store.api_key_env
    api_key = None
    if api_key_env is not None:
        secret = os.environ.get(api_key_env)
        if secret is not None and secret.strip():
            api_key = SecretStr(secret)
    repository = QdrantVectorStoreRepository(
        url=rag_config.vector_store.url,
        collection_name=collection_name,
        timeout_seconds=rag_config.vector_store.timeout_seconds,
        api_key=api_key,
    )
    repository.initialize(dimensions=provider_config.dimensions)
    return repository


@lru_cache(maxsize=1)
def get_document_index_service() -> DocumentIndexService:
    """Build the document discovery, chunking and indexing service."""
    return DocumentIndexService(
        config=get_connections_config().rag,
        repository=get_document_index_repository(),
        vector_store=get_vector_store_repository(),
        embedding_provider_factory=get_embedding_provider_factory(),
        environment=os.environ,
        audit=get_audit_service(),
    )


@lru_cache(maxsize=1)
def get_document_search_service() -> DocumentSearchService:
    """Build the semantic document search service."""
    return DocumentSearchService(
        config=get_connections_config().rag,
        vector_store=get_vector_store_repository(),
        embedding_provider_factory=get_embedding_provider_factory(),
        environment=os.environ,
        audit=get_audit_service(),
    )


@lru_cache(maxsize=1)
def get_document_index_scheduler() -> DocumentIndexScheduler:
    """Build the single process-wide document index scheduler."""
    service = get_document_index_service()
    config = get_connections_config().rag
    return DocumentIndexScheduler(
        service=service,
        interval_seconds=config.refresh_interval_minutes * 60,
        refresh_on_startup=config.refresh_on_startup,
        enabled=config.enabled,
    )


@lru_cache(maxsize=1)
def get_document_query_validation_service() -> DocumentQueryValidationService:
    """Build the stateless allowlist-backed MongoDB query validator."""
    return DocumentQueryValidationService()


@lru_cache(maxsize=1)
def get_document_query_execution_service() -> DocumentQueryExecutionService:
    """Build the bounded MongoDB find/aggregate execution service."""
    return DocumentQueryExecutionService(
        connections=get_connection_service(),
        validator=get_document_query_validation_service(),
        audit=get_audit_service(),
        policy=get_connections_config().query,
    )
