"""Tests for the reporting use case: period resolution, export, and size limits."""

import base64
import json
from pathlib import Path

import pytest

from app.exceptions import (
    ReportFormatNotSupportedError,
    ReportingNotConfiguredError,
    ReportTooLargeError,
)
from app.models.generation import GenerationOutcome
from app.models.reporting import ReportFormat, ReportingConfig, ReportPeriodKeyword
from tests.generation_fakes import build_reporting_services


@pytest.mark.parametrize("report_format", list(ReportFormat))
def test_generate_report_succeeds_for_each_allowed_format(
    tmp_path: Path,
    report_format: ReportFormat,
) -> None:
    reporting, provider, audit_repository, _adapter = build_reporting_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    provider.responses.append(
        json.dumps({"outcome": "generated", "sql": "SELECT id, nombre FROM productos"})
    )

    result = reporting.generate_report(
        "postgres-demo", "dame las ventas del mes pasado", report_format
    )

    assert result.outcome is GenerationOutcome.GENERATED
    assert result.payload is not None
    assert result.payload.format is report_format
    assert result.row_count == 2
    assert result.is_empty is False
    assert result.truncation is not None
    assert result.truncation.truncated is False
    assert result.period is not None
    assert result.period.keyword is ReportPeriodKeyword.LAST_MONTH
    assert result.applied_filters
    raw = base64.b64decode(result.payload.content_base64)
    assert len(raw) == result.payload.size_bytes

    audit = audit_repository.list_records()[-1]
    question = "dame las ventas del mes pasado"
    persisted_bytes = (tmp_path / "audit.db").read_bytes()
    assert audit.operation.value == "report"
    assert question.encode() not in persisted_bytes


def test_generate_report_empty_result_is_not_an_error(tmp_path: Path) -> None:
    reporting, provider, _audit_repository, adapter = build_reporting_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    adapter.rows = ()
    provider.responses.append(
        json.dumps({"outcome": "generated", "sql": "SELECT id, nombre FROM productos"})
    )

    result = reporting.generate_report("postgres-demo", "dame los productos", ReportFormat.CSV)

    assert result.outcome is GenerationOutcome.GENERATED
    assert result.is_empty is True
    assert result.row_count == 0
    assert result.payload is not None


def test_generate_report_truncates_when_size_exceeds_budget(tmp_path: Path) -> None:
    reporting, provider, _audit_repository, adapter = build_reporting_services(
        tmp_path / "catalog.db",
        tmp_path / "audit.db",
        reporting_config=ReportingConfig(
            enabled=True,
            max_inline_bytes=1_024,
            default_row_limit=500,
        ),
    )
    adapter.rows = tuple((i, "x" * 200) for i in range(200))
    provider.responses.append(
        json.dumps({"outcome": "generated", "sql": "SELECT id, nombre FROM productos"})
    )

    result = reporting.generate_report("postgres-demo", "dame los productos", ReportFormat.CSV)

    assert result.payload is not None
    assert result.truncation is not None
    assert result.truncation.truncated is True
    assert result.truncation.rows_included < 200
    assert result.truncation.rows_available == 200
    assert result.row_count == result.truncation.rows_included


def test_generate_report_rejects_when_size_exceeds_budget_and_configured_to_reject(
    tmp_path: Path,
) -> None:
    reporting, provider, _audit_repository, adapter = build_reporting_services(
        tmp_path / "catalog.db",
        tmp_path / "audit.db",
        reporting_config=ReportingConfig(
            enabled=True,
            max_inline_bytes=1_024,
            default_row_limit=500,
            on_size_exceeded="reject",
        ),
    )
    adapter.rows = tuple((i, "x" * 200) for i in range(200))
    provider.responses.append(
        json.dumps({"outcome": "generated", "sql": "SELECT id, nombre FROM productos"})
    )

    with pytest.raises(ReportTooLargeError):
        reporting.generate_report("postgres-demo", "dame los productos", ReportFormat.CSV)


def test_generate_report_rejects_disallowed_format(tmp_path: Path) -> None:
    reporting, _provider, _audit_repository, _adapter = build_reporting_services(
        tmp_path / "catalog.db",
        tmp_path / "audit.db",
        reporting_config=ReportingConfig(enabled=True, allowed_formats=(ReportFormat.CSV,)),
    )

    with pytest.raises(ReportFormatNotSupportedError):
        reporting.generate_report("postgres-demo", "dame los productos", ReportFormat.PDF)


def test_generate_report_raises_when_not_enabled(tmp_path: Path) -> None:
    reporting, _provider, _audit_repository, _adapter = build_reporting_services(
        tmp_path / "catalog.db",
        tmp_path / "audit.db",
        reporting_config=ReportingConfig(enabled=False),
    )

    with pytest.raises(ReportingNotConfiguredError):
        reporting.generate_report("postgres-demo", "dame los productos", ReportFormat.CSV)


def test_generate_report_propagates_clarification_without_exporting(tmp_path: Path) -> None:
    reporting, provider, _audit_repository, adapter = build_reporting_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    provider.responses.append(
        json.dumps(
            {
                "outcome": "clarification_required",
                "clarification": {
                    "ambiguous_term": "cliente",
                    "question": "¿cuál tabla?",
                    "candidates": [],
                },
            }
        )
    )

    result = reporting.generate_report(
        "postgres-demo", "dame los datos del cliente", ReportFormat.CSV
    )

    assert result.outcome is GenerationOutcome.CLARIFICATION_REQUIRED
    assert result.payload is None
    assert result.clarification is not None
    assert adapter.execute_calls == 0


def test_generate_report_propagates_blocked_sql_without_exporting(tmp_path: Path) -> None:
    reporting, provider, _audit_repository, adapter = build_reporting_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    provider.responses.append(json.dumps({"outcome": "generated", "sql": "DELETE FROM productos"}))

    result = reporting.generate_report("postgres-demo", "borra los productos", ReportFormat.CSV)

    assert result.payload is None
    assert result.error_code == "SQL_VALIDATION_BLOCKED"
    assert adapter.execute_calls == 0
