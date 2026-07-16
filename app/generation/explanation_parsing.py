"""Parse and validate the LLM's JSON object-explanation payload."""

import json

from pydantic import BaseModel, ConfigDict, ValidationError

from app.exceptions import LlmExplanationParseError


class LlmExplanationPayload(BaseModel):
    """Internal shape of the JSON payload expected from the explanation LLM call."""

    model_config = ConfigDict(frozen=True)

    purpose: str
    facts: tuple[str, ...] = ()
    inferences: tuple[str, ...] = ()
    referenced_tables: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()


def parse_explanation_payload(raw_content: str) -> LlmExplanationPayload:
    """Parse the raw LLM content into the internal explanation payload contract."""
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as error:
        raise LlmExplanationParseError() from error
    try:
        return LlmExplanationPayload.model_validate(data)
    except ValidationError as error:
        raise LlmExplanationParseError() from error
