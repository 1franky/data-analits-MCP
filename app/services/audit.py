"""Privacy-preserving audit event creation."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from app.models.audit import AuditConfig, AuditOperation, AuditRecord, AuditStatus
from app.models.query import SqlValidationResult
from app.repositories import AuditRepository


class AuditService:
    """Record query decisions without retaining SQL, parameters or returned data."""

    def __init__(
        self,
        repository: AuditRepository,
        config: AuditConfig,
    ) -> None:
        self._repository = repository
        self._enabled = config.enabled

    def record(
        self,
        *,
        tool_name: str,
        connection_id: str,
        operation: AuditOperation,
        sql: str,
        validation: SqlValidationResult,
        executed: bool,
        duration_ms: float,
        row_count: int | None,
        error_code: str | None = None,
    ) -> AuditRecord | None:
        """Append one event; only a SHA-256 correlation hash represents the SQL."""
        if not self._enabled:
            return None
        blocked = not validation.executable
        status = (
            AuditStatus.ERROR
            if error_code is not None and not blocked
            else AuditStatus.BLOCKED
            if blocked
            else AuditStatus.SUCCESS
        )
        record = AuditRecord(
            event_id=str(uuid4()),
            timestamp=datetime.now(UTC),
            tool_name=tool_name,
            connection_id=connection_id,
            operation=operation,
            statement_type=validation.statement_type.value,
            query_hash=sha256(sql.encode("utf-8")).hexdigest(),
            validation_valid=validation.valid,
            executed=executed,
            blocked=blocked,
            blocked_reason_codes=tuple(issue.code for issue in validation.blocked_reasons),
            duration_ms=round(duration_ms, 3),
            row_count=row_count,
            status=status,
            error_code=error_code,
        )
        self._repository.append(record)
        return record
