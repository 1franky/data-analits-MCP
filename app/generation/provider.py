"""Contract implemented by LLM completion providers."""

from abc import ABC, abstractmethod

from app.models.generation import LlmCompletionRequest, LlmCompletionResponse


class LlmProvider(ABC):
    """Stateless request/response contract for chat-style LLM completions."""

    @abstractmethod
    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResponse:
        """Return one completion for a provider-agnostic chat request."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release any transport resources held by the provider."""
        raise NotImplementedError
