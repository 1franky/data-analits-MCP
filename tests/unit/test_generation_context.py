"""Tests for bounding the catalog context passed to LLM prompts."""

from datetime import UTC, datetime

from app.generation.context import select_context_tables
from app.models.catalog import CatalogSnapshot
from app.models.connections import ColumnInfo, ForeignKeyInfo, SchemaInfo, TableDescription


def _table(name: str, *, foreign_keys: tuple[ForeignKeyInfo, ...] = ()) -> TableDescription:
    return TableDescription(
        schema="public",
        name=name,
        description=f"Tabla {name}.",
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
        foreign_keys=foreign_keys,
    )


def _snapshot(tables: tuple[TableDescription, ...]) -> CatalogSnapshot:
    return CatalogSnapshot(
        connection_id="postgres-demo",
        refreshed_at=datetime(2026, 7, 16, tzinfo=UTC),
        schema_hash="hash",
        schemas=(SchemaInfo(name="public"),),
        tables=tables,
    )


def test_full_snapshot_is_returned_when_it_fits_the_limit() -> None:
    tables = (_table("clientes"), _table("productos"))
    snapshot = _snapshot(tables)

    selected = select_context_tables(snapshot, "cualquier pregunta", max_tables=5)

    assert selected == tables


def test_relevant_tables_are_ranked_above_unrelated_ones() -> None:
    tables = tuple(_table(f"tabla_{index}") for index in range(10))
    snapshot = _snapshot((*tables, _table("clientes")))

    selected = select_context_tables(snapshot, "quiero ver clientes", max_tables=3)

    assert any(table.name == "clientes" for table in selected)
    assert len(selected) == 3


def test_foreign_key_neighbors_are_included_even_beyond_the_soft_limit() -> None:
    ventas = _table(
        "ventas",
        foreign_keys=(
            ForeignKeyInfo(
                name="ventas_cliente_id_fkey",
                columns=("cliente_id",),
                referenced_schema="public",
                referenced_table="clientes",
                referenced_columns=("id",),
            ),
        ),
    )
    # Named to alphabetically outrank "clientes" among zero-score fillers, so "clientes"
    # would be excluded by ranking alone and can only appear via FK-neighbor inclusion.
    filler = tuple(_table(f"aaa_{index}") for index in range(10))
    snapshot = _snapshot((*filler, ventas, _table("clientes")))

    selected = select_context_tables(snapshot, "ventas recientes", max_tables=2)

    names = {table.name for table in selected}
    assert "ventas" in names
    assert "clientes" in names
    assert len(selected) > 2
