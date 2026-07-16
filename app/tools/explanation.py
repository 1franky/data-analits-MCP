"""MCP tool for LLM-assisted explanation of cached database objects."""

from typing import Annotated, Literal

from pydantic import Field

from app.container import get_object_explanation_service
from app.models.generation import ExplainObjectResult

MetadataName = Annotated[str, Field(min_length=1, max_length=128)]


def explain_database_object(
    connection_id: str,
    schema: MetadataName,
    object_type: Literal["procedure", "trigger"],
    name: MetadataName,
    table: MetadataName | None = None,
) -> ExplainObjectResult:
    """Explain one cached procedure or trigger from its real SQL definition."""
    return get_object_explanation_service().explain_object(
        connection_id=connection_id,
        schema=schema,
        object_type=object_type,
        name=name,
        table=table,
    )
