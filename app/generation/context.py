"""Bound the catalog context passed to LLM prompts."""

from app.models.catalog import CatalogSnapshot
from app.models.connections import TableDescription


def select_context_tables(
    snapshot: CatalogSnapshot,
    question: str,
    max_tables: int,
) -> tuple[TableDescription, ...]:
    """Return the full snapshot if it fits, otherwise the most relevant tables.

    Foreign-key neighbors of the top-ranked tables are always appended so referential
    context stays intact; the result may therefore modestly exceed ``max_tables``.
    """
    if len(snapshot.tables) <= max_tables:
        return snapshot.tables

    terms = _tokenize(question)
    ranked = sorted(
        snapshot.tables,
        key=lambda table: (-_score(table, terms), table.schema_name, table.name),
    )
    selected = list(ranked[:max_tables])
    selected_keys = {(table.schema_name, table.name) for table in selected}

    neighbor_keys: set[tuple[str, str]] = set()
    for table in selected:
        for foreign_key in table.foreign_keys:
            neighbor_keys.add((foreign_key.referenced_schema, foreign_key.referenced_table))

    by_key = {(table.schema_name, table.name): table for table in snapshot.tables}
    for key in sorted(neighbor_keys):
        if key in selected_keys:
            continue
        neighbor = by_key.get(key)
        if neighbor is not None:
            selected.append(neighbor)
            selected_keys.add(key)

    return tuple(sorted(selected, key=lambda table: (table.schema_name, table.name)))


def _tokenize(question: str) -> tuple[str, ...]:
    normalized = "".join(char if char.isalnum() else " " for char in question.casefold())
    return tuple(token for token in normalized.split() if len(token) > 2)


def _score(table: TableDescription, terms: tuple[str, ...]) -> int:
    if not terms:
        return 0
    column_names = " ".join(column.name for column in table.columns)
    haystack = (
        f"{table.schema_name} {table.name} {table.description or ''} {column_names}"
    ).casefold()
    return sum(1 for term in terms if term in haystack)
