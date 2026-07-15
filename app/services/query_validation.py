"""Parser-backed SQL validation and safe row-limit rewriting."""

from collections.abc import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.models.query import (
    PreparedReadQuery,
    ReferencedObject,
    SqlStatementType,
    SqlValidationResult,
    ValidationIssue,
)
from app.security import PostgresSqlPolicy

_DML_TYPES = (exp.Insert, exp.Update, exp.Delete, exp.Merge)
_DDL_TYPES = (exp.Create, exp.Alter, exp.Drop, exp.TruncateTable)
_PRIVILEGE_TYPES = (exp.Grant, exp.Revoke)
_READ_ROOT_TYPES = (exp.Select, exp.SetOperation)


class QueryValidationService:
    """Validate PostgreSQL using its parsed AST, never regular expressions alone."""

    def validate(self, sql: str, dialect: str) -> SqlValidationResult:
        """Parse SQL and return every applicable structured block reason."""
        normalized_input = sql.strip()
        if not normalized_input:
            return self._invalid_without_ast(
                dialect,
                "SQL_EMPTY",
                "La consulta SQL no puede estar vacía.",
            )
        if dialect != "postgres":
            return self._invalid_without_ast(
                dialect,
                "SQL_DIALECT_UNSUPPORTED",
                f"El dialecto '{dialect}' todavía no tiene una política SQL ejecutable.",
            )

        try:
            parsed_expressions = sqlglot.parse(normalized_input, read=dialect)
        except SqlglotError:
            return self._invalid_without_ast(
                dialect,
                "SQL_PARSE_ERROR",
                "La consulta no es sintácticamente válida para PostgreSQL.",
            )
        expressions = tuple(
            expression
            for expression in parsed_expressions
            if isinstance(expression, exp.Expression)
        )
        if not expressions:
            return self._invalid_without_ast(
                dialect,
                "SQL_PARSE_ERROR",
                "La consulta no contiene una sentencia SQL válida.",
            )

        issues: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        multiple = len(expressions) != 1
        if multiple:
            self._append_issue(
                issues,
                "MULTIPLE_STATEMENTS",
                "Solo se permite una sentencia SQL por solicitud.",
            )

        root_types = tuple(self._classify(expression) for expression in expressions)
        statement_type = root_types[0] if not multiple else SqlStatementType.MULTIPLE
        for expression, root_type in zip(expressions, root_types, strict=True):
            self._inspect_expression(expression, root_type, issues, warnings)

        normalized_sql = "; ".join(
            expression.sql(dialect=dialect, pretty=False) for expression in expressions
        )
        references = self._referenced_objects(expressions)
        parameter_names = self._parameter_names(expressions, issues)
        read_only = not multiple and isinstance(expressions[0], _READ_ROOT_TYPES) and not issues
        valid = not issues
        return SqlValidationResult(
            valid=valid,
            read_only=read_only,
            executable=valid and read_only and statement_type is SqlStatementType.SELECT,
            statement_type=statement_type,
            dialect=dialect,
            multiple_statements=multiple,
            normalized_sql=normalized_sql,
            blocked_reasons=tuple(issues),
            warnings=tuple(warnings),
            referenced_objects=references,
            parameter_names=parameter_names,
        )

    def apply_row_limit(
        self,
        normalized_sql: str,
        dialect: str,
        maximum_rows: int,
    ) -> PreparedReadQuery:
        """Enforce an outer LIMIT without trusting textual SQL manipulation."""
        expression = sqlglot.parse_one(normalized_sql, read=dialect)
        if not isinstance(expression, _READ_ROOT_TYPES):
            raise ValueError("apply_row_limit requires a parsed read query")

        existing_limit = expression.args.get("limit")
        existing_value = self._literal_limit(existing_limit)
        row_limit = minimum = maximum_rows
        limit_reduced = existing_limit is None
        if existing_limit is not None:
            if existing_value is None:
                limit_reduced = True
            else:
                row_limit = min(existing_value, maximum_rows)
                limit_reduced = existing_value > maximum_rows
                minimum = row_limit
        rewritten = expression.limit(minimum, copy=True)
        return PreparedReadQuery(
            sql=rewritten.sql(dialect=dialect, pretty=False),
            row_limit=row_limit,
            limit_reduced=limit_reduced,
        )

    def block_for_parameter_mismatch(
        self,
        validation: SqlValidationResult,
    ) -> SqlValidationResult:
        """Convert a parsed result into a blocked parameter-contract result."""
        return self.add_block(
            validation,
            "QUERY_PARAMETERS_MISMATCH",
            "Los parámetros proporcionados no coinciden con los placeholders SQL.",
        )

    @staticmethod
    def add_block(
        validation: SqlValidationResult,
        code: str,
        message: str,
    ) -> SqlValidationResult:
        """Return a copy with an additional structured execution block."""
        issue = ValidationIssue(code=code, message=message)
        return validation.model_copy(
            update={
                "valid": False,
                "read_only": False,
                "executable": False,
                "blocked_reasons": (*validation.blocked_reasons, issue),
            }
        )

    def _inspect_expression(
        self,
        expression: exp.Expression,
        root_type: SqlStatementType,
        issues: list[ValidationIssue],
        warnings: list[ValidationIssue],
    ) -> None:
        if not isinstance(expression, _READ_ROOT_TYPES):
            self._append_issue(
                issues,
                "READ_ONLY_STATEMENT_REQUIRED",
                "La ejecución está limitada a sentencias SELECT.",
            )

        nodes = tuple(expression.walk())
        dml_nodes = tuple(node for node in nodes if isinstance(node, _DML_TYPES))
        if dml_nodes:
            self._append_issue(
                issues,
                "DML_NOT_ALLOWED",
                "Las sentencias DML se pueden revisar, pero nunca ejecutar.",
            )
            self._append_issue(
                warnings,
                "WRITE_IMPACT_WARNING",
                "La sentencia puede modificar datos y fue marcada como no ejecutable.",
            )
        if any(node.find_ancestor(exp.CTE) is not None for node in dml_nodes):
            self._append_issue(
                issues,
                "WRITE_IN_CTE",
                "Se detectó una operación de escritura dentro de un CTE.",
            )
        if any(isinstance(node, _DDL_TYPES) for node in nodes):
            self._append_issue(
                issues,
                "DDL_NOT_ALLOWED",
                "Las sentencias DDL se pueden revisar, pero nunca ejecutar.",
            )
            self._append_issue(
                warnings,
                "DDL_IMPACT_WARNING",
                "La sentencia puede modificar la estructura y fue marcada como no ejecutable.",
            )
        if any(isinstance(node, _PRIVILEGE_TYPES) for node in nodes):
            self._append_issue(
                issues,
                "PRIVILEGE_COMMAND_NOT_ALLOWED",
                "No se permiten comandos de privilegios.",
            )
        if any(isinstance(node, exp.Copy) for node in nodes):
            self._append_issue(
                issues,
                "COPY_NOT_ALLOWED",
                "COPY no está permitido en la superficie de consultas.",
            )
        if any(isinstance(node, exp.Command) for node in nodes):
            self._append_issue(
                issues,
                "ADMIN_COMMAND_NOT_ALLOWED",
                "El comando no pertenece a la allowlist de lectura.",
            )
        if any(isinstance(node, exp.Into) for node in nodes):
            self._append_issue(
                issues,
                "SELECT_INTO_NOT_ALLOWED",
                "SELECT INTO crea objetos y no está permitido.",
            )
        if any(isinstance(node, exp.Lock) for node in nodes):
            self._append_issue(
                issues,
                "LOCKING_SELECT_NOT_ALLOWED",
                "No se permiten cláusulas de bloqueo en SELECT.",
            )
        for node in nodes:
            if isinstance(node, exp.Func) and PostgresSqlPolicy.function_is_blocked(
                self._function_name(node)
            ):
                self._append_issue(
                    issues,
                    "DANGEROUS_FUNCTION_NOT_ALLOWED",
                    f"La función '{self._function_name(node)}' no está permitida.",
                )
        if root_type is SqlStatementType.UNKNOWN:
            self._append_issue(
                issues,
                "STATEMENT_TYPE_NOT_ALLOWED",
                "No fue posible clasificar la sentencia dentro de la allowlist.",
            )

    @staticmethod
    def _classify(expression: exp.Expression) -> SqlStatementType:
        if isinstance(expression, _READ_ROOT_TYPES):
            return SqlStatementType.SELECT
        mapping: tuple[tuple[type[exp.Expression], SqlStatementType], ...] = (
            (exp.Insert, SqlStatementType.INSERT),
            (exp.Update, SqlStatementType.UPDATE),
            (exp.Delete, SqlStatementType.DELETE),
            (exp.Merge, SqlStatementType.MERGE),
            (exp.Create, SqlStatementType.CREATE),
            (exp.Alter, SqlStatementType.ALTER),
            (exp.Drop, SqlStatementType.DROP),
            (exp.TruncateTable, SqlStatementType.TRUNCATE),
            (exp.Copy, SqlStatementType.COPY),
            (exp.Grant, SqlStatementType.GRANT),
            (exp.Revoke, SqlStatementType.REVOKE),
            (exp.Command, SqlStatementType.COMMAND),
        )
        return next(
            (
                statement_type
                for node_type, statement_type in mapping
                if isinstance(expression, node_type)
            ),
            SqlStatementType.UNKNOWN,
        )

    @staticmethod
    def _function_name(function: exp.Func) -> str:
        if isinstance(function, exp.Anonymous):
            return function.name.casefold()
        return function.sql_name().casefold()

    @classmethod
    def _referenced_objects(
        cls,
        expressions: Iterable[exp.Expression],
    ) -> tuple[ReferencedObject, ...]:
        expression_tuple = tuple(expressions)
        cte_names = {
            cte.alias_or_name.casefold()
            for expression in expression_tuple
            for cte in expression.find_all(exp.CTE)
        }
        references = {
            (table.db or None, table.name)
            for expression in expression_tuple
            for table in expression.find_all(exp.Table)
            if table.db or table.name.casefold() not in cte_names
        }
        return tuple(
            ReferencedObject(schema_name=schema, name=name)
            for schema, name in sorted(references, key=lambda item: (item[0] or "", item[1]))
        )

    @classmethod
    def _parameter_names(
        cls,
        expressions: Iterable[exp.Expression],
        issues: list[ValidationIssue],
    ) -> tuple[str, ...]:
        names: set[str] = set()
        for expression in expressions:
            for placeholder in expression.find_all(exp.Placeholder):
                name = placeholder.name
                if not name or name == "?":
                    cls._append_issue(
                        issues,
                        "NAMED_PARAMETERS_REQUIRED",
                        "Solo se permiten parámetros nombrados.",
                    )
                    continue
                names.add(name)
        return tuple(sorted(names))

    @staticmethod
    def _literal_limit(limit: object) -> int | None:
        if not isinstance(limit, exp.Limit):
            return None
        value = limit.expression
        if not isinstance(value, exp.Literal) or value.is_string:
            return None
        try:
            return max(0, int(value.this))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _append_issue(
        issues: list[ValidationIssue],
        code: str,
        message: str,
    ) -> None:
        if all(issue.code != code for issue in issues):
            issues.append(ValidationIssue(code=code, message=message))

    @staticmethod
    def _invalid_without_ast(dialect: str, code: str, message: str) -> SqlValidationResult:
        return SqlValidationResult(
            valid=False,
            read_only=False,
            executable=False,
            statement_type=SqlStatementType.UNKNOWN,
            dialect=dialect,
            multiple_statements=False,
            normalized_sql=None,
            blocked_reasons=(ValidationIssue(code=code, message=message),),
            warnings=(),
            referenced_objects=(),
            parameter_names=(),
        )
