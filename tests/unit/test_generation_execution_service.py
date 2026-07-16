"""Tests ensuring generated SQL is always fully revalidated before executing."""

import json
from pathlib import Path

from app.exceptions import GenerationProviderError
from app.models.generation import GenerationOutcome
from tests.generation_fakes import build_generation_services


def test_generated_select_is_executed_with_real_rows(tmp_path: Path) -> None:
    _generation, execution, provider, _audit_repository, adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )
    provider.responses.append(
        json.dumps({"outcome": "generated", "sql": "SELECT id, nombre FROM productos"})
    )

    result = execution.generate_and_execute("postgres-demo", "dame los productos")

    assert result.outcome is GenerationOutcome.GENERATED
    assert result.execution is not None
    assert result.execution.executed is True
    assert result.execution.rows[0] == (1, "Laptop")
    assert adapter.execute_calls == 1


def test_generated_write_sql_never_reaches_the_adapter(tmp_path: Path) -> None:
    _generation, execution, provider, audit_repository, adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )
    provider.responses.append(json.dumps({"outcome": "generated", "sql": "DELETE FROM productos"}))

    result = execution.generate_and_execute("postgres-demo", "borra los productos")

    assert result.outcome is GenerationOutcome.GENERATED
    assert result.execution is not None
    assert result.execution.executed is False
    assert result.execution.error_code == "SQL_VALIDATION_BLOCKED"
    assert adapter.execute_calls == 0
    tool_names = {record.tool_name for record in audit_repository.list_records()}
    assert "generate_and_execute_query" in tool_names


def test_clarification_required_never_executes(tmp_path: Path) -> None:
    _generation, execution, provider, _audit_repository, adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
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

    result = execution.generate_and_execute("postgres-demo", "dame los datos del cliente")

    assert result.outcome is GenerationOutcome.CLARIFICATION_REQUIRED
    assert result.execution is None
    assert result.clarification is not None
    assert adapter.execute_calls == 0


def test_provider_failure_never_executes(tmp_path: Path) -> None:
    _generation, execution, provider, _audit_repository, adapter, _catalog = (
        build_generation_services(tmp_path / "catalog.db", tmp_path / "audit.db")
    )
    provider.error = GenerationProviderError(code="GENERATION_PROVIDER_ERROR", message="boom")

    result = execution.generate_and_execute("postgres-demo", "cualquier pregunta")

    assert result.outcome is GenerationOutcome.GENERATION_FAILED
    assert result.execution is None
    assert adapter.execute_calls == 0
