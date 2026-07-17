"""Read-only MariaDB metadata, query and plan adapter."""

import base64
import json
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal, NoReturn, cast

import pymysql
import pymysql.cursors
from pydantic import SecretStr

from app.adapters.base import SqlDatabaseAdapter
from app.exceptions import (
    ConfigurationError,
    DatabaseObjectNotFoundError,
    DatabaseOperationError,
)
from app.models.connections import (
    ColumnInfo,
    ConnectionCapabilities,
    ConnectionConfig,
    ConnectionTestResult,
    ForeignKeyInfo,
    ProcedureInfo,
    QueryLanguage,
    SchemaInfo,
    TableDescription,
    TableInfo,
    TriggerInfo,
    UniqueKeyInfo,
)
from app.models.query import (
    AdapterQueryPlan,
    AdapterQueryResult,
    QueryParameter,
    SerializedValue,
)

_ALLOWED_MARIADB_OPTIONS = {
    "charset",
    "ssl_ca",
    "ssl_cert",
    "ssl_key",
    "ssl_verify_cert",
}

_STATEMENT_TIMEOUT_ERROR_CODES = {1969}
_NAMED_PLACEHOLDER_PATTERN = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


class MariaDbAdapter(SqlDatabaseAdapter):
    """MariaDB adapter protected by readonly sessions and bounded operations."""

    CAPABILITIES = ConnectionCapabilities(
        query_language=QueryLanguage.SQL,
        test_connection=True,
        list_schemas=True,
        list_tables=True,
        describe_table=True,
        primary_keys=True,
        foreign_keys=True,
        execute_read_query=True,
        explain_query=True,
        list_procedures=True,
        list_triggers=True,
    )

    def __init__(self, config: ConnectionConfig, password: SecretStr) -> None:
        if config.type.value != "mariadb":
            raise ConfigurationError(
                code="MARIADB_CONFIG_TYPE_ERROR",
                message="MariaDbAdapter requiere una conexión de tipo mariadb.",
            )
        invalid_options = set(config.options).difference(_ALLOWED_MARIADB_OPTIONS)
        if invalid_options:
            names = ", ".join(sorted(invalid_options))
            raise ConfigurationError(
                code="MARIADB_OPTIONS_ERROR",
                message=f"Opciones MariaDB no soportadas: {names}",
            )
        self._config = config
        self._password = password

    @property
    def capabilities(self) -> ConnectionCapabilities:
        """Return MariaDB metadata capabilities."""
        return self.CAPABILITIES

    def test_connection(self) -> ConnectionTestResult:
        """Open a read-only session and execute a constant liveness query."""
        started_at = perf_counter()
        try:
            with (
                self._connect_readonly() as connection,
                connection.cursor(pymysql.cursors.DictCursor) as cursor,
            ):
                cursor.execute("SELECT 1 AS value")
                row = cursor.fetchone()
            success = row is not None and row["value"] == 1
        except pymysql.MySQLError as error:
            return ConnectionTestResult(
                connection_id=self._config.id,
                success=False,
                latency_ms=self._elapsed_ms(started_at),
                error_code=str(error.args[0]) if error.args else "DATABASE_CONNECTION_ERROR",
                message="No fue posible conectar con MariaDB.",
            )

        return ConnectionTestResult(
            connection_id=self._config.id,
            success=success,
            latency_ms=self._elapsed_ms(started_at),
            error_code=None if success else "DATABASE_LIVENESS_ERROR",
            message="Conexión MariaDB disponible." if success else "Respuesta MariaDB inválida.",
        )

    def list_schemas(self) -> tuple[SchemaInfo, ...]:
        """List the single schema backing this connection (schema == database in MariaDB)."""
        query = """
            SELECT SCHEMA_NAME AS name
            FROM information_schema.SCHEMATA
            WHERE SCHEMA_NAME = %s
        """
        try:
            with (
                self._connect_readonly() as connection,
                connection.cursor(pymysql.cursors.DictCursor) as cursor,
            ):
                cursor.execute(query, (self._config.database,))
                rows = cursor.fetchall()
        except pymysql.MySQLError:
            self._raise_metadata_error()
        return tuple(SchemaInfo(name=cast(str, row["name"])) for row in rows)

    def list_tables(self, schema: str | None = None) -> tuple[TableInfo, ...]:
        """List base tables visible in the connection's database."""
        target_schema = schema or self._config.database
        if target_schema != self._config.database:
            return ()
        query = """
            SELECT TABLE_NAME AS table_name
            FROM information_schema.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
              AND TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
        """
        try:
            with (
                self._connect_readonly() as connection,
                connection.cursor(pymysql.cursors.DictCursor) as cursor,
            ):
                cursor.execute(query, (target_schema,))
                rows = cursor.fetchall()
        except pymysql.MySQLError:
            self._raise_metadata_error()
        return tuple(
            TableInfo(schema=target_schema, name=cast(str, row["table_name"]), kind="table")
            for row in rows
        )

    def describe_table(self, schema: str, table: str) -> TableDescription:
        """Describe visible columns, primary key, unique keys and foreign keys."""
        if schema != self._config.database:
            raise DatabaseObjectNotFoundError(schema, table)
        try:
            with self._connect_readonly() as connection:
                columns = self._load_columns(connection, schema, table)
                if not columns:
                    raise DatabaseObjectNotFoundError(schema, table)
                description = self._load_table_comment(connection, schema, table)
                primary_key = self._load_primary_key(connection, schema, table)
                unique_keys = self._load_unique_keys(connection, schema, table)
                foreign_keys = self._load_foreign_keys(connection, schema, table)
        except pymysql.MySQLError:
            self._raise_metadata_error()

        return TableDescription(
            schema=schema,
            name=table,
            kind="table",
            description=description,
            columns=columns,
            primary_key=primary_key,
            unique_keys=unique_keys,
            foreign_keys=foreign_keys,
        )

    def list_procedures(self, schema: str | None = None) -> tuple[ProcedureInfo, ...]:
        """List visible functions and procedures, with real DDL definitions."""
        target_schema = schema or self._config.database
        if target_schema != self._config.database:
            return ()
        query = """
            SELECT ROUTINE_NAME AS routine_name, ROUTINE_TYPE AS routine_type
            FROM information_schema.ROUTINES
            WHERE ROUTINE_SCHEMA = %s
            ORDER BY ROUTINE_NAME
        """
        try:
            with (
                self._connect_readonly() as connection,
                connection.cursor(pymysql.cursors.DictCursor) as cursor,
            ):
                cursor.execute(query, (target_schema,))
                routines = cursor.fetchall()
                results = [
                    self._describe_procedure(
                        connection,
                        target_schema,
                        cast(str, row["routine_name"]),
                        cast(str, row["routine_type"]),
                    )
                    for row in routines
                ]
        except pymysql.MySQLError:
            self._raise_metadata_error()
        return tuple(results)

    def list_triggers(
        self,
        schema: str | None = None,
        table: str | None = None,
    ) -> tuple[TriggerInfo, ...]:
        """List visible triggers, joined to their table and function."""
        target_schema = schema or self._config.database
        if target_schema != self._config.database:
            return ()
        query = """
            SELECT
                TRIGGER_NAME AS trigger_name,
                EVENT_OBJECT_TABLE AS table_name,
                ACTION_TIMING AS timing,
                EVENT_MANIPULATION AS event
            FROM information_schema.TRIGGERS
            WHERE TRIGGER_SCHEMA = %s
              AND (%s IS NULL OR EVENT_OBJECT_TABLE = %s)
            ORDER BY EVENT_OBJECT_TABLE, TRIGGER_NAME
        """
        try:
            with (
                self._connect_readonly() as connection,
                connection.cursor(pymysql.cursors.DictCursor) as cursor,
            ):
                cursor.execute(query, (target_schema, table, table))
                rows = cursor.fetchall()
                results = [self._describe_trigger(connection, target_schema, row) for row in rows]
        except pymysql.MySQLError:
            self._raise_metadata_error()
        return tuple(results)

    def execute_read_query(
        self,
        sql: str,
        parameters: dict[str, QueryParameter] | None,
        max_rows: int,
        timeout_seconds: int,
        max_serialized_bytes: int,
    ) -> AdapterQueryResult:
        """Execute prevalidated SQL and serialize a bounded result."""
        started_at = perf_counter()
        connection = self._connect_for_query(timeout_seconds)
        translated_sql = self._translate_placeholders(sql)
        try:
            with connection.cursor(pymysql.cursors.SSCursor) as cursor:
                cursor.execute(translated_sql, parameters or {})
                columns = tuple(column[0] for column in (cursor.description or ()))
                fetched = (cursor.fetchone() for _ in range(max(max_rows, 1)))
                raw_rows = [row for row in fetched if row is not None]
            rows, serialized_bytes, bytes_truncated = self._serialize_rows(
                raw_rows,
                max_serialized_bytes,
            )
            connection.rollback()
        except pymysql.err.OperationalError as error:
            self._rollback_and_close(connection)
            if error.args and error.args[0] in _STATEMENT_TIMEOUT_ERROR_CODES:
                raise DatabaseOperationError(
                    code="QUERY_TIMEOUT",
                    message="La consulta excedió el timeout permitido.",
                ) from None
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="MariaDB no pudo ejecutar la consulta de lectura.",
            ) from None
        except pymysql.MySQLError:
            self._rollback_and_close(connection)
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="MariaDB no pudo ejecutar la consulta de lectura.",
            ) from None
        connection.close()
        return AdapterQueryResult(
            columns=columns,
            rows=rows,
            duration_ms=self._elapsed_ms(started_at),
            truncated=bytes_truncated or len(raw_rows) >= max_rows,
            serialized_bytes=serialized_bytes,
        )

    def explain_read_query(
        self,
        sql: str,
        parameters: dict[str, QueryParameter] | None,
        timeout_seconds: int,
    ) -> AdapterQueryPlan:
        """Return a MariaDB JSON EXPLAIN plan without executing the query."""
        started_at = perf_counter()
        connection = self._connect_for_query(timeout_seconds)
        translated_sql = self._translate_placeholders(sql)
        explain_sql = "EXPLAIN FORMAT=JSON " + translated_sql
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(explain_sql, parameters or {})
                row = cursor.fetchone()
            if row is None:
                self._rollback_and_close(connection)
                raise DatabaseOperationError(
                    code="QUERY_PLAN_EMPTY",
                    message="MariaDB no devolvió un plan de ejecución.",
                )
            plan = json.loads(next(iter(row.values())))
            connection.rollback()
        except pymysql.err.OperationalError as error:
            self._rollback_and_close(connection)
            if error.args and error.args[0] in _STATEMENT_TIMEOUT_ERROR_CODES:
                raise DatabaseOperationError(
                    code="QUERY_TIMEOUT",
                    message="La planificación excedió el timeout permitido.",
                ) from None
            raise DatabaseOperationError(
                code="DATABASE_EXPLAIN_ERROR",
                message="MariaDB no pudo generar el plan de lectura.",
            ) from None
        except pymysql.MySQLError:
            self._rollback_and_close(connection)
            raise DatabaseOperationError(
                code="DATABASE_EXPLAIN_ERROR",
                message="MariaDB no pudo generar el plan de lectura.",
            ) from None
        connection.close()
        return AdapterQueryPlan(plan=plan, duration_ms=self._elapsed_ms(started_at))

    @staticmethod
    def _translate_placeholders(sql: str) -> str:
        """Translate SQLGlot-normalized ':name' placeholders to PyMySQL pyformat."""
        return _NAMED_PLACEHOLDER_PATTERN.sub(r"%(\1)s", sql)

    def _connect_for_query(self, timeout_seconds: int) -> "pymysql.connections.Connection[Any]":
        try:
            connection = self._connect_readonly(timeout_seconds)
        except pymysql.MySQLError:
            raise DatabaseOperationError(
                code="DATABASE_CONNECTION_ERROR",
                message="No fue posible abrir la sesión MariaDB de solo lectura.",
            ) from None
        effective_timeout = min(timeout_seconds, self._config.query_timeout_seconds)
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute("SET SESSION max_statement_time = %s", (effective_timeout,))
        return connection

    def _connect_readonly(
        self,
        timeout_seconds: int | None = None,
    ) -> "pymysql.connections.Connection[Any]":
        effective_timeout = min(
            timeout_seconds or self._config.query_timeout_seconds,
            self._config.query_timeout_seconds,
        )
        # The socket-level timeout gets a small buffer over the server-side
        # max_statement_time so the server reports a clean, specific timeout error
        # (1969) instead of racing it with a generic client-side socket timeout.
        socket_timeout = effective_timeout + 5
        driver_options = cast("dict[str, Any]", dict(self._config.options))
        connection = pymysql.connect(
            host=self._config.host,
            port=self._config.port,
            database=self._config.database,
            user=self._config.username,
            password=self._password.get_secret_value(),
            connect_timeout=self._config.connect_timeout_seconds,
            read_timeout=socket_timeout,
            write_timeout=socket_timeout,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            **driver_options,
        )
        return connection

    @classmethod
    def _serialize_rows(
        cls,
        raw_rows: list[tuple[object, ...]],
        max_serialized_bytes: int,
    ) -> tuple[tuple[tuple[SerializedValue, ...], ...], int, bool]:
        rows: list[tuple[SerializedValue, ...]] = []
        serialized_bytes = 0
        truncated = False
        for raw_row in raw_rows:
            row = tuple(cls._serialize_value(value) for value in raw_row)
            row_bytes = len(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            if serialized_bytes + row_bytes > max_serialized_bytes:
                truncated = True
                break
            rows.append(row)
            serialized_bytes += row_bytes
        return tuple(rows), serialized_bytes, truncated

    @staticmethod
    def _serialize_value(value: object) -> SerializedValue:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date, time, timedelta)):
            return str(value)
        if isinstance(value, (bytes, bytearray, memoryview)):
            encoded = base64.b64encode(bytes(value)).decode("ascii")
            return f"base64:{encoded}"
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _rollback_and_close(connection: "pymysql.connections.Connection[Any]") -> None:
        try:
            connection.rollback()
        except pymysql.MySQLError:
            connection.close()
            return
        connection.close()

    @staticmethod
    def _load_columns(
        connection: "pymysql.connections.Connection[Any]",
        schema: str,
        table: str,
    ) -> tuple[ColumnInfo, ...]:
        query = """
            SELECT
                ORDINAL_POSITION AS ordinal_position,
                COLUMN_NAME AS column_name,
                COLUMN_TYPE AS data_type,
                IS_NULLABLE = 'YES' AS nullable,
                COLUMN_DEFAULT AS default_value,
                COLUMN_COMMENT AS description
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, (schema, table))
            rows = cursor.fetchall()
        return tuple(
            ColumnInfo(
                ordinal_position=cast(int, row["ordinal_position"]),
                name=cast(str, row["column_name"]),
                data_type=cast(str, row["data_type"]),
                nullable=bool(row["nullable"]),
                default=cast(str | None, row["default_value"]),
                description=cast(str, row["description"]) or None,
            )
            for row in rows
        )

    @staticmethod
    def _load_table_comment(
        connection: "pymysql.connections.Connection[Any]",
        schema: str,
        table: str,
    ) -> str | None:
        query = """
            SELECT TABLE_COMMENT AS description
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, (schema, table))
            row = cursor.fetchone()
        if row is None:
            raise DatabaseObjectNotFoundError(schema, table)
        description = cast(str, row["description"])
        return description or None

    @staticmethod
    def _load_primary_key(
        connection: "pymysql.connections.Connection[Any]",
        schema: str,
        table: str,
    ) -> tuple[str, ...]:
        query = """
            SELECT COLUMN_NAME AS column_name
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
              AND CONSTRAINT_NAME = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
        """
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, (schema, table))
            rows = cursor.fetchall()
        return tuple(cast(str, row["column_name"]) for row in rows)

    @staticmethod
    def _load_unique_keys(
        connection: "pymysql.connections.Connection[Any]",
        schema: str,
        table: str,
    ) -> tuple[UniqueKeyInfo, ...]:
        query = """
            SELECT INDEX_NAME AS index_name, COLUMN_NAME AS column_name
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
              AND NON_UNIQUE = 0
              AND INDEX_NAME <> 'PRIMARY'
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
        """
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, (schema, table))
            rows = cursor.fetchall()
        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(cast(str, row["index_name"]), []).append(
                cast(str, row["column_name"])
            )
        return tuple(
            UniqueKeyInfo(name=name, columns=tuple(columns)) for name, columns in grouped.items()
        )

    @staticmethod
    def _load_foreign_keys(
        connection: "pymysql.connections.Connection[Any]",
        schema: str,
        table: str,
    ) -> tuple[ForeignKeyInfo, ...]:
        query = """
            SELECT
                CONSTRAINT_NAME AS constraint_name,
                COLUMN_NAME AS column_name,
                REFERENCED_TABLE_SCHEMA AS referenced_schema,
                REFERENCED_TABLE_NAME AS referenced_table,
                REFERENCED_COLUMN_NAME AS referenced_column
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
        """
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, (schema, table))
            rows = cursor.fetchall()
        grouped: dict[str, dict[str, object]] = {}
        for row in rows:
            name = cast(str, row["constraint_name"])
            entry = grouped.setdefault(
                name,
                {
                    "columns": [],
                    "referenced_schema": row["referenced_schema"],
                    "referenced_table": row["referenced_table"],
                    "referenced_columns": [],
                },
            )
            cast("list[str]", entry["columns"]).append(cast(str, row["column_name"]))
            cast("list[str]", entry["referenced_columns"]).append(
                cast(str, row["referenced_column"])
            )
        return tuple(
            ForeignKeyInfo(
                name=name,
                columns=tuple(cast("list[str]", entry["columns"])),
                referenced_schema=cast(str, entry["referenced_schema"]),
                referenced_table=cast(str, entry["referenced_table"]),
                referenced_columns=tuple(cast("list[str]", entry["referenced_columns"])),
            )
            for name, entry in grouped.items()
        )

    @staticmethod
    def _describe_procedure(
        connection: "pymysql.connections.Connection[Any]",
        schema: str,
        name: str,
        routine_type: str,
    ) -> ProcedureInfo:
        kind: Literal["function", "procedure"] = (
            "function" if routine_type == "FUNCTION" else "procedure"
        )
        keyword = "FUNCTION" if kind == "function" else "PROCEDURE"
        params_query = """
            SELECT PARAMETER_NAME AS parameter_name, DTD_IDENTIFIER AS data_type
            FROM information_schema.PARAMETERS
            WHERE SPECIFIC_SCHEMA = %s AND SPECIFIC_NAME = %s AND ROUTINE_TYPE = %s
            ORDER BY ORDINAL_POSITION
        """
        comment_query = """
            SELECT ROUTINE_COMMENT AS comment, DTD_IDENTIFIER AS return_type
            FROM information_schema.ROUTINES
            WHERE ROUTINE_SCHEMA = %s AND ROUTINE_NAME = %s AND ROUTINE_TYPE = %s
        """
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(params_query, (schema, name, routine_type))
            parameter_rows = cursor.fetchall()
            cursor.execute(comment_query, (schema, name, routine_type))
            comment_row = cursor.fetchone()
            cursor.execute(f"SHOW CREATE {keyword} `{schema}`.`{name}`")
            create_row = cursor.fetchone()
        arguments = ", ".join(
            f"{row['parameter_name']} {row['data_type']}"
            for row in parameter_rows
            if row["parameter_name"] is not None
        )
        comment = cast(str | None, comment_row["comment"]) if comment_row else None
        return_type = (
            cast(str | None, comment_row["return_type"])
            if comment_row and kind == "function"
            else None
        )
        definition_key = "Create Function" if kind == "function" else "Create Procedure"
        definition = cast(str, (create_row or {}).get(definition_key, ""))
        return ProcedureInfo(
            schema=schema,
            name=name,
            kind=kind,
            language="SQL",
            arguments=arguments,
            return_type=return_type,
            comment=comment or None,
            definition=definition,
        )

    @staticmethod
    def _describe_trigger(
        connection: "pymysql.connections.Connection[Any]",
        schema: str,
        row: dict[str, object],
    ) -> TriggerInfo:
        name = cast(str, row["trigger_name"])
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(f"SHOW CREATE TRIGGER `{schema}`.`{name}`")
            create_row = cursor.fetchone()
        definition = cast(str, (create_row or {}).get("SQL Original Statement", ""))
        return TriggerInfo(
            schema=schema,
            name=name,
            table=cast(str, row["table_name"]),
            timing=cast(Literal["BEFORE", "AFTER"], row["timing"]),
            events=(cast(Literal["INSERT", "UPDATE", "DELETE"], row["event"]),),
            function_schema=schema,
            function_name=name,
            comment=None,
            definition=definition,
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((perf_counter() - started_at) * 1000, 3)

    @staticmethod
    def _raise_metadata_error() -> NoReturn:
        raise DatabaseOperationError(
            code="DATABASE_METADATA_ERROR",
            message="No fue posible recuperar metadata de MariaDB.",
        ) from None
