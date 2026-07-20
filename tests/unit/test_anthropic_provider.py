"""Tests for the native Anthropic provider using a mocked HTTP transport."""

import json

import httpx
import pytest
from pydantic import SecretStr

from app.exceptions import GenerationProviderError
from app.generation.anthropic_native import AnthropicProvider
from app.models.generation import (
    GenerationProviderConfig,
    LlmChatMessage,
    LlmChatRole,
    LlmCompletionRequest,
)


def _config() -> GenerationProviderConfig:
    return GenerationProviderConfig(
        base_url="http://llm.invalid",
        api_key_env="ANTHROPIC_API_KEY",
        model="test-model",
        timeout_seconds=5,
    )


def _request() -> LlmCompletionRequest:
    return LlmCompletionRequest(
        messages=(
            LlmChatMessage(role=LlmChatRole.SYSTEM, content="system prompt"),
            LlmChatMessage(role=LlmChatRole.USER, content="user question"),
        ),
        max_output_tokens=128,
        temperature=0.0,
        json_mode=True,
    )


def _provider_with_transport(handler: httpx.MockTransport) -> AnthropicProvider:
    provider = AnthropicProvider(_config(), SecretStr("unit-test-key"))
    provider._client.close()
    provider._client = httpx.Client(
        base_url=_config().base_url,
        transport=handler,
        headers={
            "x-api-key": "unit-test-key",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    return provider


def test_complete_sends_api_key_and_version_and_parses_content() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["x-api-key"] = request.headers.get("x-api-key")
        captured["anthropic-version"] = request.headers.get("anthropic-version")
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": '{"outcome": "generated"}'}],
                "stop_reason": "end_turn",
            },
        )

    provider = _provider_with_transport(httpx.MockTransport(handle))
    response = provider.complete(_request())

    assert response.content == '{"outcome": "generated"}'
    assert response.finish_reason == "end_turn"
    assert captured["x-api-key"] == "unit-test-key"
    assert captured["anthropic-version"] == "2023-06-01"
    provider.close()


def test_complete_sends_system_prompt_separate_from_user_message() -> None:
    captured_payload: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"},
        )

    provider = _provider_with_transport(httpx.MockTransport(handle))
    provider.complete(_request())

    assert captured_payload["system"] == "system prompt"
    assert captured_payload["messages"] == [{"role": "user", "content": "user question"}]
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


def test_complete_raises_on_response_without_text_block() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"content": [{"type": "tool_use", "id": "x"}], "stop_reason": "tool_use"},
        )

    provider = _provider_with_transport(httpx.MockTransport(handle))

    with pytest.raises(GenerationProviderError) as excinfo:
        provider.complete(_request())
    assert excinfo.value.code == "GENERATION_PROVIDER_INVALID_RESPONSE"
