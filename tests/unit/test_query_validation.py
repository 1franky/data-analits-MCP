"""Security tests for parser-backed SQL classification and limit rewriting."""

import pytest

from app.models.query import SqlStatementType, SqlValidationResult
from app.services import QueryValidationService


@pytest.fixture
def validator() -> QueryValidationService:
    return QueryValidationService()


def issue_codes(result: SqlValidationResult) -> set[str]:
    return {issue.code for issue in result.blocked_reasons}


def test_select_and_read_cte_are_executable(validator: QueryValidationService) -> None:
    result = validator.validate(
        """
        WITH totales AS (
            SELECT cliente_id, SUM(cantidad) AS total
            FROM ventas
            GROUP BY cliente_id
        )
        SELECT * FROM totales
        """,
        "postgres",
    )

    assert result.valid is True
    assert result.read_only is True
    assert result.executable is True
    assert result.statement_type is SqlStatementType.SELECT
    assert tuple(reference.name for reference in result.referenced_objects) == ("ventas",)


@pytest.mark.parametrize(
    ("sql", "statement_type", "reason"),
    [
        ("INSERT INTO ventas (id) VALUES (1)", SqlStatementType.INSERT, "DML_NOT_ALLOWED"),
        ("UPDATE productos SET stock = 0", SqlStatementType.UPDATE, "DML_NOT_ALLOWED"),
        ("DELETE FROM ventas", SqlStatementType.DELETE, "DML_NOT_ALLOWED"),
        ("DROP TABLE ventas", SqlStatementType.DROP, "DDL_NOT_ALLOWED"),
        ("ALTER TABLE ventas ADD COLUMN x int", SqlStatementType.ALTER, "DDL_NOT_ALLOWED"),
        ("TRUNCATE TABLE ventas", SqlStatementType.TRUNCATE, "DDL_NOT_ALLOWED"),
        ("COPY ventas TO STDOUT", SqlStatementType.COPY, "COPY_NOT_ALLOWED"),
        ("CALL procesar_ventas()", SqlStatementType.COMMAND, "ADMIN_COMMAND_NOT_ALLOWED"),
    ],
)
def test_write_and_admin_statements_are_classified_and_blocked(
    validator: QueryValidationService,
    sql: str,
    statement_type: SqlStatementType,
    reason: str,
) -> None:
    result = validator.validate(sql, "postgres")

    assert result.valid is False
    assert result.executable is False
    assert result.statement_type is statement_type
    assert reason in issue_codes(result)
    assert result.normalized_sql is not None


def test_multiple_statements_report_every_security_reason(
    validator: QueryValidationService,
) -> None:
    result = validator.validate(
        "SELECT * FROM ventas; /* intento oculto */ DROP TABLE ventas",
        "postgres",
    )

    assert result.statement_type is SqlStatementType.MULTIPLE
    assert {"MULTIPLE_STATEMENTS", "DDL_NOT_ALLOWED"}.issubset(issue_codes(result))


def test_data_modifying_cte_is_detected(validator: QueryValidationService) -> None:
    result = validator.validate(
        "WITH borrado AS (DELETE FROM ventas RETURNING *) SELECT * FROM borrado",
        "postgres",
    )

    assert result.statement_type is SqlStatementType.SELECT
    assert {"DML_NOT_ALLOWED", "WRITE_IN_CTE"}.issubset(issue_codes(result))
    assert result.executable is False


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("SELECT * INTO copia FROM ventas", "SELECT_INTO_NOT_ALLOWED"),
        ("SELECT * FROM ventas FOR UPDATE", "LOCKING_SELECT_NOT_ALLOWED"),
        ("SELECT pg_sleep(10)", "DANGEROUS_FUNCTION_NOT_ALLOWED"),
        ("SELECT nextval('ventas_id_seq')", "DANGEROUS_FUNCTION_NOT_ALLOWED"),
        (
            "SELECT pg_catalog.set_config('search_path', 'public', false)",
            "DANGEROUS_FUNCTION_NOT_ALLOWED",
        ),
        ("SELECT dblink('remote', 'DELETE FROM ventas')", "DANGEROUS_FUNCTION_NOT_ALLOWED"),
        ("SELECT dblink_connect('remote')", "DANGEROUS_FUNCTION_NOT_ALLOWED"),
        ("SELECT lo_unlink(42)", "DANGEROUS_FUNCTION_NOT_ALLOWED"),
        ("SELECT pg_notify('channel', 'payload')", "DANGEROUS_FUNCTION_NOT_ALLOWED"),
        ("SELECT pg_advisory_unlock_all()", "DANGEROUS_FUNCTION_NOT_ALLOWED"),
        ("SELECT pg_create_restore_point('unsafe')", "DANGEROUS_FUNCTION_NOT_ALLOWED"),
        ("EXPLAIN ANALYZE SELECT * FROM ventas", "ADMIN_COMMAND_NOT_ALLOWED"),
    ],
)
def test_select_bypasses_are_blocked(
    validator: QueryValidationService,
    sql: str,
    reason: str,
) -> None:
    result = validator.validate(sql, "postgres")

    assert reason in issue_codes(result)
    assert result.executable is False


def test_invalid_sql_and_unsupported_dialect_return_structured_reasons(
    validator: QueryValidationService,
) -> None:
    invalid = validator.validate("SELECT FROM", "postgres")
    unsupported = validator.validate("SELECT 1", "oracle")

    assert issue_codes(invalid) == {"SQL_PARSE_ERROR"}
    assert issue_codes(unsupported) == {"SQL_DIALECT_UNSUPPORTED"}


def test_named_parameters_are_preserved_and_positional_parameters_are_blocked(
    validator: QueryValidationService,
) -> None:
    named = validator.validate("SELECT * FROM ventas WHERE id = %(venta_id)s", "postgres")
    positional = validator.validate("SELECT * FROM ventas WHERE id = %s", "postgres")

    assert named.parameter_names == ("venta_id",)
    assert named.normalized_sql == "SELECT * FROM ventas WHERE id = %(venta_id)s"
    assert "NAMED_PARAMETERS_REQUIRED" in issue_codes(positional)


def test_outer_limit_is_added_or_reduced_without_increasing_smaller_limit(
    validator: QueryValidationService,
) -> None:
    added = validator.apply_row_limit("SELECT * FROM ventas", "postgres", 100)
    reduced = validator.apply_row_limit("SELECT * FROM ventas LIMIT 500", "postgres", 100)
    preserved = validator.apply_row_limit("SELECT * FROM ventas LIMIT 10", "postgres", 100)

    assert added.sql.endswith("LIMIT 100")
    assert reduced.sql.endswith("LIMIT 100")
    assert reduced.row_limit == 100
    assert preserved.sql.endswith("LIMIT 10")
    assert preserved.row_limit == 10
    assert preserved.limit_reduced is False
