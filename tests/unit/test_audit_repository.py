"""Tests for privacy-preserving durable query audit."""

import sqlite3
from pathlib import Path

from app.models.audit import AuditConfig, AuditOperation, AuditStatus
from app.models.generation import GenerationOutcome
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


def test_record_generation_stores_only_prompt_and_sql_hashes(tmp_path: Path) -> None:
    repository = SqliteAuditRepository(tmp_path / "audit.db")
    repository.initialize()
    service = AuditService(repository, AuditConfig())
    prompt = "dame las ventas del correo private@example.com"
    sql = "SELECT * FROM ventas WHERE correo = 'private@example.com'"
    validation = QueryValidationService().validate(sql, "postgres")

    service.record_generation(
        tool_name="generate_sql",
        connection_id="postgres-demo",
        operation=AuditOperation.GENERATE,
        prompt=prompt,
        sql=sql,
        outcome=GenerationOutcome.GENERATED,
        validation=validation,
        executed=False,
        duration_ms=3.4,
        row_count=None,
    )
    record = repository.list_records()[0]
    persisted_bytes = (tmp_path / "audit.db").read_bytes()

    assert record.status is AuditStatus.SUCCESS
    assert len(record.query_hash) == 64
    assert record.prompt_hash is not None
    assert len(record.prompt_hash) == 64
    assert prompt.encode() not in persisted_bytes
    assert sql.encode() not in persisted_bytes
    assert b"private@example.com" not in persisted_bytes


def test_prompt_hash_column_is_added_to_a_pre_sprint5_database(tmp_path: Path) -> None:
    path = tmp_path / "legacy_audit.db"
    with sqlite3.connect(path) as legacy_connection:
        legacy_connection.executescript(
            """
            CREATE TABLE query_audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                connection_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                statement_type TEXT NOT NULL,
                query_hash TEXT NOT NULL,
                validation_valid INTEGER NOT NULL,
                executed INTEGER NOT NULL,
                blocked INTEGER NOT NULL,
                blocked_reason_codes TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                row_count INTEGER,
                status TEXT NOT NULL,
                error_code TEXT
            );
            """
        )

    repository = SqliteAuditRepository(path)
    repository.initialize()

    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(query_audit_events)")}
    assert "prompt_hash" in columns
