"""Registry-based embedding provider construction without vendor conditionals."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import SecretStr

from app.exceptions import EmbeddingProviderNotAvailableError
from app.models.rag import EmbeddingProviderConfig, EmbeddingProviderType
from app.rag.embeddings.provider import EmbeddingProvider

EmbeddingProviderBuilder = Callable[[EmbeddingProviderConfig, SecretStr], EmbeddingProvider]


@dataclass(frozen=True, slots=True)
class EmbeddingProviderRegistration:
    """Builder registered for one embedding provider type."""

    builder: EmbeddingProviderBuilder


class EmbeddingProviderFactory:
    """Create embedding providers through an explicit type registry."""

    def __init__(self) -> None:
        self._registrations: dict[EmbeddingProviderType, EmbeddingProviderRegistration] = {}

    def register(
        self,
        provider_type: EmbeddingProviderType,
        builder: EmbeddingProviderBuilder,
    ) -> None:
        """Register or replace one provider type builder."""
        self._registrations[provider_type] = EmbeddingProviderRegistration(builder)

    def supports(self, provider_type: EmbeddingProviderType) -> bool:
        """Return whether a builder is registered for a provider type."""
        return provider_type in self._registrations

    def create(
        self,
        config: EmbeddingProviderConfig,
        api_key: SecretStr,
    ) -> EmbeddingProvider:
        """Construct the registered provider for a validated declaration."""
        registration = self._registrations.get(config.type)
        if registration is None:
            raise EmbeddingProviderNotAvailableError(config.type.value)
        return registration.builder(config, api_key)
