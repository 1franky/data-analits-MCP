"""Default LLM provider registrations available in the running application."""

from app.generation.anthropic_native import AnthropicProvider
from app.generation.openai_compatible import OpenAiCompatibleProvider
from app.generation.registry import LlmProviderFactory
from app.models.generation import LlmProviderType


def create_llm_provider_factory() -> LlmProviderFactory:
    """Create an isolated registry with all implemented LLM providers."""
    factory = LlmProviderFactory()
    factory.register(
        provider_type=LlmProviderType.OPENAI_COMPATIBLE,
        builder=OpenAiCompatibleProvider,
    )
    factory.register(
        provider_type=LlmProviderType.ANTHROPIC,
        builder=AnthropicProvider,
    )
    return factory
