"""Tests for the OpenAI-compatible embedding provider using a mocked HTTP transport."""

import json

import httpx
import pytest
from pydantic import SecretStr

from app.exceptions import EmbeddingProviderError
from app.models.rag import EmbeddingProviderConfig
from app.rag.embeddings.openai_compatible import OpenAiCompatibleEmbeddingProvider


def _config(batch_size: int = 2) -> EmbeddingProviderConfig:
    return EmbeddingProviderConfig(
        base_url="http://embeddings.invalid/v1",
        api_key_env="EMBEDDING_API_KEY",
        model="test-embedding-model",
        dimensions=3,
        timeout_seconds=5,
        batch_size=batch_size,
    )


def _provider_with_transport(
    handler: httpx.MockTransport,
    batch_size: int = 2,
) -> OpenAiCompatibleEmbeddingProvider:
    provider = OpenAiCompatibleEmbeddingProvider(_config(batch_size), SecretStr("unit-test-key"))
    provider._client.close()
    provider._client = httpx.Client(
        base_url=_config(batch_size).base_url,
        transport=handler,
        headers={"Authorization": "Bearer unit-test-key"},
    )
    return provider


def test_embed_batches_requests_and_reorders_by_index() -> None:
    calls: list[list[str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload["input"])
        data = [
            {"index": index, "embedding": [float(index), 0.0, 0.0]}
            for index in range(len(payload["input"]))
        ]
        return httpx.Response(200, json={"data": list(reversed(data))})

    provider = _provider_with_transport(httpx.MockTransport(handle), batch_size=2)
    result = provider.embed(("a", "b", "c"))

    assert len(calls) == 2
    assert result.vectors == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    provider.close()


def test_embed_raises_on_timeout() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = _provider_with_transport(httpx.MockTransport(handle))

    with pytest.raises(EmbeddingProviderError) as excinfo:
        provider.embed(("a",))
    assert excinfo.value.code == "EMBEDDING_PROVIDER_TIMEOUT"


def test_embed_raises_on_http_status_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    provider = _provider_with_transport(httpx.MockTransport(handle))

    with pytest.raises(EmbeddingProviderError) as excinfo:
        provider.embed(("a",))
    assert excinfo.value.code == "EMBEDDING_PROVIDER_ERROR"


def test_embed_raises_on_malformed_response_shape() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = _provider_with_transport(httpx.MockTransport(handle))

    with pytest.raises(EmbeddingProviderError) as excinfo:
        provider.embed(("a",))
    assert excinfo.value.code == "EMBEDDING_PROVIDER_INVALID_RESPONSE"


def test_embed_raises_on_vector_count_mismatch() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.0, 0.0, 0.0]}]})

    provider = _provider_with_transport(httpx.MockTransport(handle))

    with pytest.raises(EmbeddingProviderError) as excinfo:
        provider.embed(("a", "b"))
    assert excinfo.value.code == "EMBEDDING_PROVIDER_INVALID_RESPONSE"
