"""MCP tools for SQL validation, bounded reads and safe query plans."""

from time import perf_counter
from typing import Annotated

from pydantic import Field

from app.container import (
    get_audit_service,
    get_connection_service,
    get_query_execution_service,
    get_query_validation_service,
)
from app.models.audit import AuditOperation
from app.models.query import (
    QueryExecutionResult,
    QueryParameter,
    QueryPlanResult,
    SqlValidationResult,
)


def validate_sql(connection_id: str, sql: str) -> SqlValidationResult:
    """Parse and classify SQL for the selected connection without executing it."""
    started_at = perf_counter()
    config = get_connection_service().get_connection_config(connection_id)
    result = get_query_validation_service().validate(sql, config.type.value)
    get_audit_service().record(
        tool_name="validate_sql",
        connection_id=connection_id,
        operation=AuditOperation.VALIDATE,
        sql=sql,
        validation=result,
        executed=False,
        duration_ms=(perf_counter() - started_at) * 1_000,
        row_count=None,
    )
    return result


def execute_read_query(
    connection_id: str,
    sql: str,
    parameters: dict[str, QueryParameter] | None = None,
    max_rows: Annotated[int, Field(ge=1, le=1_000_000)] | None = None,
    timeout_seconds: Annotated[int, Field(ge=1, le=3_600)] | None = None,
) -> QueryExecutionResult:
    """Execute one validated SELECT under row, byte, timeout and concurrency limits."""
    return get_query_execution_service().execute(
        connection_id=connection_id,
        sql=sql,
        parameters=parameters,
        max_rows=max_rows,
        timeout_seconds=timeout_seconds,
    )


def explain_query(
    connection_id: str,
    sql: str,
    parameters: dict[str, QueryParameter] | None = None,
    timeout_seconds: Annotated[int, Field(ge=1, le=3_600)] | None = None,
) -> QueryPlanResult:
    """Return a JSON PostgreSQL plan for a SELECT without using ANALYZE."""
    return get_query_execution_service().explain(
        connection_id=connection_id,
        sql=sql,
        parameters=parameters,
        timeout_seconds=timeout_seconds,
    )
