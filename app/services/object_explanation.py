"""Use case: explain one cached procedure or trigger definition via LLM."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal

from pydantic import SecretStr

from app.exceptions import (
    GenerationNotConfiguredError,
    GenerationProviderError,
    GenerationRequestError,
    LlmExplanationParseError,
    SecretNotConfiguredError,
)
from app.generation.explanation_parsing import parse_explanation_payload
from app.generation.explanation_prompting import (
    build_explanation_system_prompt,
    build_explanation_user_prompt,
)
from app.generation.provider import LlmProvider
from app.generation.registry import LlmProviderFactory
from app.models.audit import AuditOperation
from app.models.generation import (
    ExplainObjectResult,
    ExplanationOutcome,
    GenerationConfig,
    GenerationOutcome,
    GenerationProviderConfig,
    LlmChatMessage,
    LlmChatRole,
    LlmCompletionRequest,
)
from app.services.audit import AuditService
from app.services.catalog import CatalogService

Clock = Callable[[], datetime]
ObjectType = Literal["procedure", "trigger"]


class ObjectExplanationService:
    """Explain one cached procedure or trigger definition in natural language."""

    def __init__(
        self,
        catalog: CatalogService,
        provider_factory: LlmProviderFactory,
        config: GenerationConfig,
        environment: Mapping[str, str],
        audit: AuditService,
        clock: Clock | None = None,
    ) -> None:
        self._catalog = catalog
        self._config = config
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(UTC))
        self._provider_config: GenerationProviderConfig | None = None
        self._provider: LlmProvider | None = None
        if config.enabled:
            if config.provider is None:
                raise GenerationNotConfiguredError()
            self._provider_config = config.provider
            api_key = self._secret_for(config.provider, environment)
            self._provider = provider_factory.create(config.provider, api_key)

    def explain_object(
        self,
        connection_id: str,
        schema: str,
        object_type: ObjectType,
        name: str,
        table: str | None = None,
    ) -> ExplainObjectResult:
        """Explain one procedure or trigger already present in the cached catalog."""
        if not self._config.enabled or self._provider is None or self._provider_config is None:
            raise GenerationNotConfiguredError()

        if object_type == "trigger" and table is None:
            raise GenerationRequestError(
                code="EXPLANATION_TABLE_REQUIRED",
                message="table es obligatorio para explicar un trigger.",
            )

        if object_type == "procedure":
            definition = self._catalog.get_procedure(connection_id, schema, name).definition
        else:
            assert table is not None
            definition = self._catalog.get_trigger(connection_id, schema, table, name).definition

        max_chars = self._config.max_definition_chars
        truncated = len(definition) > max_chars

        started_at = perf_counter()
        request = LlmCompletionRequest(
            messages=(
                LlmChatMessage(
                    role=LlmChatRole.SYSTEM,
                    content=build_explanation_system_prompt(),
                ),
                LlmChatMessage(
                    role=LlmChatRole.USER,
                    content=build_explanation_user_prompt(object_type, name, definition, max_chars),
                ),
            ),
            max_output_tokens=self._provider_config.max_output_tokens,
            temperature=self._provider_config.temperature,
            json_mode=self._provider_config.json_mode,
        )

        try:
            completion = self._provider.complete(request)
        except GenerationProviderError as error:
            return self._failed(
                connection_id,
                schema,
                object_type,
                name,
                table,
                truncated,
                started_at,
                error.code,
                error.message,
                definition,
            )

        try:
            payload = parse_explanation_payload(completion.content)
        except LlmExplanationParseError as error:
            return self._failed(
                connection_id,
                schema,
                object_type,
                name,
                table,
                truncated,
                started_at,
                error.code,
                error.message,
                definition,
            )

        duration_ms = (perf_counter() - started_at) * 1_000
        self._audit.record_generation(
            tool_name="explain_database_object",
            connection_id=connection_id,
            operation=AuditOperation.EXPLAIN_OBJECT,
            prompt=definition,
            sql=None,
            outcome=GenerationOutcome.GENERATED,
            validation=None,
            executed=False,
            duration_ms=duration_ms,
            row_count=None,
        )
        return ExplainObjectResult(
            connection_id=connection_id,
            schema=schema,
            table=table,
            object_type=object_type,
            name=name,
            outcome=ExplanationOutcome.EXPLAINED,
            purpose=payload.purpose,
            facts=payload.facts,
            inferences=payload.inferences,
            referenced_tables=payload.referenced_tables,
            risks=payload.risks,
            definition_truncated=truncated,
            message="Objeto explicado a partir de su definición real.",
        )

    def _failed(
        self,
        connection_id: str,
        schema: str,
        object_type: ObjectType,
        name: str,
        table: str | None,
        truncated: bool,
        started_at: float,
        error_code: str,
        message: str,
        definition: str,
    ) -> ExplainObjectResult:
        duration_ms = (perf_counter() - started_at) * 1_000
        self._audit.record_generation(
            tool_name="explain_database_object",
            connection_id=connection_id,
            operation=AuditOperation.EXPLAIN_OBJECT,
            prompt=definition,
            sql=None,
            outcome=GenerationOutcome.GENERATION_FAILED,
            validation=None,
            executed=False,
            duration_ms=duration_ms,
            row_count=None,
            error_code=error_code,
        )
        return ExplainObjectResult(
            connection_id=connection_id,
            schema=schema,
            table=table,
            object_type=object_type,
            name=name,
            outcome=ExplanationOutcome.EXPLANATION_FAILED,
            definition_truncated=truncated,
            error_code=error_code,
            message=message,
        )

    @staticmethod
    def _secret_for(
        provider: GenerationProviderConfig,
        environment: Mapping[str, str],
    ) -> SecretStr:
        secret = environment.get(provider.api_key_env)
        if secret is None or not secret.strip():
            raise SecretNotConfiguredError(provider.api_key_env)
        return SecretStr(secret)
