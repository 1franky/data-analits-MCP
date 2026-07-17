"""Validated, audited and bounded MongoDB find/aggregate execution use cases."""

import json
from hashlib import sha256
from threading import BoundedSemaphore
from time import perf_counter

from pydantic import JsonValue

from app.exceptions import DataPlatformError
from app.models.audit import AuditOperation
from app.models.document_query import DocumentQueryExecutionResult, DocumentQueryValidationResult
from app.models.query import QueryPolicyConfig
from app.observability.metrics import (
    QUERY_BLOCKED_TOTAL,
    QUERY_DURATION_SECONDS,
    QUERY_IN_PROGRESS,
    QUERY_QUEUE_WAIT_SECONDS,
    QUERY_REQUESTS_TOTAL,
)
from app.services.audit import AuditService
from app.services.connections import ConnectionService
from app.services.document_query_validation import DocumentQueryValidationService


class DocumentQueryExecutionService:
    """Ensure a blocked MongoDB request can never reach an adapter execution method."""

    def __init__(
        self,
        connections: ConnectionService,
        validator: DocumentQueryValidationService,
        audit: AuditService,
        policy: QueryPolicyConfig,
    ) -> None:
        self._connections = connections
        self._validator = validator
        self._audit = audit
        self._policy = policy
        self._capacity = BoundedSemaphore(policy.max_concurrent_queries)

    def execute_find(
        self,
        connection_id: str,
        collection: str,
        filter: dict[str, JsonValue],
        projection: dict[str, JsonValue] | None = None,
        max_rows: int | None = None,
        timeout_seconds: int | None = None,
    ) -> DocumentQueryExecutionResult:
        """Validate and execute one find() under row, byte, timeout and concurrency limits."""
        config = self._connections.get_connection_config(connection_id)
        validation = self._validator.validate_find(collection, filter, projection)
        payload_hash = self._payload_hash({"filter": filter, "projection": projection})
        if not validation.executable:
            result = self._blocked_result(connection_id, collection, validation)
            self._record_blocked_metrics(config.type.value, "find", validation)
            self._audit_execution(connection_id, "execute_mongo_find", payload_hash, result)
            return result

        effective_rows = min(
            max_rows or config.max_rows, config.max_rows, self._policy.global_max_rows
        )
        effective_timeout = min(
            timeout_seconds or config.query_timeout_seconds, config.query_timeout_seconds
        )
        wait_started_at = perf_counter()
        acquired = self._capacity.acquire(timeout=self._policy.queue_wait_seconds)
        QUERY_QUEUE_WAIT_SECONDS.labels(config.type.value).observe(perf_counter() - wait_started_at)
        if not acquired:
            result = DocumentQueryExecutionResult(
                connection_id=connection_id,
                collection=collection,
                operation=validation.operation,
                executed=False,
                validation=validation,
                row_limit=effective_rows,
                error_code="QUERY_CAPACITY_EXCEEDED",
                message="No hay capacidad disponible para ejecutar otra consulta.",
            )
            QUERY_REQUESTS_TOTAL.labels(config.type.value, "find", "capacity_rejected").inc()
            self._audit_execution(connection_id, "execute_mongo_find", payload_hash, result)
            return result

        QUERY_IN_PROGRESS.labels(config.type.value).inc()
        try:
            adapter = self._connections.get_document_adapter(connection_id)
            adapter_result = adapter.execute_find(
                collection,
                filter,
                projection,
                effective_rows,
                effective_timeout,
                self._policy.max_serialized_bytes,
            )
            result = DocumentQueryExecutionResult(
                connection_id=connection_id,
                collection=collection,
                operation=validation.operation,
                executed=True,
                validation=validation,
                documents=adapter_result.documents,
                document_count=len(adapter_result.documents),
                row_limit=effective_rows,
                truncated=adapter_result.truncated,
                serialized_bytes=adapter_result.serialized_bytes,
                duration_ms=adapter_result.duration_ms,
                message="Consulta find() ejecutada correctamente.",
            )
        except DataPlatformError as error:
            result = DocumentQueryExecutionResult(
                connection_id=connection_id,
                collection=collection,
                operation=validation.operation,
                executed=False,
                validation=validation,
                row_limit=effective_rows,
                error_code=error.code,
                message=error.message,
            )
        finally:
            self._capacity.release()
            QUERY_IN_PROGRESS.labels(config.type.value).dec()
        QUERY_REQUESTS_TOTAL.labels(
            config.type.value, "find", "success" if result.executed else "error"
        ).inc()
        QUERY_DURATION_SECONDS.labels(config.type.value, "find").observe(result.duration_ms / 1000)
        self._audit_execution(connection_id, "execute_mongo_find", payload_hash, result)
        return result

    def execute_aggregate(
        self,
        connection_id: str,
        collection: str,
        pipeline: list[dict[str, JsonValue]],
        max_rows: int | None = None,
        timeout_seconds: int | None = None,
    ) -> DocumentQueryExecutionResult:
        """Validate and execute one aggregation pipeline under the same limits as find()."""
        config = self._connections.get_connection_config(connection_id)
        validation = self._validator.validate_aggregate(collection, pipeline)
        payload_hash = self._payload_hash({"pipeline": pipeline})
        if not validation.executable:
            result = self._blocked_result(connection_id, collection, validation)
            self._record_blocked_metrics(config.type.value, "aggregate", validation)
            self._audit_execution(connection_id, "execute_mongo_aggregate", payload_hash, result)
            return result

        effective_rows = min(
            max_rows or config.max_rows, config.max_rows, self._policy.global_max_rows
        )
        effective_timeout = min(
            timeout_seconds or config.query_timeout_seconds, config.query_timeout_seconds
        )
        wait_started_at = perf_counter()
        acquired = self._capacity.acquire(timeout=self._policy.queue_wait_seconds)
        QUERY_QUEUE_WAIT_SECONDS.labels(config.type.value).observe(perf_counter() - wait_started_at)
        if not acquired:
            result = DocumentQueryExecutionResult(
                connection_id=connection_id,
                collection=collection,
                operation=validation.operation,
                executed=False,
                validation=validation,
                row_limit=effective_rows,
                error_code="QUERY_CAPACITY_EXCEEDED",
                message="No hay capacidad disponible para ejecutar otra agregación.",
            )
            QUERY_REQUESTS_TOTAL.labels(config.type.value, "aggregate", "capacity_rejected").inc()
            self._audit_execution(connection_id, "execute_mongo_aggregate", payload_hash, result)
            return result

        QUERY_IN_PROGRESS.labels(config.type.value).inc()
        try:
            adapter = self._connections.get_document_adapter(connection_id)
            adapter_result = adapter.execute_aggregation(
                collection,
                pipeline,
                effective_rows,
                effective_timeout,
                self._policy.max_serialized_bytes,
            )
            result = DocumentQueryExecutionResult(
                connection_id=connection_id,
                collection=collection,
                operation=validation.operation,
                executed=True,
                validation=validation,
                documents=adapter_result.documents,
                document_count=len(adapter_result.documents),
                row_limit=effective_rows,
                truncated=adapter_result.truncated,
                serialized_bytes=adapter_result.serialized_bytes,
                duration_ms=adapter_result.duration_ms,
                message="Agregación ejecutada correctamente.",
            )
        except DataPlatformError as error:
            result = DocumentQueryExecutionResult(
                connection_id=connection_id,
                collection=collection,
                operation=validation.operation,
                executed=False,
                validation=validation,
                row_limit=effective_rows,
                error_code=error.code,
                message=error.message,
            )
        finally:
            self._capacity.release()
            QUERY_IN_PROGRESS.labels(config.type.value).dec()
        QUERY_REQUESTS_TOTAL.labels(
            config.type.value, "aggregate", "success" if result.executed else "error"
        ).inc()
        QUERY_DURATION_SECONDS.labels(config.type.value, "aggregate").observe(
            result.duration_ms / 1000
        )
        self._audit_execution(connection_id, "execute_mongo_aggregate", payload_hash, result)
        return result

    @staticmethod
    def _record_blocked_metrics(
        engine: str,
        operation: str,
        validation: DocumentQueryValidationResult,
    ) -> None:
        QUERY_REQUESTS_TOTAL.labels(engine, operation, "blocked").inc()
        for reason in validation.blocked_reasons:
            QUERY_BLOCKED_TOTAL.labels(engine, reason.code).inc()

    @staticmethod
    def _blocked_result(
        connection_id: str,
        collection: str,
        validation: DocumentQueryValidationResult,
    ) -> DocumentQueryExecutionResult:
        return DocumentQueryExecutionResult(
            connection_id=connection_id,
            collection=collection,
            operation=validation.operation,
            executed=False,
            validation=validation,
            error_code="DOCUMENT_VALIDATION_BLOCKED",
            message="La consulta fue bloqueada y no llegó al adaptador de ejecución.",
        )

    @staticmethod
    def _payload_hash(payload: dict[str, object]) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
        return sha256(serialized.encode("utf-8")).hexdigest()

    def _audit_execution(
        self,
        connection_id: str,
        tool_name: str,
        payload_hash: str,
        result: DocumentQueryExecutionResult,
    ) -> None:
        validation = result.validation
        self._audit.record_document_query(
            tool_name=tool_name,
            connection_id=connection_id,
            operation=AuditOperation.EXECUTE,
            statement_type=validation.operation.value,
            payload_hash=payload_hash,
            executed=result.executed,
            valid=validation.valid,
            blocked=not validation.executable,
            blocked_reason_codes=tuple(issue.code for issue in validation.blocked_reasons),
            duration_ms=result.duration_ms,
            row_count=result.document_count if result.executed else None,
            error_code=result.error_code,
        )
