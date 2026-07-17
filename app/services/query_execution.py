"""Validated, audited and bounded read-query execution use cases."""

from threading import BoundedSemaphore
from time import perf_counter

from app.exceptions import DataPlatformError
from app.models.audit import AuditOperation
from app.models.query import (
    QueryExecutionResult,
    QueryParameter,
    QueryPlanResult,
    QueryPolicyConfig,
    SqlValidationResult,
    ValidationIssue,
)
from app.observability.metrics import (
    QUERY_BLOCKED_TOTAL,
    QUERY_DURATION_SECONDS,
    QUERY_IN_PROGRESS,
    QUERY_QUEUE_WAIT_SECONDS,
    QUERY_REQUESTS_TOTAL,
)
from app.services.audit import AuditService
from app.services.connections import ConnectionService
from app.services.query_validation import QueryValidationService


class QueryExecutionService:
    """Ensure blocked SQL can never reach a database adapter execution method."""

    def __init__(
        self,
        connections: ConnectionService,
        validator: QueryValidationService,
        audit: AuditService,
        policy: QueryPolicyConfig,
    ) -> None:
        self._connections = connections
        self._validator = validator
        self._audit = audit
        self._policy = policy
        self._capacity = BoundedSemaphore(policy.max_concurrent_queries)

    def execute(
        self,
        connection_id: str,
        sql: str,
        parameters: dict[str, QueryParameter] | None = None,
        max_rows: int | None = None,
        timeout_seconds: int | None = None,
        tool_name: str = "execute_read_query",
    ) -> QueryExecutionResult:
        """Validate and execute one SELECT with effective connection/global limits."""
        config = self._connections.get_connection_config(connection_id)
        validation = self._validator.validate(sql, config.type.value)
        validation = self._validate_request(
            validation,
            parameters,
            max_rows,
            timeout_seconds,
        )
        if not validation.executable or validation.normalized_sql is None:
            result = self._blocked_execution(connection_id, validation)
            self._record_blocked_metrics(config.type.value, "execute", validation)
            self._audit_execution(connection_id, sql, result, tool_name)
            return result

        effective_rows = min(
            max_rows if max_rows is not None else config.max_rows,
            config.max_rows,
            self._policy.global_max_rows,
        )
        effective_timeout = min(
            timeout_seconds if timeout_seconds is not None else config.query_timeout_seconds,
            config.query_timeout_seconds,
        )
        prepared = self._validator.apply_row_limit(
            validation.normalized_sql,
            validation.dialect,
            effective_rows,
        )
        validation = self._with_limit_warning(validation, prepared.limit_reduced, effective_rows)
        wait_started_at = perf_counter()
        acquired = self._capacity.acquire(timeout=self._policy.queue_wait_seconds)
        QUERY_QUEUE_WAIT_SECONDS.labels(config.type.value).observe(perf_counter() - wait_started_at)
        if not acquired:
            result = QueryExecutionResult(
                connection_id=connection_id,
                executed=False,
                validation=validation,
                row_limit=prepared.row_limit,
                error_code="QUERY_CAPACITY_EXCEEDED",
                message="No hay capacidad disponible para ejecutar otra consulta.",
            )
            QUERY_REQUESTS_TOTAL.labels(config.type.value, "execute", "capacity_rejected").inc()
            self._audit_execution(connection_id, sql, result, tool_name)
            return result

        QUERY_IN_PROGRESS.labels(config.type.value).inc()
        try:
            adapter = self._connections.get_adapter(connection_id)
            adapter_result = adapter.execute_read_query(
                prepared.sql,
                parameters,
                prepared.row_limit,
                effective_timeout,
                self._policy.max_serialized_bytes,
            )
            result = QueryExecutionResult(
                connection_id=connection_id,
                executed=True,
                validation=validation,
                executed_sql=prepared.sql,
                columns=adapter_result.columns,
                rows=adapter_result.rows,
                row_count=len(adapter_result.rows),
                row_limit=prepared.row_limit,
                truncated=adapter_result.truncated,
                serialized_bytes=adapter_result.serialized_bytes,
                duration_ms=adapter_result.duration_ms,
                message="Consulta de lectura ejecutada correctamente.",
            )
        except DataPlatformError as error:
            result = QueryExecutionResult(
                connection_id=connection_id,
                executed=False,
                validation=validation,
                executed_sql=prepared.sql,
                row_limit=prepared.row_limit,
                error_code=error.code,
                message=error.message,
            )
        finally:
            self._capacity.release()
            QUERY_IN_PROGRESS.labels(config.type.value).dec()
        QUERY_REQUESTS_TOTAL.labels(
            config.type.value, "execute", "success" if result.executed else "error"
        ).inc()
        QUERY_DURATION_SECONDS.labels(config.type.value, "execute").observe(
            result.duration_ms / 1000
        )
        self._audit_execution(connection_id, sql, result, tool_name)
        return result

    def explain(
        self,
        connection_id: str,
        sql: str,
        parameters: dict[str, QueryParameter] | None = None,
        timeout_seconds: int | None = None,
    ) -> QueryPlanResult:
        """Generate a PostgreSQL JSON plan for one validated SELECT without ANALYZE."""
        config = self._connections.get_connection_config(connection_id)
        validation = self._validator.validate(sql, config.type.value)
        validation = self._validate_request(validation, parameters, None, timeout_seconds)
        if not validation.executable or validation.normalized_sql is None:
            result = QueryPlanResult(
                connection_id=connection_id,
                explained=False,
                validation=validation,
                error_code="SQL_VALIDATION_BLOCKED",
                message="La consulta fue bloqueada antes de generar el plan.",
            )
            self._record_blocked_metrics(config.type.value, "explain", validation)
            self._audit_plan(connection_id, sql, result)
            return result

        effective_rows = min(config.max_rows, self._policy.global_max_rows)
        effective_timeout = min(
            timeout_seconds if timeout_seconds is not None else config.query_timeout_seconds,
            config.query_timeout_seconds,
        )
        prepared = self._validator.apply_row_limit(
            validation.normalized_sql,
            validation.dialect,
            effective_rows,
        )
        validation = self._with_limit_warning(validation, prepared.limit_reduced, effective_rows)
        wait_started_at = perf_counter()
        acquired = self._capacity.acquire(timeout=self._policy.queue_wait_seconds)
        QUERY_QUEUE_WAIT_SECONDS.labels(config.type.value).observe(perf_counter() - wait_started_at)
        if not acquired:
            result = QueryPlanResult(
                connection_id=connection_id,
                explained=False,
                validation=validation,
                explained_sql=prepared.sql,
                error_code="QUERY_CAPACITY_EXCEEDED",
                message="No hay capacidad disponible para generar otro plan.",
            )
            QUERY_REQUESTS_TOTAL.labels(config.type.value, "explain", "capacity_rejected").inc()
            self._audit_plan(connection_id, sql, result)
            return result

        QUERY_IN_PROGRESS.labels(config.type.value).inc()
        try:
            adapter = self._connections.get_adapter(connection_id)
            adapter_plan = adapter.explain_read_query(
                prepared.sql,
                parameters,
                effective_timeout,
            )
            result = QueryPlanResult(
                connection_id=connection_id,
                explained=True,
                analyze=False,
                validation=validation,
                explained_sql=prepared.sql,
                plan=adapter_plan.plan,
                duration_ms=adapter_plan.duration_ms,
                message="Plan de ejecución generado sin ANALYZE.",
            )
        except DataPlatformError as error:
            result = QueryPlanResult(
                connection_id=connection_id,
                explained=False,
                validation=validation,
                explained_sql=prepared.sql,
                error_code=error.code,
                message=error.message,
            )
        finally:
            self._capacity.release()
            QUERY_IN_PROGRESS.labels(config.type.value).dec()
        QUERY_REQUESTS_TOTAL.labels(
            config.type.value, "explain", "success" if result.explained else "error"
        ).inc()
        QUERY_DURATION_SECONDS.labels(config.type.value, "explain").observe(
            result.duration_ms / 1000
        )
        self._audit_plan(connection_id, sql, result)
        return result

    def _validate_request(
        self,
        validation: SqlValidationResult,
        parameters: dict[str, QueryParameter] | None,
        max_rows: int | None,
        timeout_seconds: int | None,
    ) -> SqlValidationResult:
        provided_parameters = set(parameters or {})
        if provided_parameters != set(validation.parameter_names):
            validation = self._validator.block_for_parameter_mismatch(validation)
        if max_rows is not None and max_rows <= 0:
            validation = self._validator.add_block(
                validation,
                "QUERY_LIMIT_INVALID",
                "max_rows debe ser mayor que cero.",
            )
        if timeout_seconds is not None and timeout_seconds <= 0:
            validation = self._validator.add_block(
                validation,
                "QUERY_TIMEOUT_INVALID",
                "timeout_seconds debe ser mayor que cero.",
            )
        return validation

    @staticmethod
    def _with_limit_warning(
        validation: SqlValidationResult,
        limit_reduced: bool,
        maximum_rows: int,
    ) -> SqlValidationResult:
        if not limit_reduced:
            return validation
        warning = ValidationIssue(
            code="ROW_LIMIT_ENFORCED",
            message=f"Se aplicó un límite exterior máximo de {maximum_rows} filas.",
        )
        return validation.model_copy(update={"warnings": (*validation.warnings, warning)})

    @staticmethod
    def _record_blocked_metrics(
        engine: str,
        operation: str,
        validation: SqlValidationResult,
    ) -> None:
        QUERY_REQUESTS_TOTAL.labels(engine, operation, "blocked").inc()
        for reason in validation.blocked_reasons:
            QUERY_BLOCKED_TOTAL.labels(engine, reason.code).inc()

    @staticmethod
    def _blocked_execution(
        connection_id: str,
        validation: SqlValidationResult,
    ) -> QueryExecutionResult:
        return QueryExecutionResult(
            connection_id=connection_id,
            executed=False,
            validation=validation,
            error_code="SQL_VALIDATION_BLOCKED",
            message="La consulta fue bloqueada y no llegó al adaptador de ejecución.",
        )

    def _audit_execution(
        self,
        connection_id: str,
        sql: str,
        result: QueryExecutionResult,
        tool_name: str = "execute_read_query",
    ) -> None:
        self._audit.record(
            tool_name=tool_name,
            connection_id=connection_id,
            operation=AuditOperation.EXECUTE,
            sql=sql,
            validation=result.validation,
            executed=result.executed,
            duration_ms=result.duration_ms,
            row_count=result.row_count if result.executed else None,
            error_code=result.error_code,
        )

    def _audit_plan(
        self,
        connection_id: str,
        sql: str,
        result: QueryPlanResult,
    ) -> None:
        self._audit.record(
            tool_name="explain_query",
            connection_id=connection_id,
            operation=AuditOperation.EXPLAIN,
            sql=sql,
            validation=result.validation,
            executed=False,
            duration_ms=result.duration_ms,
            row_count=None,
            error_code=result.error_code,
        )
