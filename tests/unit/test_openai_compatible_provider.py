"""Tests for the OpenAI-compatible provider using a mocked HTTP transport."""

import httpx
import pytest
from pydantic import SecretStr

from app.exceptions import GenerationProviderError
from app.generation.openai_compatible import OpenAiCompatibleProvider
from app.models.generation import (
    GenerationProviderConfig,
    LlmChatMessage,
    LlmChatRole,
    LlmCompletionRequest,
)


def _config() -> GenerationProviderConfig:
    return GenerationProviderConfig(
        base_url="http://llm.invalid/v1",
        api_key_env="LLM_API_KEY",
        model="test-model",
        timeout_seconds=5,
    )


def _request() -> LlmCompletionRequest:
    return LlmCompletionRequest(
        messages=(
            LlmChatMessage(role=LlmChatRole.SYSTEM, content="system"),
            LlmChatMessage(role=LlmChatRole.USER, content="user question"),
        ),
        max_output_tokens=128,
        temperature=0.0,
        json_mode=True,
    )


def _provider_with_transport(handler: httpx.MockTransport) -> OpenAiCompatibleProvider:
    provider = OpenAiCompatibleProvider(_config(), SecretStr("unit-test-key"))
    provider._client.close()
    provider._client = httpx.Client(
        base_url=_config().base_url,
        transport=handler,
        headers={"Authorization": "Bearer unit-test-key"},
    )
    return provider


def test_complete_sends_bearer_auth_and_json_mode_and_parses_content() -> None:
    captured_auth: dict[str, str | None] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured_auth["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"outcome": "generated"}'}, "finish_reason": "stop"}
                ]
            },
        )

    provider = _provider_with_transport(httpx.MockTransport(handle))
    response = provider.complete(_request())

    assert response.content == '{"outcome": "generated"}'
    assert response.finish_reason == "stop"
    assert captured_auth["authorization"] == "Bearer unit-test-key"
    provider.close()


def test_complete_raises_on_timeout() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = _provider_with_transport(httpx.MockTransport(handle))

    with pytest.raises(GenerationProviderError) as excinfo:
        provider.complete(_request())
    assert excinfo.value.code == "GENERATION_PROVIDER_TIMEOUT"


def test_complete_raises_on_http_status_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    provider = _provider_with_transport(httpx.MockTransport(handle))

    with pytest.raises(GenerationProviderError) as excinfo:
        provider.complete(_request())
    assert excinfo.value.code == "GENERATION_PROVIDER_ERROR"


def test_complete_raises_on_malformed_response_shape() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = _provider_with_transport(httpx.MockTransport(handle))

    with pytest.raises(GenerationProviderError) as excinfo:
        provider.complete(_request())
    assert excinfo.value.code == "GENERATION_PROVIDER_INVALID_RESPONSE"
