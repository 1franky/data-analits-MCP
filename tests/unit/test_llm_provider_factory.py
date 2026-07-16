"""Tests for registry-based LLM provider construction."""

from pydantic import SecretStr

from app.exceptions import GenerationProviderNotAvailableError
from app.generation.provider import LlmProvider
from app.generation.registry import LlmProviderFactory
from app.models.generation import (
    GenerationProviderConfig,
    LlmCompletionRequest,
    LlmCompletionResponse,
    LlmProviderType,
)


class StubLlmProvider(LlmProvider):
    """Minimal concrete provider used to exercise the registry."""

    def __init__(self, config: GenerationProviderConfig, api_key: SecretStr) -> None:
        self.config = config
        self.api_key = api_key
        self.closed = False

    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResponse:
        return LlmCompletionResponse(content="{}", duration_ms=1.0)

    def close(self) -> None:
        self.closed = True


def _provider_config() -> GenerationProviderConfig:
    return GenerationProviderConfig(
        base_url="http://llm.invalid/v1",
        api_key_env="LLM_API_KEY",
        model="test-model",
    )


def test_factory_uses_registered_builder() -> None:
    factory = LlmProviderFactory()
    factory.register(LlmProviderType.OPENAI_COMPATIBLE, StubLlmProvider)

    provider = factory.create(_provider_config(), SecretStr("unit-test-key"))

    assert isinstance(provider, StubLlmProvider)
    assert provider.api_key.get_secret_value() == "unit-test-key"
    assert factory.supports(LlmProviderType.OPENAI_COMPATIBLE) is True


def test_factory_rejects_unregistered_provider_type() -> None:
    factory = LlmProviderFactory()

    try:
        factory.create(_provider_config(), SecretStr("unit-test-key"))
    except GenerationProviderNotAvailableError as error:
        assert error.code == "GENERATION_PROVIDER_NOT_AVAILABLE"
    else:
        raise AssertionError("GenerationProviderNotAvailableError was not raised")
    assert factory.supports(LlmProviderType.OPENAI_COMPATIBLE) is False
