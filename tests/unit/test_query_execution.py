"""Tests that only validated reads reach adapters and that every decision is audited."""

from pathlib import Path
from threading import Event, Thread

from app.models.audit import AuditStatus
from app.models.query import QueryPolicyConfig
from tests.factories import make_connection_config
from tests.query_fakes import QueryStubAdapter, build_query_services


def test_execute_select_enforces_limits_parameters_and_audit(tmp_path: Path) -> None:
    _connections, _validator, service, repository, adapter = build_query_services(
        tmp_path / "audit.db",
        connection=make_connection_config(max_rows=50, query_timeout_seconds=20),
        policy=QueryPolicyConfig(global_max_rows=25),
    )

    result = service.execute(
        "postgres-demo",
        "SELECT id, nombre FROM productos WHERE id >= %(minimum)s LIMIT 500",
        parameters={"minimum": 1},
        max_rows=40,
        timeout_seconds=30,
    )
    audit = repository.list_records()[0]

    assert result.executed is True
    assert result.row_limit == 25
    assert result.executed_sql is not None and result.executed_sql.endswith("LIMIT 25")
    assert result.columns == ("id", "nombre")
    assert result.row_count == 2
    assert adapter.execute_calls == 1
    assert adapter.last_parameters == {"minimum": 1}
    assert adapter.last_timeout_seconds == 20
    assert audit.executed is True
    assert audit.status is AuditStatus.SUCCESS
    assert len(audit.query_hash) == 64


def test_write_sql_is_returned_for_review_but_never_reaches_adapter(tmp_path: Path) -> None:
    _connections, _validator, service, repository, adapter = build_query_services(
        tmp_path / "audit.db"
    )
    sql = "UPDATE productos SET precio = precio * 1.10 WHERE stock = 0"

    result = service.execute("postgres-demo", sql)
    audit = repository.list_records()[0]

    assert result.executed is False
    assert result.validation.normalized_sql == sql
    assert result.validation.warnings[0].code == "WRITE_IMPACT_WARNING"
    assert result.error_code == "SQL_VALIDATION_BLOCKED"
    assert adapter.execute_calls == 0
    assert audit.blocked is True
    assert audit.status is AuditStatus.BLOCKED
    assert sql not in audit.model_dump_json()


def test_parameter_mismatch_and_invalid_limit_never_reach_adapter(tmp_path: Path) -> None:
    _connections, _validator, service, _repository, adapter = build_query_services(
        tmp_path / "audit.db"
    )

    mismatch = service.execute(
        "postgres-demo",
        "SELECT * FROM ventas WHERE id = %(id)s",
        parameters={"other": 1},
    )
    bad_limit = service.execute("postgres-demo", "SELECT * FROM ventas", max_rows=0)

    assert mismatch.executed is False
    assert mismatch.validation.blocked_reasons[-1].code == "QUERY_PARAMETERS_MISMATCH"
    assert bad_limit.executed is False
    assert bad_limit.validation.blocked_reasons[-1].code == "QUERY_LIMIT_INVALID"
    assert adapter.execute_calls == 0


def test_explain_accepts_only_read_queries_and_never_analyzes(tmp_path: Path) -> None:
    _connections, _validator, service, repository, adapter = build_query_services(
        tmp_path / "audit.db"
    )

    explained = service.explain("postgres-demo", "SELECT * FROM productos")
    blocked = service.explain("postgres-demo", "DELETE FROM productos")

    assert explained.explained is True
    assert explained.analyze is False
    assert explained.plan is not None
    assert blocked.explained is False
    assert adapter.explain_calls == 1
    assert repository.list_records()[1].status is AuditStatus.BLOCKED


def test_concurrency_limit_rejects_second_query_without_adapter_call(tmp_path: Path) -> None:
    adapter = QueryStubAdapter()
    adapter.started_event = Event()
    adapter.release_event = Event()
    _connections, _validator, service, _repository, _adapter = build_query_services(
        tmp_path / "audit.db",
        adapter=adapter,
        policy=QueryPolicyConfig(max_concurrent_queries=1),
    )
    first_results: list[bool] = []

    def execute_first() -> None:
        first_results.append(service.execute("postgres-demo", "SELECT 1").executed)

    thread = Thread(target=execute_first)
    thread.start()
    assert adapter.started_event.wait(timeout=5)

    second = service.execute("postgres-demo", "SELECT 2")
    adapter.release_event.set()
    thread.join(timeout=5)

    assert second.executed is False
    assert second.error_code == "QUERY_CAPACITY_EXCEEDED"
    assert first_results == [True]
    assert adapter.execute_calls == 1
