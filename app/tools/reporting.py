"""MCP tools for LLM-assisted, natural-language report generation."""

from typing import Annotated

from pydantic import Field

from app.container import get_reporting_service
from app.models.reporting import GenerateReportResult, ReportFormat


def generate_report(
    connection_id: str,
    question: Annotated[str, Field(min_length=1, max_length=4_000)],
    format: ReportFormat,
    max_rows: Annotated[int, Field(ge=1, le=10_000)] | None = None,
) -> GenerateReportResult:
    """Generate SQL, execute it under full revalidation and export it inline."""
    return get_reporting_service().generate_report(
        connection_id=connection_id,
        question=question,
        format=format,
        max_rows=max_rows,
    )
