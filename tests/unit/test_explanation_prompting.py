"""Tests for deterministic database object explanation prompts."""

from app.generation.explanation_prompting import (
    build_explanation_system_prompt,
    build_explanation_user_prompt,
)


def test_system_prompt_enforces_facts_versus_inferences() -> None:
    prompt = build_explanation_system_prompt()

    assert "facts" in prompt
    assert "inferences" in prompt
    assert "JSON" in prompt


def test_user_prompt_includes_identity_and_definition_without_truncation() -> None:
    prompt = build_explanation_user_prompt(
        "procedure",
        "resumen_ventas_cliente",
        "CREATE FUNCTION resumen_ventas_cliente(...) ...",
        max_definition_chars=1_000,
    )

    assert "procedure" in prompt
    assert "resumen_ventas_cliente" in prompt
    assert "CREATE FUNCTION resumen_ventas_cliente" in prompt
    assert "ADVERTENCIA" not in prompt


def test_user_prompt_truncates_and_warns_when_definition_exceeds_limit() -> None:
    definition = "A" * 50
    prompt = build_explanation_user_prompt(
        "trigger",
        "trg_demo",
        definition,
        max_definition_chars=10,
    )

    assert "A" * 10 in prompt
    assert "A" * 11 not in prompt
    assert "ADVERTENCIA" in prompt
    assert "10 caracteres" in prompt


def test_user_prompt_does_not_warn_at_exact_limit() -> None:
    definition = "B" * 10
    prompt = build_explanation_user_prompt(
        "procedure",
        "func_demo",
        definition,
        max_definition_chars=10,
    )

    assert "ADVERTENCIA" not in prompt
