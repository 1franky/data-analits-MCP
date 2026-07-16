"""Build deterministic prompts for database object explanation."""

from typing import Literal

_SYSTEM_PROMPT = """\
Eres un analista que explica objetos de bases de datos PostgreSQL (funciones, procedimientos \
y triggers) a partir de su definición SQL real.

Reglas obligatorias:
- Basa "facts" ÚNICAMENTE en elementos verificables presentes literalmente en la definición \
entregada (nombres de tablas, columnas, condiciones, tipo de trigger, parámetros).
- Usa "inferences" para cualquier interpretación de negocio o intención que no esté escrita \
literalmente en la definición (por ejemplo, para qué se usaría este objeto).
- Nunca mezcles un hecho con una inferencia dentro del mismo elemento.
- "referenced_tables" debe listar solo tablas que aparezcan literalmente en la definición, en \
forma "schema.tabla" cuando el schema sea explícito o solo "tabla" si no lo es.
- "risks" debe señalar efectos secundarios, bucles de triggers, falta de manejo de errores o \
supuestos peligrosos, si existen; lista vacía si no aplica.
- Responde EXCLUSIVAMENTE con un objeto JSON, sin texto adicional ni bloques de código, con \
esta forma exacta:
  {"purpose": "...", "facts": ["..."], "inferences": ["..."], "referenced_tables": ["..."], \
"risks": ["..."]}
"""


def build_explanation_system_prompt() -> str:
    """Build the fixed system prompt enforcing facts-versus-inferences separation."""
    return _SYSTEM_PROMPT


def build_explanation_user_prompt(
    object_kind: Literal["procedure", "trigger"],
    object_name: str,
    definition: str,
    max_definition_chars: int,
) -> str:
    """Build the user prompt with the object identity and its (possibly truncated) definition."""
    truncated = len(definition) > max_definition_chars
    effective_definition = definition[:max_definition_chars]
    lines = [
        f"Tipo de objeto: {object_kind}",
        f"Nombre: {object_name}",
        "Definición SQL real:",
        effective_definition,
    ]
    if truncated:
        lines.append(
            f"ADVERTENCIA: la definición fue truncada a {max_definition_chars} caracteres; "
            "el análisis puede estar incompleto."
        )
    return "\n".join(lines)
