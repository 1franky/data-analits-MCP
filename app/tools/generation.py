"""MCP tools for LLM-assisted SQL generation and orchestrated execution."""

from typing import Annotated

from pydantic import Field

from app.container import get_generation_execution_service, get_generation_service
from app.models.generation import GenerateAndExecuteResult, GenerateSqlResult


def generate_sql(
    connection_id: str,
    question: Annotated[str, Field(min_length=1, max_length=4_000)],
) -> GenerateSqlResult:
    """Generate one validated SELECT from a natural-language question, without executing it."""
    return get_generation_service().generate_sql(connection_id, question)


def generate_and_execute_query(
    connection_id: str,
    question: Annotated[str, Field(min_length=1, max_length=4_000)],
    max_rows: Annotated[int, Field(ge=1, le=1_000_000)] | None = None,
    timeout_seconds: Annotated[int, Field(ge=1, le=3_600)] | None = None,
) -> GenerateAndExecuteResult:
    """Generate SQL and, only if it is executable, run it under full revalidation."""
    return get_generation_execution_service().generate_and_execute(
        connection_id=connection_id,
        question=question,
        max_rows=max_rows,
        timeout_seconds=timeout_seconds,
    )
