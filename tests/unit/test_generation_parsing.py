"""Tests for parsing the LLM's JSON generation payload."""

import pytest

from app.exceptions import LlmGenerationParseError
from app.generation.parsing import parse_generation_payload


def test_parses_generated_outcome_with_assumptions() -> None:
    payload = parse_generation_payload(
        '{"outcome": "generated", "sql": "SELECT 1", "assumptions": ["ninguno"]}'
    )

    assert payload.outcome == "generated"
    assert payload.sql == "SELECT 1"
    assert payload.assumptions == ("ninguno",)


def test_parses_clarification_required_outcome_with_candidates() -> None:
    payload = parse_generation_payload(
        """
        {"outcome": "clarification_required", "clarification": {
            "ambiguous_term": "cliente",
            "question": "¿A qué tabla de cliente te refieres?",
            "candidates": [
                {"schema": "public", "table": "clientes", "column": null, "reason": "coincide"}
            ]
        }}
        """
    )

    assert payload.outcome == "clarification_required"
    assert payload.clarification is not None
    assert payload.clarification.candidates[0].table == "clientes"


def test_rejects_invalid_json() -> None:
    with pytest.raises(LlmGenerationParseError):
        parse_generation_payload("not json")


def test_rejects_generated_outcome_without_sql() -> None:
    with pytest.raises(LlmGenerationParseError):
        parse_generation_payload('{"outcome": "generated"}')


def test_rejects_clarification_required_without_clarification_block() -> None:
    with pytest.raises(LlmGenerationParseError):
        parse_generation_payload('{"outcome": "clarification_required"}')
