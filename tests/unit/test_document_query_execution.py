"""Tests ensuring blocked MongoDB requests never reach the adapter."""

from pathlib import Path
from threading import Event, Thread, Timer
from time import perf_counter

from app.models.query import QueryPolicyConfig
from tests.document_query_fakes import DocumentQueryStubAdapter, build_document_query_services


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


def test_concurrency_limit_rejects_second_query_without_adapter_call(tmp_path: Path) -> None:
    adapter = DocumentQueryStubAdapter()
    adapter.started_event = Event()
    adapter.release_event = Event()
    _connections, _validator, execution, _audit_repository, _adapter = (
        build_document_query_services(
            tmp_path / "audit.db",
            adapter=adapter,
            policy=QueryPolicyConfig(max_concurrent_queries=1),
        )
    )
    first_results: list[bool] = []

    def execute_first() -> None:
        first_results.append(execution.execute_find("mongodb-demo", "clientes", {}).executed)

    thread = Thread(target=execute_first)
    thread.start()
    assert adapter.started_event.wait(timeout=5)

    second = execution.execute_find("mongodb-demo", "clientes", {})
    adapter.release_event.set()
    thread.join(timeout=5)

    assert second.executed is False
    assert second.error_code == "QUERY_CAPACITY_EXCEEDED"
    assert first_results == [True]
    assert adapter.find_calls == 1


def test_queue_wait_seconds_allows_a_delayed_second_query_to_succeed(tmp_path: Path) -> None:
    adapter = DocumentQueryStubAdapter()
    adapter.started_event = Event()
    adapter.release_event = Event()
    _connections, _validator, execution, _audit_repository, _adapter = (
        build_document_query_services(
            tmp_path / "audit.db",
            adapter=adapter,
            policy=QueryPolicyConfig(max_concurrent_queries=1, queue_wait_seconds=2),
        )
    )
    first_results: list[bool] = []

    def execute_first() -> None:
        first_results.append(execution.execute_find("mongodb-demo", "clientes", {}).executed)

    thread = Thread(target=execute_first)
    thread.start()
    assert adapter.started_event.wait(timeout=5)

    Timer(0.2, adapter.release_event.set).start()
    second = execution.execute_find("mongodb-demo", "clientes", {})
    thread.join(timeout=5)

    assert second.executed is True
    assert first_results == [True]


def test_queue_wait_seconds_rejects_once_the_wait_window_elapses(tmp_path: Path) -> None:
    adapter = DocumentQueryStubAdapter()
    adapter.started_event = Event()
    adapter.release_event = Event()
    _connections, _validator, execution, _audit_repository, _adapter = (
        build_document_query_services(
            tmp_path / "audit.db",
            adapter=adapter,
            policy=QueryPolicyConfig(max_concurrent_queries=1, queue_wait_seconds=0.2),
        )
    )
    first_results: list[bool] = []

    def execute_first() -> None:
        first_results.append(execution.execute_find("mongodb-demo", "clientes", {}).executed)

    thread = Thread(target=execute_first)
    thread.start()
    assert adapter.started_event.wait(timeout=5)

    started_at = perf_counter()
    second = execution.execute_find("mongodb-demo", "clientes", {})
    elapsed = perf_counter() - started_at

    adapter.release_event.set()
    thread.join(timeout=5)

    assert second.executed is False
    assert second.error_code == "QUERY_CAPACITY_EXCEEDED"
    assert elapsed >= 0.2
    assert first_results == [True]
