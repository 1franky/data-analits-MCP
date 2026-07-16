"""Use case: resolve a period, generate+execute SQL, and export the result inline."""

import base64
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter

from app.exceptions import (
    ReportFormatNotSupportedError,
    ReportingNotConfiguredError,
    ReportTooLargeError,
)
from app.models.audit import AuditOperation
from app.models.generation import GenerationOutcome
from app.models.query import SqlValidationResult
from app.models.reporting import (
    GenerateReportResult,
    ReportFormat,
    ReportingConfig,
    ReportPayload,
    ReportPeriodKeyword,
    ReportTruncation,
)
from app.reporting.exporters.base import ReportData, ReportExporter
from app.reporting.exporters.registry import ReportExporterFactory
from app.reporting.periods import (
    augment_question_with_period,
    detect_period_keyword,
    resolve_period,
)
from app.services.audit import AuditService
from app.services.generation_execution import GenerationExecutionService

Clock = Callable[[], datetime]


class ReportingService:
    """Resolve a relative period, generate+execute SQL, and export the result inline."""

    def __init__(
        self,
        generation_execution: GenerationExecutionService,
        exporter_factory: ReportExporterFactory,
        config: ReportingConfig,
        audit: AuditService,
        clock: Clock | None = None,
    ) -> None:
        self._generation_execution = generation_execution
        self._exporter_factory = exporter_factory
        self._config = config
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(UTC))

    def generate_report(
        self,
        connection_id: str,
        question: str,
        format: ReportFormat,
        max_rows: int | None = None,
    ) -> GenerateReportResult:
        """Generate one report, or reflect why it could not be produced."""
        if not self._config.enabled:
            raise ReportingNotConfiguredError()
        if format not in self._config.allowed_formats:
            raise ReportFormatNotSupportedError(format.value)

        started_at = perf_counter()
        generated_at = self._clock()
        keyword = detect_period_keyword(question)
        period = resolve_period(keyword, generated_at.date())
        augmented_question = augment_question_with_period(question, period)
        applied_filters = (
            () if period.keyword is ReportPeriodKeyword.NONE else (f"Periodo: {period.label}",)
        )

        effective_max_rows = min(
            max_rows or self._config.default_row_limit,
            self._config.default_row_limit,
        )
        result = self._generation_execution.generate_and_execute(
            connection_id,
            augmented_question,
            max_rows=effective_max_rows,
        )
        execution = result.execution

        if result.outcome is not GenerationOutcome.GENERATED or execution is None:
            self._audit_report(
                connection_id=connection_id,
                question=question,
                started_at=started_at,
                sql=result.generated.sql if result.generated else None,
                outcome=result.outcome,
                validation=result.generated.validation if result.generated else None,
                executed=False,
                row_count=None,
                error_code=result.error_code,
            )
            return GenerateReportResult(
                connection_id=connection_id,
                question=question,
                format=format,
                outcome=result.outcome,
                period=period,
                generated_at=generated_at,
                clarification=result.clarification,
                error_code=result.error_code,
                message=result.message,
            )

        if not execution.executed:
            self._audit_report(
                connection_id=connection_id,
                question=question,
                started_at=started_at,
                sql=result.generated.sql if result.generated else None,
                outcome=result.outcome,
                validation=execution.validation,
                executed=False,
                row_count=None,
                error_code=execution.error_code,
            )
            return GenerateReportResult(
                connection_id=connection_id,
                question=question,
                format=format,
                outcome=result.outcome,
                period=period,
                generated_at=generated_at,
                error_code=execution.error_code,
                message=execution.message,
            )

        report_data = ReportData(
            columns=execution.columns,
            rows=execution.rows,
            title=f"Reporte: {question}",
            generated_at=generated_at,
            period_label=period.label or None,
            applied_filters=applied_filters,
        )
        exporter = self._exporter_factory.create(format)
        raw_bytes, truncation = self._export_within_budget(exporter, report_data)
        payload = ReportPayload(
            format=format,
            filename=f"reporte.{exporter.file_extension}",
            content_type=exporter.content_type,
            content_base64=base64.b64encode(raw_bytes).decode("ascii"),
            size_bytes=len(raw_bytes),
        )

        self._audit_report(
            connection_id=connection_id,
            question=question,
            started_at=started_at,
            sql=result.generated.sql if result.generated else None,
            outcome=result.outcome,
            validation=execution.validation,
            executed=True,
            row_count=truncation.rows_included,
            error_code=None,
        )
        message = (
            "Reporte generado y truncado por tamaño."
            if truncation.truncated
            else "Reporte generado."
        )
        return GenerateReportResult(
            connection_id=connection_id,
            question=question,
            format=format,
            outcome=result.outcome,
            period=period,
            applied_filters=applied_filters,
            generated_at=generated_at,
            row_count=truncation.rows_included,
            is_empty=truncation.rows_included == 0,
            truncation=truncation,
            payload=payload,
            message=message,
        )

    def _audit_report(
        self,
        *,
        connection_id: str,
        question: str,
        started_at: float,
        sql: str | None,
        outcome: GenerationOutcome,
        validation: SqlValidationResult | None,
        executed: bool,
        row_count: int | None,
        error_code: str | None,
    ) -> None:
        duration_ms = (perf_counter() - started_at) * 1_000
        self._audit.record_generation(
            tool_name="generate_report",
            connection_id=connection_id,
            operation=AuditOperation.REPORT,
            prompt=question,
            sql=sql,
            outcome=outcome,
            validation=validation,
            executed=executed,
            duration_ms=duration_ms,
            row_count=row_count,
            error_code=error_code,
        )

    def _export_within_budget(
        self,
        exporter: ReportExporter,
        data: ReportData,
    ) -> tuple[bytes, ReportTruncation]:
        """Export the report, truncating or rejecting it if it exceeds the size budget."""
        raw_budget = (self._config.max_inline_bytes * 3) // 4
        total_rows = len(data.rows)
        raw_bytes = exporter.export(data)
        if len(raw_bytes) <= raw_budget:
            return raw_bytes, ReportTruncation(
                truncated=False,
                rows_included=total_rows,
                rows_available=total_rows,
            )

        if self._config.on_size_exceeded == "reject":
            raise ReportTooLargeError()

        low, high = 0, total_rows - 1
        best: tuple[bytes, int] | None = None
        while low <= high:
            mid = (low + high) // 2
            candidate_data = data.model_copy(update={"rows": data.rows[:mid]})
            candidate_bytes = exporter.export(candidate_data)
            if len(candidate_bytes) <= raw_budget:
                best = (candidate_bytes, mid)
                low = mid + 1
            else:
                high = mid - 1

        if best is None:
            raise ReportTooLargeError()

        best_bytes, rows_included = best
        return best_bytes, ReportTruncation(
            truncated=True,
            reason="El reporte excede el tamaño máximo permitido; se redujeron las filas.",
            rows_included=rows_included,
            rows_available=total_rows,
        )
