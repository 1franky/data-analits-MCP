"""Unit tests for the allowlist-based MongoDB find/aggregate validator."""

from pydantic import JsonValue

from app.models.document_query import DocumentOperationType
from app.services.document_query_validation import DocumentQueryValidationService


def _codes(result: object) -> set[str]:
    return {issue.code for issue in result.blocked_reasons}  # type: ignore[attr-defined]


def test_valid_find_filter_is_executable() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_find(
        "ventas",
        {"$and": [{"cantidad": {"$gt": 1}}, {"cliente_id": {"$in": [1, 2, 3]}}]},
        {"nombre": 1},
    )

    assert result.valid is True
    assert result.executable is True
    assert result.operation is DocumentOperationType.FIND
    assert result.blocked_reasons == ()


def test_valid_aggregate_pipeline_is_executable() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_aggregate(
        "ventas",
        [
            {"$match": {"cliente_id": 1}},
            {"$group": {"_id": "$producto_id", "total": {"$sum": "$cantidad"}}},
            {"$sort": {"total": -1}},
            {"$limit": 10},
        ],
    )

    assert result.valid is True
    assert result.executable is True
    assert result.operation is DocumentOperationType.AGGREGATE


def test_out_stage_is_blocked_explicitly() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_aggregate("ventas", [{"$out": "otra_coleccion"}])

    assert result.executable is False
    assert "STAGE_NOT_ALLOWED" in _codes(result)


def test_merge_stage_is_blocked_explicitly() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_aggregate("ventas", [{"$merge": "otra_coleccion"}])

    assert result.executable is False
    assert "STAGE_NOT_ALLOWED" in _codes(result)


def test_where_operator_with_js_is_blocked() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_find("ventas", {"$where": "function() { return true; }"}, None)

    assert result.executable is False
    assert "OPERATOR_NOT_ALLOWED" in _codes(result)


def test_unknown_operator_is_blocked() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_find("ventas", {"$totallyMadeUp": 1}, None)

    assert result.executable is False
    assert "OPERATOR_NOT_ALLOWED" in _codes(result)


def test_unknown_stage_is_blocked() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_aggregate("ventas", [{"$notARealStage": {}}])

    assert result.executable is False
    assert "STAGE_NOT_ALLOWED" in _codes(result)


def test_deeply_nested_payload_is_blocked() -> None:
    service = DocumentQueryValidationService()
    nested: dict[str, JsonValue] = {"$eq": 1}
    for _ in range(40):
        nested = {"$and": [nested]}

    result = service.validate_find("ventas", nested, None)

    assert result.executable is False
    assert "NESTING_TOO_DEEP" in _codes(result)


def test_invalid_collection_name_is_blocked() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_find("$system.indexes", {}, None)

    assert result.executable is False
    assert "COLLECTION_NAME_INVALID" in _codes(result)


def test_empty_collection_name_is_blocked() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_find("", {}, None)

    assert result.executable is False
    assert "COLLECTION_NAME_INVALID" in _codes(result)


def test_stage_with_more_than_one_key_is_blocked() -> None:
    service = DocumentQueryValidationService()

    result = service.validate_aggregate("ventas", [{"$match": {}, "$limit": 1}])

    assert result.executable is False
    assert "STAGE_SHAPE_INVALID" in _codes(result)
