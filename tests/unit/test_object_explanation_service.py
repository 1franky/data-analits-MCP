"""Tests for LLM-assisted object explanation, its scoping and privacy guarantees."""

import json
from pathlib import Path

import pytest

from app.exceptions import (
    DatabaseObjectNotFoundError,
    GenerationNotConfiguredError,
    GenerationProviderError,
    GenerationRequestError,
)
from app.models.audit import AuditStatus
from app.models.connections import ProcedureInfo
from app.models.generation import ExplanationOutcome, GenerationConfig
from tests.generation_fakes import PROVIDER_CONFIG, build_explanation_services


def test_explains_procedure_with_facts_and_inferences_separated(tmp_path: Path) -> None:
    explanation, provider, audit_repository, _adapter, _catalog = build_explanation_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    provider.responses.append(
        json.dumps(
            {
                "purpose": "Calcula el resumen de ventas de un cliente.",
                "facts": ["Recibe p_cliente_id integer", "Consulta ventas y productos"],
                "inferences": ["Se usaría para un dashboard de clientes"],
                "referenced_tables": ["ventas", "productos"],
                "risks": [],
            }
        )
    )

    result = explanation.explain_object(
        "postgres-demo", "public", "procedure", "resumen_ventas_cliente"
    )
    audit = audit_repository.list_records()[0]
    persisted_bytes = (tmp_path / "audit.db").read_bytes()

    assert result.outcome is ExplanationOutcome.EXPLAINED
    assert result.purpose == "Calcula el resumen de ventas de un cliente."
    assert result.facts == ("Recibe p_cliente_id integer", "Consulta ventas y productos")
    assert result.inferences == ("Se usaría para un dashboard de clientes",)
    assert result.referenced_tables == ("ventas", "productos")
    assert result.definition_truncated is False
    assert audit.status is AuditStatus.SUCCESS
    assert audit.prompt_hash is not None and len(audit.prompt_hash) == 64
    assert b"CREATE FUNCTION resumen_ventas_cliente" not in persisted_bytes
    assert b"Calcula el resumen de ventas" not in persisted_bytes


def test_explains_trigger_bound_to_its_table(tmp_path: Path) -> None:
    explanation, provider, _audit_repository, _adapter, _catalog = build_explanation_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    provider.responses.append(
        json.dumps(
            {
                "purpose": "Descuenta stock al registrar una venta.",
                "facts": ["Se dispara AFTER INSERT en ventas"],
                "inferences": [],
                "referenced_tables": ["productos"],
                "risks": ["No valida stock negativo"],
            }
        )
    )

    result = explanation.explain_object(
        "postgres-demo",
        "public",
        "trigger",
        "trg_ventas_actualiza_stock",
        table="ventas",
    )

    assert result.outcome is ExplanationOutcome.EXPLAINED
    assert result.table == "ventas"
    assert result.risks == ("No valida stock negativo",)


def test_trigger_without_table_raises_generation_request_error(tmp_path: Path) -> None:
    explanation, _provider, _audit_repository, _adapter, _catalog = build_explanation_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )

    with pytest.raises(GenerationRequestError) as excinfo:
        explanation.explain_object("postgres-demo", "public", "trigger", "trg_demo")

    assert excinfo.value.code == "EXPLANATION_TABLE_REQUIRED"


def test_unknown_procedure_never_calls_the_provider(tmp_path: Path) -> None:
    explanation, provider, _audit_repository, _adapter, _catalog = build_explanation_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )

    with pytest.raises(DatabaseObjectNotFoundError):
        explanation.explain_object("postgres-demo", "public", "procedure", "no_existe")

    assert provider.calls == []


def test_generation_disabled_raises_not_configured(tmp_path: Path) -> None:
    explanation, _provider, _audit_repository, _adapter, _catalog = build_explanation_services(
        tmp_path / "catalog.db",
        tmp_path / "audit.db",
        generation_config=GenerationConfig(enabled=False),
    )

    with pytest.raises(GenerationNotConfiguredError):
        explanation.explain_object("postgres-demo", "public", "procedure", "resumen_ventas_cliente")


def test_provider_failure_is_reported_and_audited(tmp_path: Path) -> None:
    explanation, provider, audit_repository, _adapter, _catalog = build_explanation_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    provider.error = GenerationProviderError(code="GENERATION_PROVIDER_ERROR", message="boom")

    result = explanation.explain_object(
        "postgres-demo", "public", "procedure", "resumen_ventas_cliente"
    )
    audit = audit_repository.list_records()[0]

    assert result.outcome is ExplanationOutcome.EXPLANATION_FAILED
    assert result.error_code == "GENERATION_PROVIDER_ERROR"
    assert audit.status is AuditStatus.ERROR


def test_unparseable_response_is_reported_as_failed(tmp_path: Path) -> None:
    explanation, provider, audit_repository, _adapter, _catalog = build_explanation_services(
        tmp_path / "catalog.db", tmp_path / "audit.db"
    )
    provider.responses.append("not json")

    result = explanation.explain_object(
        "postgres-demo", "public", "procedure", "resumen_ventas_cliente"
    )
    audit = audit_repository.list_records()[0]

    assert result.outcome is ExplanationOutcome.EXPLANATION_FAILED
    assert result.error_code == "EXPLANATION_RESPONSE_PARSE_ERROR"
    assert audit.status is AuditStatus.ERROR


def test_long_definition_is_truncated_with_explicit_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explanation, provider, _audit_repository, _adapter, catalog = build_explanation_services(
        tmp_path / "catalog.db",
        tmp_path / "audit.db",
        generation_config=GenerationConfig(
            enabled=True,
            provider=PROVIDER_CONFIG,
            max_definition_chars=500,
        ),
    )
    long_procedure = ProcedureInfo(
        schema="public",
        name="resumen_ventas_cliente",
        kind="function",
        language="sql",
        arguments="p_cliente_id integer",
        return_type="TABLE(total_ventas bigint, monto_total numeric)",
        definition="SELECT " + ("x" * 600),
        comment=None,
    )
    monkeypatch.setattr(catalog, "get_procedure", lambda *args, **kwargs: long_procedure)
    provider.responses.append(json.dumps({"purpose": "resumen"}))

    result = explanation.explain_object(
        "postgres-demo", "public", "procedure", "resumen_ventas_cliente"
    )

    assert result.definition_truncated is True
    sent_prompt = provider.calls[0].messages[1].content
    assert "ADVERTENCIA" in sent_prompt
