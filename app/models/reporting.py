"""Typed contracts for natural-language report generation and delivery."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.contracts import VersionedToolResponse
from app.models.generation import ClarificationRequired, GenerationOutcome


class ReportFormat(StrEnum):
    """File formats a report can be exported to."""

    XLSX = "xlsx"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"


class ReportPeriodKeyword(StrEnum):
    """Relative time periods resolvable without LLM assistance."""

    NONE = "none"
    CUSTOM = "custom"
    TODAY = "today"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    THIS_QUARTER = "this_quarter"
    LAST_QUARTER = "last_quarter"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"
    YEAR_TO_DATE = "year_to_date"


class ReportPeriod(BaseModel):
    """Exact date range resolved deterministically from a relative keyword."""

    model_config = ConfigDict(frozen=True)

    keyword: ReportPeriodKeyword
    start_date: date | None = None
    end_date: date | None = None
    label: str


class ReportingConfig(BaseModel):
    """Opt-in policy for inline report generation and delivery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    default_row_limit: Annotated[int, Field(ge=1, le=10_000)] = 1_000
    max_inline_bytes: Annotated[int, Field(ge=1_024, le=20_000_000)] = 5_000_000
    on_size_exceeded: Literal["truncate", "reject"] = "truncate"
    allowed_formats: tuple[ReportFormat, ...] = (
        ReportFormat.CSV,
        ReportFormat.JSON,
        ReportFormat.XLSX,
        ReportFormat.PDF,
    )


class ReportTruncation(BaseModel):
    """Explicit notice that a report was reduced to fit the inline size budget."""

    model_config = ConfigDict(frozen=True)

    truncated: bool
    reason: str | None = None
    rows_included: int
    rows_available: int | None = None


class ReportPayload(BaseModel):
    """Base64-encoded report file delivered inline in the MCP envelope."""

    model_config = ConfigDict(frozen=True)

    format: ReportFormat
    filename: str
    content_type: str
    content_base64: str
    size_bytes: int


class GenerateReportResult(VersionedToolResponse):
    """Structured outcome of the generate_report use case."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    question: str
    format: ReportFormat
    outcome: GenerationOutcome
    period: ReportPeriod | None = None
    applied_filters: tuple[str, ...] = ()
    generated_at: datetime
    row_count: int = 0
    is_empty: bool = False
    truncation: ReportTruncation | None = None
    payload: ReportPayload | None = None
    clarification: ClarificationRequired | None = None
    error_code: str | None = None
    message: str
