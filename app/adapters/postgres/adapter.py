"""Read-only PostgreSQL connectivity and metadata adapter."""

from time import perf_counter
from typing import Literal, NoReturn, cast

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row
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
    QueryLanguage,
    SchemaInfo,
    TableDescription,
    TableInfo,
)

_ALLOWED_POSTGRES_OPTIONS = {
    "application_name",
    "keepalives",
    "keepalives_count",
    "keepalives_idle",
    "keepalives_interval",
    "sslcert",
    "sslkey",
    "sslmode",
    "sslrootcert",
    "target_session_attrs",
}


class PostgresAdapter(SqlDatabaseAdapter):
    """PostgreSQL adapter limited to connectivity and catalog metadata."""

    CAPABILITIES = ConnectionCapabilities(
        query_language=QueryLanguage.SQL,
        test_connection=True,
        list_schemas=True,
        list_tables=True,
        describe_table=True,
        primary_keys=True,
        foreign_keys=True,
    )

    def __init__(self, config: ConnectionConfig, password: SecretStr) -> None:
        if config.type.value != "postgres":
            raise ConfigurationError(
                code="POSTGRES_CONFIG_TYPE_ERROR",
                message="PostgresAdapter requiere una conexión de tipo postgres.",
            )
        invalid_options = set(config.options).difference(_ALLOWED_POSTGRES_OPTIONS)
        if invalid_options:
            names = ", ".join(sorted(invalid_options))
            raise ConfigurationError(
                code="POSTGRES_OPTIONS_ERROR",
                message=f"Opciones PostgreSQL no soportadas: {names}",
            )
        self._config = config
        self._password = password

    @property
    def capabilities(self) -> ConnectionCapabilities:
        """Return PostgreSQL metadata capabilities."""
        return self.CAPABILITIES

    def test_connection(self) -> ConnectionTestResult:
        """Open a read-only session and execute a constant liveness query."""
        started_at = perf_counter()
        try:
            with self._connect_readonly() as connection:
                row = connection.execute("SELECT 1 AS value").fetchone()
            success = row is not None and row["value"] == 1
        except psycopg.Error as error:
            return ConnectionTestResult(
                connection_id=self._config.id,
                success=False,
                latency_ms=self._elapsed_ms(started_at),
                error_code=error.sqlstate or "DATABASE_CONNECTION_ERROR",
                message="No fue posible conectar con PostgreSQL.",
            )

        return ConnectionTestResult(
            connection_id=self._config.id,
            success=success,
            latency_ms=self._elapsed_ms(started_at),
            error_code=None if success else "DATABASE_LIVENESS_ERROR",
            message=(
                "Conexión PostgreSQL disponible." if success else "Respuesta PostgreSQL inválida."
            ),
        )

    def list_schemas(self) -> tuple[SchemaInfo, ...]:
        """List visible application schemas, excluding PostgreSQL internals."""
        query = """
            SELECT nspname AS name
            FROM pg_catalog.pg_namespace
            WHERE nspname NOT LIKE 'pg\\_%' ESCAPE '\\'
              AND nspname <> 'information_schema'
              AND has_schema_privilege(nspname, 'USAGE')
            ORDER BY nspname
        """
        try:
            with self._connect_readonly() as connection:
                rows = connection.execute(query).fetchall()
        except psycopg.Error:
            self._raise_metadata_error()
        return tuple(SchemaInfo(name=cast(str, row["name"])) for row in rows)

    def list_tables(self, schema: str | None = None) -> tuple[TableInfo, ...]:
        """List ordinary and partitioned tables visible to the configured role."""
        query = """
            SELECT
                namespace.nspname AS schema_name,
                relation.relname AS table_name,
                CASE relation.relkind
                    WHEN 'p' THEN 'partitioned_table'
                    ELSE 'table'
                END AS table_kind
            FROM pg_catalog.pg_class AS relation
            INNER JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
            WHERE relation.relkind IN ('r', 'p')
              AND namespace.nspname NOT LIKE 'pg\\_%%' ESCAPE '\\'
              AND namespace.nspname <> 'information_schema'
              AND (%s::text IS NULL OR namespace.nspname = %s)
              AND has_table_privilege(relation.oid, 'SELECT')
            ORDER BY namespace.nspname, relation.relname
        """
        try:
            with self._connect_readonly() as connection:
                rows = connection.execute(query, (schema, schema)).fetchall()
        except psycopg.Error:
            self._raise_metadata_error()
        return tuple(
            TableInfo(
                schema=cast(str, row["schema_name"]),
                name=cast(str, row["table_name"]),
                kind=cast(Literal["table", "partitioned_table"], row["table_kind"]),
            )
            for row in rows
        )

    def describe_table(self, schema: str, table: str) -> TableDescription:
        """Describe visible columns, primary key and foreign keys."""
        try:
            with self._connect_readonly() as connection:
                columns = self._load_columns(connection, schema, table)
                if not columns:
                    raise DatabaseObjectNotFoundError(schema, table)
                primary_key = self._load_primary_key(connection, schema, table)
                foreign_keys = self._load_foreign_keys(connection, schema, table)
        except psycopg.Error:
            self._raise_metadata_error()

        return TableDescription(
            schema=schema,
            name=table,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
        )

    def _connect_readonly(self) -> psycopg.Connection[DictRow]:
        driver_options = {
            key: "1" if value is True else "0" if value is False else str(value)
            for key, value in self._config.options.items()
        }
        conninfo = make_conninfo(
            host=self._config.host,
            port=self._config.port,
            dbname=self._config.database,
            user=self._config.username,
            password=self._password.get_secret_value(),
            connect_timeout=self._config.connect_timeout_seconds,
            options=f"-c statement_timeout={self._config.query_timeout_seconds * 1000}",
            **driver_options,
        )
        connection = psycopg.connect(conninfo, row_factory=dict_row)
        connection.read_only = True
        return connection

    @staticmethod
    def _load_columns(
        connection: psycopg.Connection[DictRow],
        schema: str,
        table: str,
    ) -> tuple[ColumnInfo, ...]:
        query = """
            SELECT
                attribute.attnum AS ordinal_position,
                attribute.attname AS column_name,
                pg_catalog.format_type(attribute.atttypid, attribute.atttypmod) AS data_type,
                NOT attribute.attnotnull AS nullable,
                pg_catalog.pg_get_expr(default_value.adbin, default_value.adrelid) AS default_value
            FROM pg_catalog.pg_attribute AS attribute
            INNER JOIN pg_catalog.pg_class AS relation
                ON relation.oid = attribute.attrelid
            INNER JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
            LEFT JOIN pg_catalog.pg_attrdef AS default_value
                ON default_value.adrelid = relation.oid
               AND default_value.adnum = attribute.attnum
            WHERE namespace.nspname = %s
              AND relation.relname = %s
              AND relation.relkind IN ('r', 'p')
              AND attribute.attnum > 0
              AND NOT attribute.attisdropped
              AND has_table_privilege(relation.oid, 'SELECT')
            ORDER BY attribute.attnum
        """
        rows = connection.execute(query, (schema, table)).fetchall()
        return tuple(
            ColumnInfo(
                ordinal_position=cast(int, row["ordinal_position"]),
                name=cast(str, row["column_name"]),
                data_type=cast(str, row["data_type"]),
                nullable=cast(bool, row["nullable"]),
                default=cast(str | None, row["default_value"]),
            )
            for row in rows
        )

    @staticmethod
    def _load_primary_key(
        connection: psycopg.Connection[DictRow],
        schema: str,
        table: str,
    ) -> tuple[str, ...]:
        query = """
            SELECT attribute.attname AS column_name
            FROM pg_catalog.pg_index AS index_definition
            INNER JOIN pg_catalog.pg_class AS relation
                ON relation.oid = index_definition.indrelid
            INNER JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
            INNER JOIN LATERAL unnest(index_definition.indkey)
                WITH ORDINALITY AS key_column(attribute_number, position) ON TRUE
            INNER JOIN pg_catalog.pg_attribute AS attribute
                ON attribute.attrelid = relation.oid
               AND attribute.attnum = key_column.attribute_number
            WHERE namespace.nspname = %s
              AND relation.relname = %s
              AND index_definition.indisprimary
            ORDER BY key_column.position
        """
        rows = connection.execute(query, (schema, table)).fetchall()
        return tuple(cast(str, row["column_name"]) for row in rows)

    @staticmethod
    def _load_foreign_keys(
        connection: psycopg.Connection[DictRow],
        schema: str,
        table: str,
    ) -> tuple[ForeignKeyInfo, ...]:
        query = """
            SELECT
                constraint_definition.conname AS constraint_name,
                array_agg(source_attribute.attname ORDER BY key_column.position) AS columns,
                target_namespace.nspname AS referenced_schema,
                target_relation.relname AS referenced_table,
                array_agg(target_attribute.attname ORDER BY key_column.position)
                    AS referenced_columns
            FROM pg_catalog.pg_constraint AS constraint_definition
            INNER JOIN pg_catalog.pg_class AS source_relation
                ON source_relation.oid = constraint_definition.conrelid
            INNER JOIN pg_catalog.pg_namespace AS source_namespace
                ON source_namespace.oid = source_relation.relnamespace
            INNER JOIN pg_catalog.pg_class AS target_relation
                ON target_relation.oid = constraint_definition.confrelid
            INNER JOIN pg_catalog.pg_namespace AS target_namespace
                ON target_namespace.oid = target_relation.relnamespace
            INNER JOIN LATERAL unnest(
                constraint_definition.conkey,
                constraint_definition.confkey
            ) WITH ORDINALITY AS key_column(
                source_attribute_number,
                target_attribute_number,
                position
            ) ON TRUE
            INNER JOIN pg_catalog.pg_attribute AS source_attribute
                ON source_attribute.attrelid = source_relation.oid
               AND source_attribute.attnum = key_column.source_attribute_number
            INNER JOIN pg_catalog.pg_attribute AS target_attribute
                ON target_attribute.attrelid = target_relation.oid
               AND target_attribute.attnum = key_column.target_attribute_number
            WHERE constraint_definition.contype = 'f'
              AND source_namespace.nspname = %s
              AND source_relation.relname = %s
              AND has_table_privilege(source_relation.oid, 'SELECT')
            GROUP BY
                constraint_definition.conname,
                target_namespace.nspname,
                target_relation.relname
            ORDER BY constraint_definition.conname
        """
        rows = connection.execute(query, (schema, table)).fetchall()
        return tuple(
            ForeignKeyInfo(
                name=cast(str, row["constraint_name"]),
                columns=tuple(cast(list[str], row["columns"])),
                referenced_schema=cast(str, row["referenced_schema"]),
                referenced_table=cast(str, row["referenced_table"]),
                referenced_columns=tuple(cast(list[str], row["referenced_columns"])),
            )
            for row in rows
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((perf_counter() - started_at) * 1000, 3)

    @staticmethod
    def _raise_metadata_error() -> NoReturn:
        raise DatabaseOperationError(
            code="DATABASE_METADATA_ERROR",
            message="No fue posible recuperar metadata de PostgreSQL.",
        ) from None
