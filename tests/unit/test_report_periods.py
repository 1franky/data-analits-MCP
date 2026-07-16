"""Tests for deterministic, LLM-free resolution of relative report periods."""

from datetime import date

import pytest

from app.exceptions import ReportPeriodInvalidError
from app.models.reporting import ReportPeriodKeyword
from app.reporting.periods import (
    augment_question_with_period,
    detect_period_keyword,
    resolve_period,
)

REFERENCE_DATE = date(2026, 7, 16)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("dame las ventas de hoy", ReportPeriodKeyword.TODAY),
        ("ventas de esta semana", ReportPeriodKeyword.THIS_WEEK),
        ("ventas de la semana pasada", ReportPeriodKeyword.LAST_WEEK),
        ("ventas de este mes", ReportPeriodKeyword.THIS_MONTH),
        ("dame las ventas del mes pasado", ReportPeriodKeyword.LAST_MONTH),
        ("ventas de los últimos 7 días", ReportPeriodKeyword.LAST_7_DAYS),
        ("sales for the last 7 days", ReportPeriodKeyword.LAST_7_DAYS),
        ("ventas de los últimos 30 días", ReportPeriodKeyword.LAST_30_DAYS),
        ("ventas de este trimestre", ReportPeriodKeyword.THIS_QUARTER),
        ("ventas del trimestre pasado", ReportPeriodKeyword.LAST_QUARTER),
        ("ventas de este año", ReportPeriodKeyword.THIS_YEAR),
        ("ventas del año pasado", ReportPeriodKeyword.LAST_YEAR),
        ("ventas en lo que va del año", ReportPeriodKeyword.YEAR_TO_DATE),
        ("dame todos los productos", ReportPeriodKeyword.NONE),
    ],
)
def test_detect_period_keyword_matches_relative_phrasing(
    question: str,
    expected: ReportPeriodKeyword,
) -> None:
    assert detect_period_keyword(question) is expected


@pytest.mark.parametrize(
    ("keyword", "expected_start", "expected_end"),
    [
        (ReportPeriodKeyword.TODAY, date(2026, 7, 16), date(2026, 7, 16)),
        (ReportPeriodKeyword.THIS_WEEK, date(2026, 7, 13), date(2026, 7, 19)),
        (ReportPeriodKeyword.LAST_WEEK, date(2026, 7, 6), date(2026, 7, 12)),
        (ReportPeriodKeyword.THIS_MONTH, date(2026, 7, 1), date(2026, 7, 31)),
        (ReportPeriodKeyword.LAST_MONTH, date(2026, 6, 1), date(2026, 6, 30)),
        (ReportPeriodKeyword.LAST_7_DAYS, date(2026, 7, 10), date(2026, 7, 16)),
        (ReportPeriodKeyword.LAST_30_DAYS, date(2026, 6, 17), date(2026, 7, 16)),
        (ReportPeriodKeyword.THIS_QUARTER, date(2026, 7, 1), date(2026, 9, 30)),
        (ReportPeriodKeyword.LAST_QUARTER, date(2026, 4, 1), date(2026, 6, 30)),
        (ReportPeriodKeyword.THIS_YEAR, date(2026, 1, 1), date(2026, 12, 31)),
        (ReportPeriodKeyword.LAST_YEAR, date(2025, 1, 1), date(2025, 12, 31)),
        (ReportPeriodKeyword.YEAR_TO_DATE, date(2026, 1, 1), date(2026, 7, 16)),
    ],
)
def test_resolve_period_computes_exact_date_ranges(
    keyword: ReportPeriodKeyword,
    expected_start: date,
    expected_end: date,
) -> None:
    period = resolve_period(keyword, REFERENCE_DATE)

    assert period.start_date == expected_start
    assert period.end_date == expected_end
    assert period.label != ""


def test_resolve_period_none_has_no_dates() -> None:
    period = resolve_period(ReportPeriodKeyword.NONE, REFERENCE_DATE)

    assert period.start_date is None
    assert period.end_date is None
    assert period.label == ""


def test_resolve_custom_period_requires_both_dates() -> None:
    with pytest.raises(ReportPeriodInvalidError):
        resolve_period(ReportPeriodKeyword.CUSTOM, REFERENCE_DATE, custom_start=date(2026, 1, 1))


def test_resolve_custom_period_with_explicit_range() -> None:
    period = resolve_period(
        ReportPeriodKeyword.CUSTOM,
        REFERENCE_DATE,
        custom_start=date(2026, 1, 1),
        custom_end=date(2026, 1, 31),
    )

    assert period.start_date == date(2026, 1, 1)
    assert period.end_date == date(2026, 1, 31)


def test_augment_question_with_period_appends_exact_range() -> None:
    period = resolve_period(ReportPeriodKeyword.LAST_MONTH, REFERENCE_DATE)

    augmented = augment_question_with_period("dame las ventas del mes pasado", period)

    assert "2026-06-01" in augmented
    assert "2026-06-30" in augmented


def test_augment_question_without_period_is_unchanged() -> None:
    period = resolve_period(ReportPeriodKeyword.NONE, REFERENCE_DATE)

    assert augment_question_with_period("dame todos los productos", period) == (
        "dame todos los productos"
    )
