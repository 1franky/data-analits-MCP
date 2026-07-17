"""Contract implemented by embedding providers."""

from abc import ABC, abstractmethod

from app.models.rag import EmbeddingBatchResult


class EmbeddingProvider(ABC):
    """Stateless request/response contract for computing text embeddings."""

    @abstractmethod
    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        """Return one embedding vector per input text, in the same order."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release any transport resources held by the provider."""
        raise NotImplementedError
