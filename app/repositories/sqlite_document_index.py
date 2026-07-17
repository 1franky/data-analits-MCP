"""SQLite implementation of the indexed document metadata repository."""

import sqlite3
from pathlib import Path

from app.models.rag import DocumentMetadata, IndexedDocumentSummary
from app.repositories.document_index import DocumentIndexRepository

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_documents (
    document_id TEXT PRIMARY KEY,
    source TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    connection_id TEXT,
    domain TEXT,
    document_type TEXT NOT NULL,
    version TEXT,
    content_hash TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dimensions INTEGER NOT NULL,
    indexed_at TEXT NOT NULL
);
"""


class SqliteDocumentIndexRepository(DocumentIndexRepository):
    """Store one row per indexed document, without its content or chunks."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        """Create the database and metadata table."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def upsert_document(
        self,
        metadata: DocumentMetadata,
        content_hash: str,
        chunk_count: int,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> None:
        """Replace one document's indexing state, keyed by its document_id."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rag_documents (
                    document_id, source, title, connection_id, domain, document_type,
                    version, content_hash, chunk_count, embedding_model,
                    embedding_dimensions, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    source = excluded.source,
                    title = excluded.title,
                    connection_id = excluded.connection_id,
                    domain = excluded.domain,
                    document_type = excluded.document_type,
                    version = excluded.version,
                    content_hash = excluded.content_hash,
                    chunk_count = excluded.chunk_count,
                    embedding_model = excluded.embedding_model,
                    embedding_dimensions = excluded.embedding_dimensions,
                    indexed_at = excluded.indexed_at
                """,
                (
                    metadata.document_id,
                    metadata.source,
                    metadata.title,
                    metadata.connection_id,
                    metadata.domain,
                    metadata.document_type,
                    metadata.version,
                    content_hash,
                    chunk_count,
                    embedding_model,
                    embedding_dimensions,
                    metadata.indexed_at.isoformat(),
                ),
            )

    def get_document_by_source(self, source: str) -> IndexedDocumentSummary | None:
        """Return the indexed state for one document, by its relative path."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM rag_documents WHERE source = ?",
                (source,),
            ).fetchone()
        return None if row is None else self._to_summary(row)

    def get_document_by_id(self, document_id: str) -> IndexedDocumentSummary | None:
        """Return the indexed state for one document, by its stable identifier."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM rag_documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return None if row is None else self._to_summary(row)

    def list_documents(
        self,
        connection_id: str | None = None,
        domain: str | None = None,
    ) -> tuple[IndexedDocumentSummary, ...]:
        """List indexed documents, optionally filtered by connection and/or domain."""
        query = "SELECT * FROM rag_documents WHERE 1 = 1"
        params: list[str] = []
        if connection_id is not None:
            query += " AND connection_id = ?"
            params.append(connection_id)
        if domain is not None:
            query += " AND domain = ?"
            params.append(domain)
        query += " ORDER BY source"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(self._to_summary(row) for row in rows)

    def list_sources(self) -> tuple[str, ...]:
        """Return every known document source path, for reconciling deletions."""
        with self._connect() as connection:
            rows = connection.execute("SELECT source FROM rag_documents ORDER BY source").fetchall()
        return tuple(row["source"] for row in rows)

    def delete_document(self, document_id: str) -> bool:
        """Remove one document's indexing state, returning whether it existed."""
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM rag_documents WHERE document_id = ?",
                (document_id,),
            )
            return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @staticmethod
    def _to_summary(row: sqlite3.Row) -> IndexedDocumentSummary:
        metadata = DocumentMetadata(
            document_id=row["document_id"],
            title=row["title"],
            source=row["source"],
            connection_id=row["connection_id"],
            domain=row["domain"],
            document_type=row["document_type"],
            version=row["version"],
            indexed_at=row["indexed_at"],
        )
        return IndexedDocumentSummary(
            metadata=metadata,
            content_hash=row["content_hash"],
            chunk_count=row["chunk_count"],
            embedding_model=row["embedding_model"],
            embedding_dimensions=row["embedding_dimensions"],
        )
