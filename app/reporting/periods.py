"""Deterministic resolution of relative reporting periods, without LLM involvement."""

import re
import unicodedata
from calendar import monthrange
from datetime import date, timedelta

from app.exceptions import ReportPeriodInvalidError
from app.models.reporting import ReportPeriod, ReportPeriodKeyword

_MONTH_NAMES_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

_PERIOD_PATTERNS: tuple[tuple[re.Pattern[str], ReportPeriodKeyword], ...] = (
    (re.compile(r"\bhoy\b"), ReportPeriodKeyword.TODAY),
    (re.compile(r"\b(semana pasada|la semana anterior)\b"), ReportPeriodKeyword.LAST_WEEK),
    (re.compile(r"\besta semana\b"), ReportPeriodKeyword.THIS_WEEK),
    (re.compile(r"\b(mes pasado|el mes anterior)\b"), ReportPeriodKeyword.LAST_MONTH),
    (re.compile(r"\beste mes\b"), ReportPeriodKeyword.THIS_MONTH),
    (re.compile(r"\b(ultimos?\s+7\s+dias|last\s+7\s+days)\b"), ReportPeriodKeyword.LAST_7_DAYS),
    (re.compile(r"\b(ultimos?\s+30\s+dias|last\s+30\s+days)\b"), ReportPeriodKeyword.LAST_30_DAYS),
    (
        re.compile(r"\b(trimestre pasado|el trimestre anterior)\b"),
        ReportPeriodKeyword.LAST_QUARTER,
    ),
    (re.compile(r"\beste trimestre\b"), ReportPeriodKeyword.THIS_QUARTER),
    (re.compile(r"\b(ano pasado|el ano anterior)\b"), ReportPeriodKeyword.LAST_YEAR),
    (
        re.compile(r"\b(en lo que va del ano|year to date|ytd)\b"),
        ReportPeriodKeyword.YEAR_TO_DATE,
    ),
    (re.compile(r"\beste ano\b"), ReportPeriodKeyword.THIS_YEAR),
)


def _normalize(text: str) -> str:
    """Lowercase and strip diacritics so accented and plain phrasing both match."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def detect_period_keyword(question: str) -> ReportPeriodKeyword:
    """Detect a relative period keyword from natural-language text, deterministically."""
    normalized = _normalize(question)
    for pattern, keyword in _PERIOD_PATTERNS:
        if pattern.search(normalized):
            return keyword
    return ReportPeriodKeyword.NONE


def _format_date_es(value: date) -> str:
    return f"{value.day} de {_MONTH_NAMES_ES[value.month]} de {value.year}"


def _label_for_range(start: date, end: date) -> str:
    if start == end:
        return _format_date_es(start)
    return f"{_format_date_es(start)} al {_format_date_es(end)}"


def _quarter_bounds(reference: date) -> tuple[date, date]:
    quarter_index = (reference.month - 1) // 3
    start_month = quarter_index * 3 + 1
    end_month = start_month + 2
    start = date(reference.year, start_month, 1)
    end = date(reference.year, end_month, monthrange(reference.year, end_month)[1])
    return start, end


def resolve_period(
    keyword: ReportPeriodKeyword,
    reference_date: date,
    custom_start: date | None = None,
    custom_end: date | None = None,
) -> ReportPeriod:
    """Resolve a relative keyword to an exact date range using stdlib arithmetic only."""
    if keyword is ReportPeriodKeyword.NONE:
        return ReportPeriod(keyword=keyword, label="")

    if keyword is ReportPeriodKeyword.CUSTOM:
        if custom_start is None or custom_end is None or custom_start > custom_end:
            raise ReportPeriodInvalidError()
        return ReportPeriod(
            keyword=keyword,
            start_date=custom_start,
            end_date=custom_end,
            label=_label_for_range(custom_start, custom_end),
        )

    start: date
    end: date
    if keyword is ReportPeriodKeyword.TODAY:
        start = end = reference_date
    elif keyword is ReportPeriodKeyword.THIS_WEEK:
        start = reference_date - timedelta(days=reference_date.weekday())
        end = start + timedelta(days=6)
    elif keyword is ReportPeriodKeyword.LAST_WEEK:
        this_week_start = reference_date - timedelta(days=reference_date.weekday())
        start = this_week_start - timedelta(days=7)
        end = this_week_start - timedelta(days=1)
    elif keyword is ReportPeriodKeyword.THIS_MONTH:
        start = reference_date.replace(day=1)
        end = reference_date.replace(day=monthrange(reference_date.year, reference_date.month)[1])
    elif keyword is ReportPeriodKeyword.LAST_MONTH:
        first_of_this_month = reference_date.replace(day=1)
        end = first_of_this_month - timedelta(days=1)
        start = end.replace(day=1)
    elif keyword is ReportPeriodKeyword.LAST_7_DAYS:
        start = reference_date - timedelta(days=6)
        end = reference_date
    elif keyword is ReportPeriodKeyword.LAST_30_DAYS:
        start = reference_date - timedelta(days=29)
        end = reference_date
    elif keyword is ReportPeriodKeyword.THIS_QUARTER:
        start, end = _quarter_bounds(reference_date)
    elif keyword is ReportPeriodKeyword.LAST_QUARTER:
        this_quarter_start, _this_quarter_end = _quarter_bounds(reference_date)
        start, end = _quarter_bounds(this_quarter_start - timedelta(days=1))
    elif keyword is ReportPeriodKeyword.THIS_YEAR:
        start = date(reference_date.year, 1, 1)
        end = date(reference_date.year, 12, 31)
    elif keyword is ReportPeriodKeyword.LAST_YEAR:
        start = date(reference_date.year - 1, 1, 1)
        end = date(reference_date.year - 1, 12, 31)
    elif keyword is ReportPeriodKeyword.YEAR_TO_DATE:
        start = date(reference_date.year, 1, 1)
        end = reference_date
    else:  # pragma: no cover - exhaustive over ReportPeriodKeyword
        raise AssertionError(f"Periodo no manejado: {keyword}")

    return ReportPeriod(
        keyword=keyword,
        start_date=start,
        end_date=end,
        label=_label_for_range(start, end),
    )


def augment_question_with_period(question: str, period: ReportPeriod) -> str:
    """Inject the exact resolved period into the question text, in plain language."""
    if period.keyword is ReportPeriodKeyword.NONE:
        return question
    return (
        f"{question}\n\n"
        f"Periodo exacto solicitado: {period.start_date} a {period.end_date} ({period.label})."
    )
