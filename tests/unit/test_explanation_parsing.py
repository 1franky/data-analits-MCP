"""Tests for parsing the LLM object-explanation JSON payload."""

import json

import pytest

from app.exceptions import LlmExplanationParseError
from app.generation.explanation_parsing import parse_explanation_payload


def test_parses_full_valid_payload() -> None:
    raw = json.dumps(
        {
            "purpose": "Descuenta stock al registrar una venta.",
            "facts": ["Actualiza productos.stock", "Se dispara AFTER INSERT en ventas"],
            "inferences": ["Evita vender productos sin stock"],
            "referenced_tables": ["productos", "ventas"],
            "risks": ["No valida stock negativo"],
        }
    )

    payload = parse_explanation_payload(raw)

    assert payload.purpose == "Descuenta stock al registrar una venta."
    assert payload.facts == (
        "Actualiza productos.stock",
        "Se dispara AFTER INSERT en ventas",
    )
    assert payload.inferences == ("Evita vender productos sin stock",)
    assert payload.referenced_tables == ("productos", "ventas")
    assert payload.risks == ("No valida stock negativo",)


def test_parses_payload_with_only_required_field() -> None:
    payload = parse_explanation_payload(json.dumps({"purpose": "Resume ventas por cliente."}))

    assert payload.purpose == "Resume ventas por cliente."
    assert payload.facts == ()
    assert payload.inferences == ()
    assert payload.referenced_tables == ()
    assert payload.risks == ()


def test_invalid_json_raises_explanation_parse_error() -> None:
    with pytest.raises(LlmExplanationParseError) as excinfo:
        parse_explanation_payload("not json")

    assert excinfo.value.code == "EXPLANATION_RESPONSE_PARSE_ERROR"


def test_missing_required_field_raises_explanation_parse_error() -> None:
    with pytest.raises(LlmExplanationParseError):
        parse_explanation_payload(json.dumps({"facts": ["algo"]}))


def test_non_object_json_raises_explanation_parse_error() -> None:
    with pytest.raises(LlmExplanationParseError):
        parse_explanation_payload(json.dumps(["purpose", "facts"]))
