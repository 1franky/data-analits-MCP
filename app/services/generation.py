"""Use case: translate a natural-language question into validated SQL."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from time import perf_counter

from pydantic import SecretStr

from app.exceptions import (
    GenerationNotConfiguredError,
    GenerationProviderError,
    GenerationRequestError,
    LlmGenerationParseError,
    SecretNotConfiguredError,
)
from app.generation.context import select_context_tables
from app.generation.parsing import LlmClarificationPayload, parse_generation_payload
from app.generation.prompting import build_system_prompt, build_user_prompt
from app.generation.provider import LlmProvider
from app.generation.registry import LlmProviderFactory
from app.models.audit import AuditOperation
from app.models.catalog import CatalogSnapshot
from app.models.generation import (
    AmbiguityCandidate,
    ClarificationRequired,
    GeneratedQuery,
    GenerateSqlResult,
    GenerationConfig,
    GenerationOutcome,
    GenerationProviderConfig,
    LlmChatMessage,
    LlmChatRole,
    LlmCompletionRequest,
)
from app.services.audit import AuditService
from app.services.catalog import CatalogService
from app.services.connections import ConnectionService
from app.services.query_validation import QueryValidationService

Clock = Callable[[], datetime]


class GenerationService:
    """Generate a single validated SQL statement from a natural-language question."""

    def __init__(
        self,
        connections: ConnectionService,
        catalog: CatalogService,
        provider_factory: LlmProviderFactory,
        validator: QueryValidationService,
        config: GenerationConfig,
        environment: Mapping[str, str],
        audit: AuditService,
        clock: Clock | None = None,
    ) -> None:
        self._connections = connections
        self._catalog = catalog
        self._validator = validator
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

    def generate_sql(self, connection_id: str, question: str) -> GenerateSqlResult:
        """Generate one validated SQL statement or a structured clarification."""
        if not self._config.enabled or self._provider is None or self._provider_config is None:
            raise GenerationNotConfiguredError()
        normalized_question = question.strip()
        if not normalized_question:
            raise GenerationRequestError(
                code="GENERATION_QUESTION_EMPTY",
                message="La pregunta en lenguaje natural no puede estar vacía.",
            )

        connection = self._connections.get_connection_config(connection_id)
        dialect = connection.type.value
        snapshot = self._catalog.get_snapshot(connection_id)
        context_tables = select_context_tables(
            snapshot,
            normalized_question,
            self._config.max_context_tables,
        )

        started_at = perf_counter()
        request = LlmCompletionRequest(
            messages=(
                LlmChatMessage(role=LlmChatRole.SYSTEM, content=build_system_prompt(dialect)),
                LlmChatMessage(
                    role=LlmChatRole.USER,
                    content=build_user_prompt(
                        normalized_question,
                        context_tables,
                        self._clock().date(),
                    ),
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
                normalized_question,
                started_at,
                error.code,
                error.message,
            )

        try:
            payload = parse_generation_payload(completion.content)
        except LlmGenerationParseError as error:
            return self._failed(
                connection_id,
                normalized_question,
                started_at,
                error.code,
                error.message,
            )

        duration_ms = (perf_counter() - started_at) * 1_000

        if payload.outcome == "clarification_required":
            if payload.clarification is None:
                return self._failed(
                    connection_id,
                    normalized_question,
                    started_at,
                    "GENERATION_RESPONSE_PARSE_ERROR",
                    "La respuesta del proveedor LLM no se pudo interpretar como generación válida.",
                )
            clarification = self._ground_clarification(payload.clarification, snapshot)
            self._audit.record_generation(
                tool_name="generate_sql",
                connection_id=connection_id,
                operation=AuditOperation.GENERATE,
                prompt=normalized_question,
                sql=None,
                outcome=GenerationOutcome.CLARIFICATION_REQUIRED,
                validation=None,
                executed=False,
                duration_ms=duration_ms,
                row_count=None,
            )
            return GenerateSqlResult(
                connection_id=connection_id,
                question=normalized_question,
                outcome=GenerationOutcome.CLARIFICATION_REQUIRED,
                clarification=clarification,
                message="Se requiere aclaración antes de generar SQL.",
            )

        sql = payload.sql
        if sql is None:
            return self._failed(
                connection_id,
                normalized_question,
                started_at,
                "GENERATION_RESPONSE_PARSE_ERROR",
                "La respuesta del proveedor LLM no se pudo interpretar como generación válida.",
            )

        validation = self._validator.validate(sql, dialect)
        generated = GeneratedQuery(
            sql=sql,
            dialect=dialect,
            assumptions=payload.assumptions,
            validation=validation,
        )
        self._audit.record_generation(
            tool_name="generate_sql",
            connection_id=connection_id,
            operation=AuditOperation.GENERATE,
            prompt=normalized_question,
            sql=sql,
            outcome=GenerationOutcome.GENERATED,
            validation=validation,
            executed=False,
            duration_ms=duration_ms,
            row_count=None,
        )
        message = (
            "SQL generado y validado como ejecutable."
            if validation.executable
            else "SQL generado, pero bloqueado por la política de solo lectura."
        )
        return GenerateSqlResult(
            connection_id=connection_id,
            question=normalized_question,
            outcome=GenerationOutcome.GENERATED,
            generated=generated,
            message=message,
        )

    def _failed(
        self,
        connection_id: str,
        question: str,
        started_at: float,
        error_code: str,
        message: str,
    ) -> GenerateSqlResult:
        duration_ms = (perf_counter() - started_at) * 1_000
        self._audit.record_generation(
            tool_name="generate_sql",
            connection_id=connection_id,
            operation=AuditOperation.GENERATE,
            prompt=question,
            sql=None,
            outcome=GenerationOutcome.GENERATION_FAILED,
            validation=None,
            executed=False,
            duration_ms=duration_ms,
            row_count=None,
            error_code=error_code,
        )
        return GenerateSqlResult(
            connection_id=connection_id,
            question=question,
            outcome=GenerationOutcome.GENERATION_FAILED,
            error_code=error_code,
            message=message,
        )

    @staticmethod
    def _ground_clarification(
        payload: LlmClarificationPayload,
        snapshot: CatalogSnapshot,
    ) -> ClarificationRequired:
        """Discard candidates that do not exist verbatim in the cached snapshot."""
        known_tables = {(table.schema_name, table.name) for table in snapshot.tables}
        known_columns = {
            (table.schema_name, table.name, column.name)
            for table in snapshot.tables
            for column in table.columns
        }
        grounded: list[AmbiguityCandidate] = []
        for candidate in payload.candidates:
            table_key = (candidate.schema_name, candidate.table)
            if table_key not in known_tables:
                continue
            if (
                candidate.column is not None
                and (candidate.schema_name, candidate.table, candidate.column) not in known_columns
            ):
                continue
            grounded.append(candidate)
        return ClarificationRequired(
            ambiguous_term=payload.ambiguous_term,
            question=payload.question,
            candidates=tuple(grounded),
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
