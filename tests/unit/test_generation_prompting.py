"""Tests for deterministic prompt construction."""

from datetime import date

from app.generation.prompting import build_system_prompt, build_user_prompt
from app.models.connections import ColumnInfo, ForeignKeyInfo, TableDescription


def test_system_prompt_states_dialect_and_read_only_rules() -> None:
    prompt = build_system_prompt("postgres")

    assert "postgres" in prompt
    assert "SELECT" in prompt
    assert "INSERT" in prompt
    assert "JSON" in prompt


def test_user_prompt_includes_question_reference_date_and_context_tables() -> None:
    table = TableDescription(
        schema="public",
        name="clientes",
        columns=(
            ColumnInfo(
                ordinal_position=1,
                name="id",
                data_type="integer",
                nullable=False,
                default=None,
            ),
        ),
        primary_key=("id",),
        foreign_keys=(
            ForeignKeyInfo(
                name="clientes_pais_fkey",
                columns=("pais_id",),
                referenced_schema="public",
                referenced_table="paises",
                referenced_columns=("id",),
            ),
        ),
    )

    prompt = build_user_prompt("¿cuántos clientes hay?", (table,), date(2026, 7, 16))

    assert "2026-07-16" in prompt
    assert "¿cuántos clientes hay?" in prompt
    assert "public.clientes" in prompt
    assert "id (integer)" in prompt
    assert "public.clientes.pais_id -> public.paises.id" in prompt
