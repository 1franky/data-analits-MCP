"""SQLite append-only query audit repository."""

import json
import sqlite3
from pathlib import Path

from app.models.audit import AuditRecord
from app.repositories.audit import AuditRepository

_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_audit_events (
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

CREATE INDEX IF NOT EXISTS query_audit_timestamp_idx
ON query_audit_events (timestamp);
"""


class SqliteAuditRepository(AuditRepository):
    """Persist security events without SQL text, parameters or result values."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        """Create the database and append-only event table."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def append(self, record: AuditRecord) -> None:
        """Insert one event using bound values."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO query_audit_events (
                    event_id, timestamp, tool_name, connection_id, operation,
                    statement_type, query_hash, validation_valid, executed,
                    blocked, blocked_reason_codes, duration_ms, row_count,
                    status, error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_id,
                    record.timestamp.isoformat(),
                    record.tool_name,
                    record.connection_id,
                    record.operation.value,
                    record.statement_type,
                    record.query_hash,
                    record.validation_valid,
                    record.executed,
                    record.blocked,
                    json.dumps(record.blocked_reason_codes, separators=(",", ":")),
                    record.duration_ms,
                    record.row_count,
                    record.status.value,
                    record.error_code,
                ),
            )

    def list_records(self) -> tuple[AuditRecord, ...]:
        """Load events in durable insertion order."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    event_id, timestamp, tool_name, connection_id, operation,
                    statement_type, query_hash, validation_valid, executed,
                    blocked, blocked_reason_codes, duration_ms, row_count,
                    status, error_code
                FROM query_audit_events
                ORDER BY rowid
                """
            ).fetchall()
        return tuple(
            AuditRecord.model_validate(
                {
                    **dict(row),
                    "blocked_reason_codes": json.loads(row["blocked_reason_codes"]),
                }
            )
            for row in rows
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
