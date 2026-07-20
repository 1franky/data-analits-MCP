"""Native Anthropic Messages API provider over HTTP."""

from time import perf_counter

import httpx
from pydantic import SecretStr

from app.exceptions import GenerationProviderError
from app.generation.provider import LlmProvider
from app.models.generation import (
    GenerationProviderConfig,
    LlmChatRole,
    LlmCompletionRequest,
    LlmCompletionResponse,
)

_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(LlmProvider):
    """Minimal client for the native Anthropic `/v1/messages` endpoint."""

    def __init__(self, config: GenerationProviderConfig, api_key: SecretStr) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={
                "x-api-key": api_key.get_secret_value(),
                "anthropic-version": _ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
        )

    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResponse:
        """Call `/v1/messages` once, with no retries, and parse its content."""
        system_prompt = self._message_for(request, LlmChatRole.SYSTEM)
        user_prompt = self._message_for(request, LlmChatRole.USER)
        payload: dict[str, object] = {
            "model": self._config.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }

        started_at = perf_counter()
        try:
            response = self._client.post("/v1/messages", json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as error:
            raise GenerationProviderError(
                code="GENERATION_PROVIDER_TIMEOUT",
                message="El proveedor LLM no respondió dentro del tiempo configurado.",
            ) from error
        except httpx.HTTPError as error:
            raise GenerationProviderError(
                code="GENERATION_PROVIDER_ERROR",
                message="El proveedor LLM devolvió un error de transporte.",
            ) from error
        duration_ms = (perf_counter() - started_at) * 1_000

        content, finish_reason = self._extract_message(body)
        return LlmCompletionResponse(
            content=content,
            finish_reason=finish_reason,
            duration_ms=duration_ms,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    @staticmethod
    def _message_for(request: LlmCompletionRequest, role: LlmChatRole) -> str:
        for message in request.messages:
            if message.role is role:
                return message.content
        raise GenerationProviderError(
            code="GENERATION_PROVIDER_INVALID_RESPONSE",
            message=f"La petición no incluye un mensaje de rol '{role.value}'.",
        )

    @staticmethod
    def _extract_message(body: object) -> tuple[str, str | None]:
        try:
            blocks = body["content"]  # type: ignore[index]
            text_block = next(
                block for block in blocks if isinstance(block, dict) and block.get("type") == "text"
            )
            content = text_block["text"]
            finish_reason = body["stop_reason"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError, StopIteration) as error:
            raise GenerationProviderError(
                code="GENERATION_PROVIDER_INVALID_RESPONSE",
                message="La respuesta del proveedor LLM no tiene el formato esperado.",
            ) from error
        if not isinstance(content, str):
            raise GenerationProviderError(
                code="GENERATION_PROVIDER_INVALID_RESPONSE",
                message="La respuesta del proveedor LLM no tiene el formato esperado.",
            )
        return content, finish_reason if isinstance(finish_reason, str) else None
