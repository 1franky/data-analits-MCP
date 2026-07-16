"""Build deterministic prompts for SQL generation."""

from datetime import date

from app.models.connections import TableDescription

_SYSTEM_PROMPT_TEMPLATE = """\
Eres un generador de SQL de solo lectura para el dialecto {dialect}.

Reglas obligatorias:
- Genera EXCLUSIVAMENTE una sentencia SELECT (incluidas CTE y operaciones de conjuntos de \
solo lectura).
- Nunca generes INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP, TRUNCATE, COPY ni comandos \
administrativos.
- Usa solo las tablas y columnas listadas en el contexto entregado; nunca inventes objetos.
- Nunca uses placeholders ni parámetros; usa siempre literales explícitos dentro del SQL.
- Si la pregunta es ambigua (por ejemplo, un término podría referirse a más de una tabla o \
columna del contexto), no generes SQL: solicita aclaración.
- Responde EXCLUSIVAMENTE con un objeto JSON, sin texto adicional ni bloques de código, con una \
de estas dos formas exactas:
  {{"outcome": "generated", "sql": "...", "assumptions": ["..."]}}
  {{"outcome": "clarification_required", "clarification": {{"ambiguous_term": "...", \
"question": "...", "candidates": [{{"schema": "...", "table": "...", "column": null, \
"reason": "..."}}]}}}}
- "candidates" debe listar únicamente objetos que existan literalmente en el contexto entregado.
- "assumptions" debe listar de forma explícita cualquier supuesto de negocio hecho al generar \
el SQL (por ejemplo, qué columna se usó como fecha o como estado).
"""


def build_system_prompt(dialect: str) -> str:
    """Build the fixed system prompt enforcing the read-only generation contract."""
    return _SYSTEM_PROMPT_TEMPLATE.format(dialect=dialect)


def build_user_prompt(
    question: str,
    context_tables: tuple[TableDescription, ...],
    reference_date: date,
) -> str:
    """Build the user prompt with the question, reference date and catalog context."""
    lines = [
        f"Fecha de referencia: {reference_date.isoformat()}",
        f"Pregunta: {question}",
        "Contexto de catálogo disponible (únicas tablas y columnas permitidas):",
    ]
    for table in context_tables:
        columns = ", ".join(f"{column.name} ({column.data_type})" for column in table.columns)
        lines.append(f"- {table.schema_name}.{table.name}: {columns}")
        for foreign_key in table.foreign_keys:
            source = f"{table.schema_name}.{table.name}.{', '.join(foreign_key.columns)}"
            target = (
                f"{foreign_key.referenced_schema}.{foreign_key.referenced_table}."
                f"{', '.join(foreign_key.referenced_columns)}"
            )
            lines.append(f"    FK {source} -> {target}")
    return "\n".join(lines)
