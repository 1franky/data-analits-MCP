"""Hardening tests: ambiguity candidates are always grounded against the real catalog."""

from datetime import UTC, datetime

from app.generation.parsing import LlmClarificationPayload
from app.models.catalog import CatalogSnapshot
from app.models.connections import ColumnInfo, SchemaInfo, TableDescription
from app.models.generation import AmbiguityCandidate
from app.services.generation import GenerationService


def _table(name: str, *, columns: tuple[str, ...] = ("id",)) -> TableDescription:
    return TableDescription(
        schema="public",
        name=name,
        columns=tuple(
            ColumnInfo(
                ordinal_position=index + 1,
                name=column,
                data_type="text",
                nullable=True,
                default=None,
            )
            for index, column in enumerate(columns)
        ),
        primary_key=("id",) if "id" in columns else (),
        foreign_keys=(),
    )


def _snapshot(tables: tuple[TableDescription, ...]) -> CatalogSnapshot:
    return CatalogSnapshot(
        connection_id="postgres-demo",
        refreshed_at=datetime(2026, 7, 16, tzinfo=UTC),
        schema_hash="hash",
        schemas=(SchemaInfo(name="public"),),
        tables=tables,
    )


def test_grounding_keeps_candidates_with_similar_but_real_names() -> None:
    snapshot = _snapshot(
        (
            _table("clientes", columns=("id", "correo")),
            _table("clientes_archivados", columns=("id", "correo")),
        )
    )
    payload = LlmClarificationPayload(
        ambiguous_term="cliente",
        question="¿te refieres a clientes activos o archivados?",
        candidates=(
            AmbiguityCandidate(schema="public", table="clientes", column=None, reason="activos"),
            AmbiguityCandidate(
                schema="public",
                table="clientes_archivados",
                column=None,
                reason="archivados",
            ),
        ),
    )

    clarification = GenerationService._ground_clarification(payload, snapshot)

    assert {candidate.table for candidate in clarification.candidates} == {
        "clientes",
        "clientes_archivados",
    }


def test_grounding_discards_tables_absent_from_the_snapshot() -> None:
    snapshot = _snapshot((_table("clientes"),))
    payload = LlmClarificationPayload(
        ambiguous_term="cliente",
        question="¿cuál tabla de cliente?",
        candidates=(
            AmbiguityCandidate(schema="public", table="clientes", column=None, reason="real"),
            AmbiguityCandidate(
                schema="public",
                table="clientes_inventada",
                column=None,
                reason="alucinación",
            ),
        ),
    )

    clarification = GenerationService._ground_clarification(payload, snapshot)

    assert [candidate.table for candidate in clarification.candidates] == ["clientes"]


def test_grounding_discards_columns_absent_from_the_named_table() -> None:
    snapshot = _snapshot((_table("clientes", columns=("id", "correo")),))
    payload = LlmClarificationPayload(
        ambiguous_term="estado",
        question="¿qué columna de estado?",
        candidates=(
            AmbiguityCandidate(
                schema="public",
                table="clientes",
                column="correo",
                reason="existe",
            ),
            AmbiguityCandidate(
                schema="public",
                table="clientes",
                column="estado_civil",
                reason="alucinación",
            ),
        ),
    )

    clarification = GenerationService._ground_clarification(payload, snapshot)

    assert len(clarification.candidates) == 1
    assert clarification.candidates[0].column == "correo"


def test_grounding_with_no_valid_candidates_returns_empty_tuple() -> None:
    snapshot = _snapshot((_table("clientes"),))
    payload = LlmClarificationPayload(
        ambiguous_term="fantasma",
        question="¿cuál tabla fantasma?",
        candidates=(
            AmbiguityCandidate(
                schema="public",
                table="no_existe",
                column=None,
                reason="alucinación",
            ),
        ),
    )

    clarification = GenerationService._ground_clarification(payload, snapshot)

    assert clarification.candidates == ()
    assert clarification.ambiguous_term == "fantasma"
