"""OpenAI-compatible chat completions provider over HTTP."""

from time import perf_counter

import httpx
from pydantic import SecretStr

from app.exceptions import GenerationProviderError
from app.generation.provider import LlmProvider
from app.models.generation import (
    GenerationProviderConfig,
    LlmCompletionRequest,
    LlmCompletionResponse,
)


class OpenAiCompatibleProvider(LlmProvider):
    """Minimal client for OpenAI-compatible `/chat/completions` endpoints."""

    def __init__(self, config: GenerationProviderConfig, api_key: SecretStr) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
        )

    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResponse:
        """Call `/chat/completions` once, with no retries, and parse its content."""
        payload: dict[str, object] = {
            "model": self._config.model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        started_at = perf_counter()
        try:
            response = self._client.post("/chat/completions", json=payload)
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

        content, finish_reason = self._extract_choice(body)
        return LlmCompletionResponse(
            content=content,
            finish_reason=finish_reason,
            duration_ms=duration_ms,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    @staticmethod
    def _extract_choice(body: object) -> tuple[str, str | None]:
        try:
            choice = body["choices"][0]  # type: ignore[index]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError) as error:
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
