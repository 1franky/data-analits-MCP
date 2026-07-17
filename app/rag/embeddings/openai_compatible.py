"""OpenAI-compatible embeddings provider over HTTP."""

from time import perf_counter

import httpx
from pydantic import SecretStr

from app.exceptions import EmbeddingProviderError
from app.models.rag import EmbeddingBatchResult, EmbeddingProviderConfig
from app.rag.embeddings.provider import EmbeddingProvider


class OpenAiCompatibleEmbeddingProvider(EmbeddingProvider):
    """Minimal client for OpenAI-compatible `/embeddings` endpoints."""

    def __init__(self, config: EmbeddingProviderConfig, api_key: SecretStr) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
        )

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        """Call `/embeddings` once per batch, with no retries, in input order."""
        vectors: list[tuple[float, ...]] = []
        total_duration_ms = 0.0
        batch_size = self._config.batch_size
        for offset in range(0, len(texts), batch_size):
            batch = texts[offset : offset + batch_size]
            batch_vectors, duration_ms = self._embed_batch(batch)
            vectors.extend(batch_vectors)
            total_duration_ms += duration_ms
        return EmbeddingBatchResult(
            vectors=tuple(vectors),
            model=self._config.model,
            dimensions=self._config.dimensions,
            duration_ms=total_duration_ms,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def _embed_batch(self, batch: tuple[str, ...]) -> tuple[tuple[tuple[float, ...], ...], float]:
        payload: dict[str, object] = {"model": self._config.model, "input": list(batch)}

        started_at = perf_counter()
        try:
            response = self._client.post("/embeddings", json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as error:
            raise EmbeddingProviderError(
                code="EMBEDDING_PROVIDER_TIMEOUT",
                message="El proveedor de embeddings no respondió dentro del tiempo configurado.",
            ) from error
        except httpx.HTTPError as error:
            raise EmbeddingProviderError(
                code="EMBEDDING_PROVIDER_ERROR",
                message="El proveedor de embeddings devolvió un error de transporte.",
            ) from error
        duration_ms = (perf_counter() - started_at) * 1_000

        return self._extract_vectors(body, len(batch)), duration_ms

    @staticmethod
    def _extract_vectors(
        body: object,
        expected_count: int,
    ) -> tuple[tuple[float, ...], ...]:
        try:
            entries = body["data"]  # type: ignore[index]
            if not isinstance(entries, list) or len(entries) != expected_count:
                raise ValueError("unexpected embedding entry count")
            ordered = sorted(entries, key=lambda entry: entry["index"])
            vectors = tuple(
                tuple(float(value) for value in entry["embedding"]) for entry in ordered
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise EmbeddingProviderError(
                code="EMBEDDING_PROVIDER_INVALID_RESPONSE",
                message="La respuesta del proveedor de embeddings no tiene el formato esperado.",
            ) from error
        return vectors
