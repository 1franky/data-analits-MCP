"""Registry-based LLM provider construction without vendor conditionals."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import SecretStr

from app.exceptions import GenerationProviderNotAvailableError
from app.generation.provider import LlmProvider
from app.models.generation import GenerationProviderConfig, LlmProviderType

LlmProviderBuilder = Callable[[GenerationProviderConfig, SecretStr], LlmProvider]


@dataclass(frozen=True, slots=True)
class LlmProviderRegistration:
    """Builder registered for one LLM provider type."""

    builder: LlmProviderBuilder


class LlmProviderFactory:
    """Create LLM providers through an explicit type registry."""

    def __init__(self) -> None:
        self._registrations: dict[LlmProviderType, LlmProviderRegistration] = {}

    def register(
        self,
        provider_type: LlmProviderType,
        builder: LlmProviderBuilder,
    ) -> None:
        """Register or replace one provider type builder."""
        self._registrations[provider_type] = LlmProviderRegistration(builder)

    def supports(self, provider_type: LlmProviderType) -> bool:
        """Return whether a builder is registered for a provider type."""
        return provider_type in self._registrations

    def create(
        self,
        config: GenerationProviderConfig,
        api_key: SecretStr,
    ) -> LlmProvider:
        """Construct the registered provider for a validated declaration."""
        registration = self._registrations.get(config.type)
        if registration is None:
            raise GenerationProviderNotAvailableError(config.type.value)
        return registration.builder(config, api_key)
