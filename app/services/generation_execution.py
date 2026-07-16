"""Use case: execute the SQL generated from a natural-language question."""

from app.models.generation import GenerateAndExecuteResult, GenerationOutcome
from app.services.generation import GenerationService
from app.services.query_execution import QueryExecutionService


class GenerationExecutionService:
    """Orchestrate generation followed by full, independently revalidated execution."""

    def __init__(
        self,
        generation: GenerationService,
        execution: QueryExecutionService,
    ) -> None:
        self._generation = generation
        self._execution = execution

    def generate_and_execute(
        self,
        connection_id: str,
        question: str,
        max_rows: int | None = None,
        timeout_seconds: int | None = None,
    ) -> GenerateAndExecuteResult:
        """Generate SQL and, only if it was produced, run it under full validation."""
        generated_result = self._generation.generate_sql(connection_id, question)
        if (
            generated_result.outcome is not GenerationOutcome.GENERATED
            or generated_result.generated is None
        ):
            return GenerateAndExecuteResult(
                connection_id=generated_result.connection_id,
                question=generated_result.question,
                outcome=generated_result.outcome,
                clarification=generated_result.clarification,
                error_code=generated_result.error_code,
                message=generated_result.message,
            )

        execution = self._execution.execute(
            connection_id,
            generated_result.generated.sql,
            parameters=None,
            max_rows=max_rows,
            timeout_seconds=timeout_seconds,
            tool_name="generate_and_execute_query",
        )
        return GenerateAndExecuteResult(
            connection_id=generated_result.connection_id,
            question=generated_result.question,
            outcome=generated_result.outcome,
            generated=generated_result.generated,
            execution=execution,
            error_code=execution.error_code,
            message=execution.message,
        )
