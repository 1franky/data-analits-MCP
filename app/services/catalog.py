"""Metadata snapshot refresh, freshness and in-memory catalog search."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatchcase
from hashlib import sha256
from threading import Lock

from app.exceptions import CatalogRequestError, ConnectionNotFoundError, DataPlatformError
from app.models.catalog import (
    CatalogCacheStatus,
    CatalogRefreshOutcome,
    CatalogRefreshResult,
    CatalogRefreshState,
    CatalogRelationship,
    CatalogSearchMatch,
    CatalogSearchResponse,
    CatalogSnapshot,
)
from app.models.connections import (
    CatalogConfig,
    ConnectionSummary,
    SchemaInfo,
    TableDescription,
)
from app.repositories import CatalogRepository
from app.services.connections import ConnectionService

Clock = Callable[[], datetime]


class CatalogService:
    """Build and query metadata-only snapshots for configured connections."""

    def __init__(
        self,
        connections: ConnectionService,
        repository: CatalogRepository,
        config: CatalogConfig,
        clock: Clock | None = None,
    ) -> None:
        self._connections = connections
        self._repository = repository
        self._config = config
        self._clock = clock or (lambda: datetime.now(UTC))
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    @property
    def config(self) -> CatalogConfig:
        """Expose immutable scheduling policy to the composition root."""
        return self._config

    def refresh_connection(self, connection_id: str) -> CatalogRefreshResult:
        """Refresh one connection without replacing a valid snapshot on failure."""
        started_at = self._clock()
        if not self._config.enabled:
            return self._result(
                connection_id=connection_id,
                outcome=CatalogRefreshOutcome.DISABLED,
                started_at=started_at,
                completed_at=self._clock(),
                error_code="CATALOG_DISABLED",
                message="El catálogo está deshabilitado.",
            )

        summary = self._connection_summary(connection_id)
        refresh_lock = self._lock_for(connection_id)
        if not refresh_lock.acquire(blocking=False):
            return self._result(
                connection_id=connection_id,
                outcome=CatalogRefreshOutcome.ALREADY_RUNNING,
                started_at=started_at,
                completed_at=self._clock(),
                error_code="REFRESH_ALREADY_RUNNING",
                message="Ya existe un refresh en ejecución para esta conexión.",
            )

        try:
            self._repository.mark_refresh_started(connection_id, started_at)
            self._validate_capabilities(summary)
            snapshot = self._build_snapshot(connection_id)
            completed_at = self._clock()
            self._repository.save_snapshot(snapshot, started_at, completed_at)
            return self._result(
                connection_id=connection_id,
                outcome=CatalogRefreshOutcome.SUCCESS,
                started_at=started_at,
                completed_at=completed_at,
                snapshot=snapshot,
                message="Catálogo actualizado correctamente.",
            )
        except DataPlatformError as error:
            return self._record_failure(connection_id, started_at, error.code, error.message)
        except Exception:
            return self._record_failure(
                connection_id,
                started_at,
                "CATALOG_REFRESH_ERROR",
                "No fue posible actualizar el catálogo.",
            )
        finally:
            refresh_lock.release()

    def refresh_all(self) -> tuple[CatalogRefreshResult, ...]:
        """Refresh every enabled connection in deterministic order."""
        return tuple(
            self.refresh_connection(summary.id)
            for summary in self._connections.list_connections()
            if summary.enabled
        )

    def get_cache_status(
        self,
        connection_id: str | None = None,
    ) -> tuple[CatalogCacheStatus, ...]:
        """Return last-attempt state and computed staleness."""
        summaries = self._selected_connections(connection_id)
        now = self._clock()
        stale_after = timedelta(minutes=self._config.stale_after_minutes)
        statuses: list[CatalogCacheStatus] = []
        for summary in summaries:
            snapshot = self._repository.get_snapshot(summary.id)
            record = self._repository.get_refresh_record(summary.id)
            stale = snapshot is None or now - snapshot.refreshed_at >= stale_after
            statuses.append(
                CatalogCacheStatus(
                    connection_id=summary.id,
                    state=record.state if record else CatalogRefreshState.NEVER,
                    has_snapshot=snapshot is not None,
                    stale=stale,
                    last_refreshed_at=snapshot.refreshed_at if snapshot else None,
                    last_attempt_started_at=record.started_at if record else None,
                    last_attempt_completed_at=record.completed_at if record else None,
                    schema_hash=snapshot.schema_hash if snapshot else None,
                    error_code=record.error_code if record else None,
                    message=record.message if record else None,
                )
            )
        return tuple(statuses)

    def search(
        self,
        query: str,
        connection_id: str | None = None,
        max_results: int = 20,
    ) -> CatalogSearchResponse:
        """Search table names, column names and authorized comments."""
        normalized_query = " ".join(query.split())
        if not normalized_query:
            raise CatalogRequestError(
                code="CATALOG_QUERY_EMPTY",
                message="La búsqueda del catálogo no puede estar vacía.",
            )
        if not 1 <= max_results <= 100:
            raise CatalogRequestError(
                code="CATALOG_RESULT_LIMIT_ERROR",
                message="max_results debe estar entre 1 y 100.",
            )

        summaries = self._selected_connections(connection_id)
        selected_ids = {summary.id for summary in summaries}
        terms = tuple(term.casefold() for term in normalized_query.split())
        matches: list[CatalogSearchMatch] = []
        for snapshot in self._repository.list_snapshots():
            if snapshot.connection_id not in selected_ids:
                continue
            relationships = self._relationships(snapshot.tables)
            for table in snapshot.tables:
                match = self._match_table(snapshot, table, terms, relationships)
                if match is not None:
                    matches.append(match)

        matches.sort(
            key=lambda item: (-item.score, item.connection_id, item.schema_name, item.table)
        )
        return CatalogSearchResponse(
            query=normalized_query,
            matches=tuple(matches[:max_results]),
            cache_statuses=self.get_cache_status(connection_id),
        )

    def _build_snapshot(self, connection_id: str) -> CatalogSnapshot:
        adapter = self._connections.get_adapter(connection_id)
        excluded_schemas = {name.casefold() for name in self._config.excluded_schemas}
        schemas = tuple(
            schema
            for schema in adapter.list_schemas()
            if schema.name.casefold() not in excluded_schemas
        )
        tables: list[TableDescription] = []
        for schema in schemas:
            for table in adapter.list_tables(schema.name):
                if self._table_is_included(table.schema_name, table.name):
                    tables.append(adapter.describe_table(table.schema_name, table.name))
        ordered_tables = tuple(sorted(tables, key=lambda item: (item.schema_name, item.name)))
        refreshed_at = self._clock()
        return CatalogSnapshot(
            connection_id=connection_id,
            refreshed_at=refreshed_at,
            schema_hash=self._schema_hash(schemas, ordered_tables),
            schemas=schemas,
            tables=ordered_tables,
        )

    def _record_failure(
        self,
        connection_id: str,
        started_at: datetime,
        error_code: str,
        message: str,
    ) -> CatalogRefreshResult:
        completed_at = self._clock()
        self._repository.mark_refresh_failed(
            connection_id,
            started_at,
            completed_at,
            error_code,
            message,
        )
        return self._result(
            connection_id=connection_id,
            outcome=CatalogRefreshOutcome.ERROR,
            started_at=started_at,
            completed_at=completed_at,
            error_code=error_code,
            message=message,
        )

    def _selected_connections(self, connection_id: str | None) -> tuple[ConnectionSummary, ...]:
        summaries = self._connections.list_connections()
        if connection_id is None:
            return summaries
        return (self._connection_summary(connection_id),)

    def _connection_summary(self, connection_id: str) -> ConnectionSummary:
        for summary in self._connections.list_connections():
            if summary.id == connection_id:
                return summary
        raise ConnectionNotFoundError(connection_id)

    @staticmethod
    def _validate_capabilities(summary: ConnectionSummary) -> None:
        capabilities = summary.capabilities
        if (
            capabilities is None
            or not capabilities.list_schemas
            or not capabilities.list_tables
            or not capabilities.describe_table
        ):
            raise CatalogRequestError(
                code="CATALOG_CAPABILITY_UNAVAILABLE",
                message=f"La conexión '{summary.id}' no soporta catálogo de metadata.",
            )

    def _lock_for(self, connection_id: str) -> Lock:
        with self._locks_guard:
            return self._locks.setdefault(connection_id, Lock())

    def _table_is_included(self, schema: str, table: str) -> bool:
        qualified_name = f"{schema}.{table}"
        included = any(
            fnmatchcase(qualified_name, pattern) or fnmatchcase(table, pattern)
            for pattern in self._config.include_table_patterns
        )
        excluded = any(
            fnmatchcase(qualified_name, pattern) or fnmatchcase(table, pattern)
            for pattern in self._config.exclude_table_patterns
        )
        return included and not excluded

    @staticmethod
    def _schema_hash(
        schemas: tuple[SchemaInfo, ...],
        tables: tuple[TableDescription, ...],
    ) -> str:
        payload = {
            "schemas": [schema.model_dump(mode="json") for schema in schemas],
            "tables": [table.model_dump(mode="json", by_alias=True) for table in tables],
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _relationships(
        tables: tuple[TableDescription, ...],
    ) -> tuple[CatalogRelationship, ...]:
        relationships: list[CatalogRelationship] = []
        for table in tables:
            relationships.extend(
                CatalogRelationship(
                    name=foreign_key.name,
                    source_schema=table.schema_name,
                    source_table=table.name,
                    source_columns=foreign_key.columns,
                    target_schema=foreign_key.referenced_schema,
                    target_table=foreign_key.referenced_table,
                    target_columns=foreign_key.referenced_columns,
                )
                for foreign_key in table.foreign_keys
            )
        return tuple(relationships)

    @staticmethod
    def _match_table(
        snapshot: CatalogSnapshot,
        table: TableDescription,
        terms: tuple[str, ...],
        relationships: tuple[CatalogRelationship, ...],
    ) -> CatalogSearchMatch | None:
        column_text = " ".join(
            f"{column.name} {column.description or ''}" for column in table.columns
        )
        searchable = " ".join(
            (table.schema_name, table.name, table.description or "", column_text)
        ).casefold()
        if not all(term in searchable for term in terms):
            return None

        matched_columns = tuple(
            column.name
            for column in table.columns
            if any(term in f"{column.name} {column.description or ''}".casefold() for term in terms)
        )
        name = table.name.casefold()
        qualified_name = f"{table.schema_name}.{table.name}".casefold()
        query_text = " ".join(terms)
        score = 100 if query_text in {name, qualified_name} else 0
        score += 60 if all(term in name for term in terms) else 0
        score += min(len(matched_columns) * 10, 30)
        if table.description and any(term in table.description.casefold() for term in terms):
            score += 10
        relevant_relationships = tuple(
            relationship
            for relationship in relationships
            if (
                relationship.source_schema == table.schema_name
                and relationship.source_table == table.name
            )
            or (
                relationship.target_schema == table.schema_name
                and relationship.target_table == table.name
            )
        )
        return CatalogSearchMatch(
            connection_id=snapshot.connection_id,
            schema=table.schema_name,
            table=table.name,
            description=table.description,
            matched_columns=matched_columns,
            score=score,
            relationships=relevant_relationships,
        )

    @staticmethod
    def _result(
        connection_id: str,
        outcome: CatalogRefreshOutcome,
        started_at: datetime,
        completed_at: datetime,
        message: str,
        snapshot: CatalogSnapshot | None = None,
        error_code: str | None = None,
    ) -> CatalogRefreshResult:
        return CatalogRefreshResult(
            connection_id=connection_id,
            outcome=outcome,
            refreshed=outcome is CatalogRefreshOutcome.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
            schema_hash=snapshot.schema_hash if snapshot else None,
            schemas_count=len(snapshot.schemas) if snapshot else 0,
            tables_count=len(snapshot.tables) if snapshot else 0,
            error_code=error_code,
            message=message,
        )
