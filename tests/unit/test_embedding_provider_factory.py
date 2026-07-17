"""Tests for registry-based embedding provider construction."""

from pydantic import SecretStr

from app.exceptions import EmbeddingProviderNotAvailableError
from app.models.rag import EmbeddingBatchResult, EmbeddingProviderConfig, EmbeddingProviderType
from app.rag.embeddings.provider import EmbeddingProvider
from app.rag.embeddings.registry import EmbeddingProviderFactory


class StubEmbeddingProvider(EmbeddingProvider):
    """Minimal concrete provider used to exercise the registry."""

    def __init__(self, config: EmbeddingProviderConfig, api_key: SecretStr) -> None:
        self.config = config
        self.api_key = api_key
        self.closed = False

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        return EmbeddingBatchResult(
            vectors=tuple((0.0,) for _ in texts),
            model="stub",
            dimensions=1,
            duration_ms=1.0,
        )

    def close(self) -> None:
        self.closed = True


def _provider_config() -> EmbeddingProviderConfig:
    return EmbeddingProviderConfig(
        base_url="http://embeddings.invalid/v1",
        api_key_env="EMBEDDING_API_KEY",
        model="test-model",
        dimensions=4,
    )


def test_factory_uses_registered_builder() -> None:
    factory = EmbeddingProviderFactory()
    factory.register(EmbeddingProviderType.OPENAI_COMPATIBLE, StubEmbeddingProvider)

    provider = factory.create(_provider_config(), SecretStr("unit-test-key"))

    assert isinstance(provider, StubEmbeddingProvider)
    assert provider.api_key.get_secret_value() == "unit-test-key"
    assert factory.supports(EmbeddingProviderType.OPENAI_COMPATIBLE) is True


def test_factory_rejects_unregistered_provider_type() -> None:
    factory = EmbeddingProviderFactory()

    try:
        factory.create(_provider_config(), SecretStr("unit-test-key"))
    except EmbeddingProviderNotAvailableError as error:
        assert error.code == "EMBEDDING_PROVIDER_NOT_AVAILABLE"
    else:
        raise AssertionError("EmbeddingProviderNotAvailableError was not raised")
    assert factory.supports(EmbeddingProviderType.OPENAI_COMPATIBLE) is False
