"""Typed contracts for LLM-assisted SQL generation."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.contracts import VersionedToolResponse
from app.models.query import QueryExecutionResult, SqlValidationResult


class LlmProviderType(StrEnum):
    """Known LLM provider implementations."""

    OPENAI_COMPATIBLE = "openai_compatible"


class GenerationProviderConfig(BaseModel):
    """Validated, secret-free declaration of one LLM provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: LlmProviderType = LlmProviderType.OPENAI_COMPATIBLE
    base_url: Annotated[str, Field(min_length=1, max_length=2048)]
    api_key_env: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")]
    model: Annotated[str, Field(min_length=1, max_length=128)]
    timeout_seconds: Annotated[int, Field(ge=1, le=300)] = 30
    max_output_tokens: Annotated[int, Field(ge=16, le=8_192)] = 1_024
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.0
    json_mode: bool = True


class GenerationConfig(BaseModel):
    """Opt-in policy for LLM-assisted SQL generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    provider: GenerationProviderConfig | None = None
    max_context_tables: Annotated[int, Field(ge=1, le=200)] = 20
    max_definition_chars: Annotated[int, Field(ge=500, le=100_000)] = 8_000

    @model_validator(mode="after")
    def require_provider_when_enabled(self) -> Self:
        """Ensure an enabled generation policy always declares its provider."""
        if self.enabled and self.provider is None:
            raise ValueError("generation.enabled=true requiere declarar provider")
        return self


class LlmChatRole(StrEnum):
    """Roles accepted by the internal chat completion contract."""

    SYSTEM = "system"
    USER = "user"


class LlmChatMessage(BaseModel):
    """One message in a chat completion request."""

    model_config = ConfigDict(frozen=True)

    role: LlmChatRole
    content: str


class LlmCompletionRequest(BaseModel):
    """Provider-agnostic chat completion request."""

    model_config = ConfigDict(frozen=True)

    messages: tuple[LlmChatMessage, ...]
    max_output_tokens: int
    temperature: float
    json_mode: bool = True


class LlmCompletionResponse(BaseModel):
    """Provider-agnostic chat completion response."""

    model_config = ConfigDict(frozen=True)

    content: str
    finish_reason: str | None = None
    duration_ms: float


class GenerationOutcome(StrEnum):
    """Terminal outcome of one SQL generation attempt."""

    GENERATED = "generated"
    CLARIFICATION_REQUIRED = "clarification_required"
    GENERATION_FAILED = "generation_failed"


class GeneratedQuery(BaseModel):
    """SQL text produced by the LLM alongside its informative validation."""

    model_config = ConfigDict(frozen=True)

    sql: str
    dialect: str
    assumptions: tuple[str, ...] = ()
    validation: SqlValidationResult


class AmbiguityCandidate(BaseModel):
    """One catalog object offered to resolve an ambiguous term."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, serialize_by_alias=True)

    schema_name: str = Field(alias="schema")
    table: str
    column: str | None = None
    reason: str


class ClarificationRequired(BaseModel):
    """Structured request for the caller to disambiguate before generating SQL."""

    model_config = ConfigDict(frozen=True)

    ambiguous_term: str
    question: str
    candidates: tuple[AmbiguityCandidate, ...]


class GenerateSqlResult(VersionedToolResponse):
    """Structured outcome of the generate_sql use case."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    question: str
    outcome: GenerationOutcome
    generated: GeneratedQuery | None = None
    clarification: ClarificationRequired | None = None
    error_code: str | None = None
    message: str


class GenerateAndExecuteResult(VersionedToolResponse):
    """Structured outcome of the generate_and_execute_query use case."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    question: str
    outcome: GenerationOutcome
    generated: GeneratedQuery | None = None
    clarification: ClarificationRequired | None = None
    execution: QueryExecutionResult | None = None
    error_code: str | None = None
    message: str


class ExplanationOutcome(StrEnum):
    """Terminal outcome of one object-explanation attempt."""

    EXPLAINED = "explained"
    EXPLANATION_FAILED = "explanation_failed"


class ExplainObjectResult(VersionedToolResponse):
    """Structured outcome of the explain_database_object use case."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, serialize_by_alias=True)

    connection_id: str
    schema_name: str = Field(alias="schema")
    table: str | None = None
    object_type: Literal["procedure", "trigger"]
    name: str
    outcome: ExplanationOutcome
    purpose: str | None = None
    facts: tuple[str, ...] = ()
    inferences: tuple[str, ...] = ()
    referenced_tables: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    definition_truncated: bool = False
    error_code: str | None = None
    message: str
