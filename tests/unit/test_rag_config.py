"""Tests for RagConfig validators."""

import pytest
from pydantic import ValidationError

from app.models.rag import EmbeddingProviderConfig, EmbeddingProviderType, RagConfig


def _provider() -> EmbeddingProviderConfig:
    return EmbeddingProviderConfig(
        type=EmbeddingProviderType.OPENAI_COMPATIBLE,
        base_url="http://embeddings.invalid/v1",
        api_key_env="EMBEDDING_API_KEY",
        model="test-embedding-model",
        dimensions=8,
    )


def test_enabled_without_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RagConfig(enabled=True)


def test_enabled_with_provider_is_accepted() -> None:
    config = RagConfig(enabled=True, embedding_provider=_provider())
    assert config.enabled is True


def test_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValidationError):
        RagConfig(chunk_size=100, chunk_overlap=100)


def test_overlap_smaller_than_chunk_size_is_accepted() -> None:
    config = RagConfig(chunk_size=100, chunk_overlap=50)
    assert config.chunk_overlap == 50
