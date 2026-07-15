"""Tests for privacy-preserving durable query audit."""

from pathlib import Path

from app.models.audit import AuditConfig, AuditOperation
from app.repositories import SqliteAuditRepository
from app.services import AuditService, QueryValidationService


def test_audit_round_trip_stores_hash_but_not_sql_or_parameters(tmp_path: Path) -> None:
    repository = SqliteAuditRepository(tmp_path / "audit.db")
    repository.initialize()
    service = AuditService(repository, AuditConfig())
    sql = "SELECT * FROM clientes WHERE correo = 'private@example.com'"
    validation = QueryValidationService().validate(sql, "postgres")

    service.record(
        tool_name="validate_sql",
        connection_id="postgres-demo",
        operation=AuditOperation.VALIDATE,
        sql=sql,
        validation=validation,
        executed=False,
        duration_ms=1.2,
        row_count=None,
    )
    record = repository.list_records()[0]
    persisted_bytes = (tmp_path / "audit.db").read_bytes()

    assert len(record.query_hash) == 64
    assert sql.encode() not in persisted_bytes
    assert b"private@example.com" not in persisted_bytes
    assert record.blocked is False
