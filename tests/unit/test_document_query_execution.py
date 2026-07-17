"""Tests ensuring blocked MongoDB requests never reach the adapter."""

from pathlib import Path

from tests.document_query_fakes import build_document_query_services


def test_valid_find_reaches_the_adapter(tmp_path: Path) -> None:
    _connections, _validator, execution, _audit_repository, adapter = build_document_query_services(
        tmp_path / "audit.db"
    )

    result = execution.execute_find("mongodb-demo", "clientes", {"nombre": "Ana"})

    assert result.executed is True
    assert result.documents == ({"_id": 1, "nombre": "Ana"},)
    assert adapter.find_calls == 1


def test_valid_aggregate_reaches_the_adapter(tmp_path: Path) -> None:
    _connections, _validator, execution, _audit_repository, adapter = build_document_query_services(
        tmp_path / "audit.db"
    )

    result = execution.execute_aggregate(
        "mongodb-demo",
        "ventas",
        [{"$match": {"cliente_id": 1}}, {"$group": {"_id": None, "total": {"$sum": 1}}}],
    )

    assert result.executed is True
    assert adapter.aggregate_calls == 1


def test_out_stage_never_reaches_the_adapter(tmp_path: Path) -> None:
    _connections, _validator, execution, audit_repository, adapter = build_document_query_services(
        tmp_path / "audit.db"
    )

    result = execution.execute_aggregate("mongodb-demo", "ventas", [{"$out": "otra"}])

    assert result.executed is False
    assert result.error_code == "DOCUMENT_VALIDATION_BLOCKED"
    assert adapter.aggregate_calls == 0
    tool_names = {record.tool_name for record in audit_repository.list_records()}
    assert "execute_mongo_aggregate" in tool_names


def test_unknown_operator_never_reaches_the_adapter(tmp_path: Path) -> None:
    _connections, _validator, execution, _audit_repository, adapter = build_document_query_services(
        tmp_path / "audit.db"
    )

    result = execution.execute_find("mongodb-demo", "clientes", {"$madeUpOperator": 1})

    assert result.executed is False
    assert adapter.find_calls == 0


def test_adapter_failure_is_normalized(tmp_path: Path) -> None:
    _connections, _validator, execution, _audit_repository, adapter = build_document_query_services(
        tmp_path / "audit.db"
    )
    adapter.fail = True

    result = execution.execute_find("mongodb-demo", "clientes", {})

    assert result.executed is False
    assert result.error_code == "DATABASE_QUERY_ERROR"


def test_audit_never_persists_filter_or_pipeline_in_plain_text(tmp_path: Path) -> None:
    _connections, _validator, execution, audit_repository, _adapter = build_document_query_services(
        tmp_path / "audit.db"
    )

    execution.execute_find("mongodb-demo", "clientes", {"correo_secreto_unico": "x@example.com"})

    for record in audit_repository.list_records():
        dumped = record.model_dump_json()
        assert "correo_secreto_unico" not in dumped
        assert "x@example.com" not in dumped
