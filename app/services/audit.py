"""Privacy-preserving audit event creation."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from app.models.audit import AuditConfig, AuditOperation, AuditRecord, AuditStatus
from app.models.generation import GenerationOutcome
from app.models.query import SqlStatementType, SqlValidationResult
from app.models.rag import DocumentIndexOutcome
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

    def record_document_index(
        self,
        *,
        tool_name: str,
        connection_id: str | None,
        document_type: str,
        content_hash: str,
        outcome: DocumentIndexOutcome,
        chunk_count: int,
        duration_ms: float,
        error_code: str | None = None,
    ) -> AuditRecord | None:
        """Append one document indexing event; only its content hash is stored."""
        if not self._enabled:
            return None
        status = (
            AuditStatus.ERROR if outcome is DocumentIndexOutcome.FAILED else AuditStatus.SUCCESS
        )
        record = AuditRecord(
            event_id=str(uuid4()),
            timestamp=datetime.now(UTC),
            tool_name=tool_name,
            connection_id=connection_id or "-",
            operation=AuditOperation.INDEX_DOCUMENT,
            statement_type=document_type,
            query_hash=content_hash,
            validation_valid=outcome is not DocumentIndexOutcome.FAILED,
            executed=outcome in {DocumentIndexOutcome.INDEXED, DocumentIndexOutcome.REMOVED},
            blocked=False,
            blocked_reason_codes=(),
            duration_ms=round(duration_ms, 3),
            row_count=chunk_count,
            status=status,
            error_code=error_code,
        )
        self._repository.append(record)
        return record

    def record_document_search(
        self,
        *,
        tool_name: str,
        connection_id: str | None,
        query: str,
        match_count: int,
        duration_ms: float,
        error_code: str | None = None,
    ) -> AuditRecord | None:
        """Append one document search event; only a query hash is stored."""
        if not self._enabled:
            return None
        status = AuditStatus.ERROR if error_code is not None else AuditStatus.SUCCESS
        record = AuditRecord(
            event_id=str(uuid4()),
            timestamp=datetime.now(UTC),
            tool_name=tool_name,
            connection_id=connection_id or "-",
            operation=AuditOperation.SEARCH_DOCUMENTS,
            statement_type="document_search",
            query_hash=sha256(b"").hexdigest(),
            prompt_hash=sha256(query.encode("utf-8")).hexdigest(),
            validation_valid=error_code is None,
            executed=True,
            blocked=False,
            blocked_reason_codes=(),
            duration_ms=round(duration_ms, 3),
            row_count=match_count,
            status=status,
            error_code=error_code,
        )
        self._repository.append(record)
        return record

    def record_generation(
        self,
        *,
        tool_name: str,
        connection_id: str,
        operation: AuditOperation,
        prompt: str,
        sql: str | None,
        outcome: GenerationOutcome,
        validation: SqlValidationResult | None,
        executed: bool,
        duration_ms: float,
        row_count: int | None,
        error_code: str | None = None,
    ) -> AuditRecord | None:
        """Append one LLM-assisted event; only hashes represent prompt and SQL."""
        if not self._enabled:
            return None
        blocked = validation is not None and not validation.executable
        status = (
            AuditStatus.CLARIFICATION
            if outcome is GenerationOutcome.CLARIFICATION_REQUIRED
            else AuditStatus.ERROR
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
            statement_type=(
                validation.statement_type.value
                if validation is not None
                else SqlStatementType.UNKNOWN.value
            ),
            query_hash=sha256((sql or "").encode("utf-8")).hexdigest(),
            prompt_hash=sha256(prompt.encode("utf-8")).hexdigest(),
            validation_valid=validation.valid if validation is not None else False,
            executed=executed,
            blocked=blocked,
            blocked_reason_codes=(
                tuple(issue.code for issue in validation.blocked_reasons)
                if validation is not None
                else ()
            ),
            duration_ms=round(duration_ms, 3),
            row_count=row_count,
            status=status,
            error_code=error_code,
        )
        self._repository.append(record)
        return record
