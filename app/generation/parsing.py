"""Parse and validate the LLM's JSON generation payload."""

import json
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.exceptions import LlmGenerationParseError
from app.models.generation import AmbiguityCandidate


class LlmClarificationPayload(BaseModel):
    """Internal shape of a clarification request returned by the LLM."""

    model_config = ConfigDict(frozen=True)

    ambiguous_term: str
    question: str
    candidates: tuple[AmbiguityCandidate, ...] = ()


class LlmGenerationPayload(BaseModel):
    """Internal shape of the JSON payload expected from the LLM."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["generated", "clarification_required"]
    sql: str | None = None
    assumptions: tuple[str, ...] = ()
    clarification: LlmClarificationPayload | None = None

    @model_validator(mode="after")
    def require_fields_for_outcome(self) -> Self:
        """Ensure each outcome carries the fields it requires."""
        if self.outcome == "generated" and not (self.sql and self.sql.strip()):
            raise ValueError("el outcome 'generated' requiere un campo sql no vacío")
        if self.outcome == "clarification_required" and self.clarification is None:
            raise ValueError("el outcome 'clarification_required' requiere clarification")
        return self


def parse_generation_payload(raw_content: str) -> LlmGenerationPayload:
    """Parse the raw LLM content into the internal generation payload contract."""
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as error:
        raise LlmGenerationParseError() from error
    try:
        return LlmGenerationPayload.model_validate(data)
    except ValidationError as error:
        raise LlmGenerationParseError() from error
