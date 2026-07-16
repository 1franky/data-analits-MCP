"""Configuration and records for privacy-preserving query audit."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class AuditConfig(BaseModel):
    """Enable or disable durable query audit events."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True


class AuditOperation(StrEnum):
    """Security-relevant query operations."""

    VALIDATE = "validate"
    EXECUTE = "execute"
    EXPLAIN = "explain"
    GENERATE = "generate"
    REPORT = "report"
    EXPLAIN_OBJECT = "explain_object"


class AuditStatus(StrEnum):
    """Final state of an audited operation."""

    SUCCESS = "success"
    BLOCKED = "blocked"
    ERROR = "error"
    CLARIFICATION = "clarification"


class AuditRecord(BaseModel):
    """Audit event containing no SQL text, parameters or result values."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    timestamp: datetime
    tool_name: str
    connection_id: str
    operation: AuditOperation
    statement_type: str
    query_hash: str
    prompt_hash: str | None = None
    validation_valid: bool
    executed: bool
    blocked: bool
    blocked_reason_codes: tuple[str, ...]
    duration_ms: float
    row_count: int | None
    status: AuditStatus
    error_code: str | None = None
