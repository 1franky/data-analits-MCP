"""SQLite implementation of the atomic metadata catalog repository."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.models.catalog import CatalogRefreshRecord, CatalogRefreshState, CatalogSnapshot
from app.repositories.catalog import CatalogRepository

_SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_snapshots (
    connection_id TEXT PRIMARY KEY,
    refreshed_at TEXT NOT NULL,
    schema_hash TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_refresh_status (
    connection_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error_code TEXT,
    message TEXT
);
"""


class SqliteCatalogRepository(CatalogRepository):
    """Store one JSON metadata snapshot per connection in SQLite."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        """Create tables and normalize refreshes interrupted by a restart."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            connection.execute(
                """
                UPDATE catalog_refresh_status
                SET state = ?, completed_at = ?, error_code = ?, message = ?
                WHERE state = ?
                """,
                (
                    CatalogRefreshState.ERROR.value,
                    datetime.now(UTC).isoformat(),
                    "REFRESH_INTERRUPTED",
                    "El refresh anterior fue interrumpido por un reinicio.",
                    CatalogRefreshState.REFRESHING.value,
                ),
            )

    def mark_refresh_started(self, connection_id: str, started_at: datetime) -> None:
        """Persist an in-progress attempt without touching the snapshot."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO catalog_refresh_status (
                    connection_id, state, started_at, completed_at, error_code, message
                ) VALUES (?, ?, ?, NULL, NULL, NULL)
                ON CONFLICT(connection_id) DO UPDATE SET
                    state = excluded.state,
                    started_at = excluded.started_at,
                    completed_at = NULL,
                    error_code = NULL,
                    message = NULL
                """,
                (
                    connection_id,
                    CatalogRefreshState.REFRESHING.value,
                    started_at.isoformat(),
                ),
            )

    def save_snapshot(
        self,
        snapshot: CatalogSnapshot,
        started_at: datetime,
        completed_at: datetime,
    ) -> None:
        """Replace snapshot and success status within one transaction."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO catalog_snapshots (
                    connection_id, refreshed_at, schema_hash, payload
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(connection_id) DO UPDATE SET
                    refreshed_at = excluded.refreshed_at,
                    schema_hash = excluded.schema_hash,
                    payload = excluded.payload
                """,
                (
                    snapshot.connection_id,
                    snapshot.refreshed_at.isoformat(),
                    snapshot.schema_hash,
                    snapshot.model_dump_json(),
                ),
            )
            connection.execute(
                """
                INSERT INTO catalog_refresh_status (
                    connection_id, state, started_at, completed_at, error_code, message
                ) VALUES (?, ?, ?, ?, NULL, ?)
                ON CONFLICT(connection_id) DO UPDATE SET
                    state = excluded.state,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    error_code = NULL,
                    message = excluded.message
                """,
                (
                    snapshot.connection_id,
                    CatalogRefreshState.SUCCESS.value,
                    started_at.isoformat(),
                    completed_at.isoformat(),
                    "Catálogo actualizado correctamente.",
                ),
            )

    def mark_refresh_failed(
        self,
        connection_id: str,
        started_at: datetime,
        completed_at: datetime,
        error_code: str,
        message: str,
    ) -> None:
        """Persist failure status while retaining catalog_snapshots."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO catalog_refresh_status (
                    connection_id, state, started_at, completed_at, error_code, message
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(connection_id) DO UPDATE SET
                    state = excluded.state,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    error_code = excluded.error_code,
                    message = excluded.message
                """,
                (
                    connection_id,
                    CatalogRefreshState.ERROR.value,
                    started_at.isoformat(),
                    completed_at.isoformat(),
                    error_code,
                    message,
                ),
            )

    def get_snapshot(self, connection_id: str) -> CatalogSnapshot | None:
        """Load and validate one stored snapshot."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM catalog_snapshots WHERE connection_id = ?",
                (connection_id,),
            ).fetchone()
        return None if row is None else CatalogSnapshot.model_validate_json(row["payload"])

    def list_snapshots(self) -> tuple[CatalogSnapshot, ...]:
        """Load all snapshots ordered by connection ID."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM catalog_snapshots ORDER BY connection_id"
            ).fetchall()
        return tuple(CatalogSnapshot.model_validate_json(row["payload"]) for row in rows)

    def get_refresh_record(self, connection_id: str) -> CatalogRefreshRecord | None:
        """Load the most recent refresh state."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT connection_id, state, started_at, completed_at, error_code, message
                FROM catalog_refresh_status
                WHERE connection_id = ?
                """,
                (connection_id,),
            ).fetchone()
        if row is None:
            return None
        return CatalogRefreshRecord.model_validate(dict(row))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
