"""Default embedding provider registrations available in the running application."""

from app.models.rag import EmbeddingProviderType
from app.rag.embeddings.openai_compatible import OpenAiCompatibleEmbeddingProvider
from app.rag.embeddings.registry import EmbeddingProviderFactory


def create_embedding_provider_factory() -> EmbeddingProviderFactory:
    """Create an isolated registry with all implemented embedding providers."""
    factory = EmbeddingProviderFactory()
    factory.register(
        provider_type=EmbeddingProviderType.OPENAI_COMPATIBLE,
        builder=OpenAiCompatibleEmbeddingProvider,
    )
    return factory
