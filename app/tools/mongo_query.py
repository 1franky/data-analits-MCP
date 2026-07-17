"""MCP tools for MongoDB collection listing, validation and bounded reads."""

import json
from hashlib import sha256
from time import perf_counter
from typing import Annotated, Literal

from pydantic import Field, JsonValue

from app.container import (
    get_audit_service,
    get_connection_service,
    get_document_query_execution_service,
    get_document_query_validation_service,
)
from app.models.audit import AuditOperation
from app.models.document_query import (
    DocumentQueryExecutionResult,
    DocumentQueryValidationResult,
    MongoCollectionListResponse,
)


def list_mongo_collections(connection_id: str) -> MongoCollectionListResponse:
    """List visible, non-system collections for a MongoDB connection."""
    adapter = get_connection_service().get_document_adapter(connection_id)
    return MongoCollectionListResponse(
        connection_id=connection_id,
        collections=adapter.list_collections(),
    )


def validate_mongo_query(
    connection_id: str,
    collection: str,
    operation: Literal["find", "aggregate"],
    filter: dict[str, JsonValue] | None = None,
    pipeline: list[dict[str, JsonValue]] | None = None,
) -> DocumentQueryValidationResult:
    """Validate a find filter or aggregation pipeline without executing it."""
    started_at = perf_counter()
    get_connection_service().get_connection_config(connection_id)
    validator = get_document_query_validation_service()
    payload: dict[str, object]
    if operation == "find":
        result = validator.validate_find(collection, filter or {}, None)
        payload = {"filter": filter or {}}
    else:
        result = validator.validate_aggregate(collection, pipeline or [])
        payload = {"pipeline": pipeline or []}
    payload_hash = sha256(
        json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    get_audit_service().record_document_query(
        tool_name="validate_mongo_query",
        connection_id=connection_id,
        operation=AuditOperation.VALIDATE,
        statement_type=result.operation.value,
        payload_hash=payload_hash,
        executed=False,
        valid=result.valid,
        blocked=not result.executable,
        blocked_reason_codes=tuple(issue.code for issue in result.blocked_reasons),
        duration_ms=(perf_counter() - started_at) * 1_000,
        row_count=None,
    )
    return result


def execute_mongo_find(
    connection_id: str,
    collection: str,
    filter: dict[str, JsonValue],
    projection: dict[str, JsonValue] | None = None,
    max_rows: Annotated[int, Field(ge=1, le=1_000_000)] | None = None,
    timeout_seconds: Annotated[int, Field(ge=1, le=3_600)] | None = None,
) -> DocumentQueryExecutionResult:
    """Execute one validated find() under row, byte, timeout and concurrency limits."""
    return get_document_query_execution_service().execute_find(
        connection_id=connection_id,
        collection=collection,
        filter=filter,
        projection=projection,
        max_rows=max_rows,
        timeout_seconds=timeout_seconds,
    )


def execute_mongo_aggregate(
    connection_id: str,
    collection: str,
    pipeline: list[dict[str, JsonValue]],
    max_rows: Annotated[int, Field(ge=1, le=1_000_000)] | None = None,
    timeout_seconds: Annotated[int, Field(ge=1, le=3_600)] | None = None,
) -> DocumentQueryExecutionResult:
    """Execute one validated aggregation pipeline under the same limits as find()."""
    return get_document_query_execution_service().execute_aggregate(
        connection_id=connection_id,
        collection=collection,
        pipeline=pipeline,
        max_rows=max_rows,
        timeout_seconds=timeout_seconds,
    )
