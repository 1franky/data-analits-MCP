"""Tests for LLM-assisted SQL generation, its blocking and its privacy guarantees."""

import json
from pathlib import Path

import pytest

from app.exceptions import (
    GenerationNotConfiguredError,
    GenerationProviderError,
    GenerationRequestError,
)
from app.models.audit import AuditStatus
from app.models.generation import GenerationConfig, GenerationOutcome
from tests.generation_fakes import PROVIDER_CONFIG, build_generation_services


def test_generate_sql_returns_executable_select_and_audits_hashes_only(
    tmp_path: Path,
) -> None:
    generation, _execution, provider, audit_repository, _adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )
    provider.responses.append(
        json.dumps(
            {
                "outcome": "generated",
                "sql": "SELECT id, nombre FROM productos",
                "assumptions": ["se listan todos los productos"],
            }
        )
    )
    question = "dame los productos con su nombre"

    result = generation.generate_sql("postgres-demo", question)
    audit = audit_repository.list_records()[0]
    persisted_bytes = (tmp_path / "audit.db").read_bytes()

    assert result.outcome is GenerationOutcome.GENERATED
    assert result.generated is not None
    assert result.generated.validation.executable is True
    assert result.generated.assumptions == ("se listan todos los productos",)
    assert audit.status is AuditStatus.SUCCESS
    assert len(audit.query_hash) == 64
    assert audit.prompt_hash is not None
    assert len(audit.prompt_hash) == 64
    assert question.encode() not in persisted_bytes
    assert b"SELECT id, nombre FROM productos" not in persisted_bytes


def test_generate_sql_returns_blocked_sql_for_review_without_executing(
    tmp_path: Path,
) -> None:
    generation, _execution, provider, audit_repository, adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )
    provider.responses.append(json.dumps({"outcome": "generated", "sql": "DELETE FROM productos"}))

    result = generation.generate_sql("postgres-demo", "borra los productos")
    audit = audit_repository.list_records()[0]

    assert result.outcome is GenerationOutcome.GENERATED
    assert result.generated is not None
    assert result.generated.validation.executable is False
    assert result.generated.validation.statement_type == "DELETE"
    assert audit.status is AuditStatus.BLOCKED
    assert adapter.execute_calls == 0


def test_generate_sql_returns_clarification_grounded_against_the_real_catalog(
    tmp_path: Path,
) -> None:
    generation, _execution, provider, audit_repository, _adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )
    provider.responses.append(
        json.dumps(
            {
                "outcome": "clarification_required",
                "clarification": {
                    "ambiguous_term": "cliente",
                    "question": "¿Te refieres a la tabla clientes?",
                    "candidates": [
                        {
                            "schema": "public",
                            "table": "clientes",
                            "column": "correo",
                            "reason": "coincide con el término",
                        },
                        {
                            "schema": "public",
                            "table": "tabla_inventada",
                            "column": None,
                            "reason": "alucinación del modelo",
                        },
                    ],
                },
            }
        )
    )

    result = generation.generate_sql("postgres-demo", "dame los datos del cliente")
    audit = audit_repository.list_records()[0]

    assert result.outcome is GenerationOutcome.CLARIFICATION_REQUIRED
    assert result.clarification is not None
    candidate_tables = {candidate.table for candidate in result.clarification.candidates}
    assert candidate_tables == {"clientes"}
    assert audit.status is AuditStatus.CLARIFICATION


def test_generate_sql_provider_error_yields_generation_failed(tmp_path: Path) -> None:
    generation, _execution, provider, audit_repository, _adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )
    provider.error = GenerationProviderError(
        code="GENERATION_PROVIDER_TIMEOUT",
        message="timeout",
    )

    result = generation.generate_sql("postgres-demo", "cualquier pregunta")
    audit = audit_repository.list_records()[0]

    assert result.outcome is GenerationOutcome.GENERATION_FAILED
    assert result.error_code == "GENERATION_PROVIDER_TIMEOUT"
    assert audit.status is AuditStatus.ERROR


def test_generate_sql_parse_error_yields_generation_failed(tmp_path: Path) -> None:
    generation, _execution, provider, _audit_repository, _adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )
    provider.responses.append("not valid json")

    result = generation.generate_sql("postgres-demo", "cualquier pregunta")

    assert result.outcome is GenerationOutcome.GENERATION_FAILED
    assert result.error_code == "GENERATION_RESPONSE_PARSE_ERROR"


def test_generate_sql_raises_when_generation_is_disabled(tmp_path: Path) -> None:
    generation, _execution, _provider, _audit_repository, _adapter, _catalog = (
        build_generation_services(
            tmp_path / "catalog.db",
            tmp_path / "audit.db",
            generation_config=GenerationConfig(enabled=False),
        )
    )

    with pytest.raises(GenerationNotConfiguredError):
        generation.generate_sql("postgres-demo", "cualquier pregunta")


def test_generate_sql_rejects_empty_question(tmp_path: Path) -> None:
    generation, _execution, _provider, _audit_repository, _adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )

    with pytest.raises(GenerationRequestError):
        generation.generate_sql("postgres-demo", "   ")


def test_generation_config_requires_provider_when_enabled() -> None:
    with pytest.raises(ValueError, match="provider"):
        GenerationConfig(enabled=True, provider=None)

    assert GenerationConfig(enabled=True, provider=PROVIDER_CONFIG).enabled is True
