"""Allowlist-based, structural validation for MongoDB find/aggregate requests.

Unlike SQL validation, this never parses text: filters and pipelines already
arrive as structured dict/list payloads. The policy is fail-closed — only
explicitly recognized stage and operator names are permitted; anything else is
blocked, including names not in `MongoOperatorPolicy._EXPLICITLY_BLOCKED`.
"""

import re

from pydantic import JsonValue

from app.models.document_query import DocumentOperationType, DocumentQueryValidationResult
from app.models.query import ValidationIssue
from app.security import MongoOperatorPolicy

_COLLECTION_NAME_PATTERN = re.compile(r"^[^$.\s][^$]*$")
_MAX_NESTING_DEPTH = 32


class DocumentQueryValidationService:
    """Validate MongoDB find filters and aggregation pipelines before execution."""

    def validate_find(
        self,
        collection: str,
        filter: dict[str, JsonValue],
        projection: dict[str, JsonValue] | None,
    ) -> DocumentQueryValidationResult:
        """Validate a find() filter (and optional projection) without executing it."""
        issues: list[ValidationIssue] = []
        self._validate_collection_name(collection, issues)
        self._walk(filter, 0, issues)
        if projection is not None:
            self._walk(projection, 0, issues)
        return self._result(DocumentOperationType.FIND, collection, issues)

    def validate_aggregate(
        self,
        collection: str,
        pipeline: list[dict[str, JsonValue]],
    ) -> DocumentQueryValidationResult:
        """Validate an aggregation pipeline without executing it."""
        issues: list[ValidationIssue] = []
        self._validate_collection_name(collection, issues)
        self._walk_pipeline(pipeline, 0, issues)
        return self._result(DocumentOperationType.AGGREGATE, collection, issues)

    def _walk_pipeline(
        self,
        stages: object,
        depth: int,
        issues: list[ValidationIssue],
    ) -> None:
        """Validate a list of stage dicts: the top-level pipeline or a nested sub-pipeline.

        `$lookup.pipeline` and each `$facet` output field hold their own nested list of
        stages (standard, documented MongoDB syntax) — these are structurally stage lists,
        never operator expressions, so they must be validated the same way as the top-level
        pipeline instead of falling through to `_walk`, which only recognizes operators.
        """
        if depth > _MAX_NESTING_DEPTH:
            issues.append(
                ValidationIssue(
                    code="NESTING_TOO_DEEP",
                    message=f"El payload excede la profundidad máxima de {_MAX_NESTING_DEPTH}.",
                )
            )
            return
        if not isinstance(stages, list):
            issues.append(
                ValidationIssue(
                    code="STAGE_SHAPE_INVALID",
                    message="Un sub-pipeline debe ser una lista de etapas.",
                )
            )
            return
        for stage in stages:
            if not isinstance(stage, dict) or len(stage) != 1:
                issues.append(
                    ValidationIssue(
                        code="STAGE_SHAPE_INVALID",
                        message="Cada etapa del pipeline debe tener exactamente una clave.",
                    )
                )
                continue
            stage_name = next(iter(stage))
            if not MongoOperatorPolicy.stage_is_allowed(stage_name):
                if MongoOperatorPolicy.stage_is_explicitly_blocked(stage_name):
                    issues.append(
                        ValidationIssue(
                            code="STAGE_NOT_ALLOWED",
                            message=f"La etapa '{stage_name}' está bloqueada explícitamente.",
                        )
                    )
                else:
                    issues.append(
                        ValidationIssue(
                            code="STAGE_NOT_ALLOWED",
                            message=f"La etapa '{stage_name}' no está permitida.",
                        )
                    )
                continue
            self._walk_stage_argument(stage_name, stage[stage_name], depth, issues)

    def _walk_stage_argument(
        self,
        stage_name: str,
        argument: JsonValue,
        depth: int,
        issues: list[ValidationIssue],
    ) -> None:
        """Dispatch a stage's own argument, recursing into any nested sub-pipeline."""
        if stage_name == "$lookup" and isinstance(argument, dict):
            for key, nested in argument.items():
                if key == "pipeline":
                    self._walk_pipeline(nested, depth + 1, issues)
                else:
                    self._walk(nested, depth + 1, issues)
            return
        if stage_name == "$facet" and isinstance(argument, dict):
            for nested in argument.values():
                self._walk_pipeline(nested, depth + 1, issues)
            return
        self._walk(argument, depth + 1, issues)

    def _walk(self, value: JsonValue, depth: int, issues: list[ValidationIssue]) -> None:
        """Recurse dict/list values, flagging any '$'-prefixed key not on the allowlist."""
        if depth > _MAX_NESTING_DEPTH:
            issues.append(
                ValidationIssue(
                    code="NESTING_TOO_DEEP",
                    message=f"El payload excede la profundidad máxima de {_MAX_NESTING_DEPTH}.",
                )
            )
            return
        if isinstance(value, dict):
            for key, nested in value.items():
                if key.startswith("$") and not MongoOperatorPolicy.operator_is_allowed(key):
                    if MongoOperatorPolicy.operator_is_explicitly_blocked(key):
                        issues.append(
                            ValidationIssue(
                                code="OPERATOR_NOT_ALLOWED",
                                message=f"El operador '{key}' está bloqueado explícitamente.",
                            )
                        )
                    else:
                        issues.append(
                            ValidationIssue(
                                code="OPERATOR_NOT_ALLOWED",
                                message=f"El operador '{key}' no está permitido.",
                            )
                        )
                self._walk(nested, depth + 1, issues)
        elif isinstance(value, list):
            for item in value:
                self._walk(item, depth + 1, issues)

    @staticmethod
    def _validate_collection_name(collection: str, issues: list[ValidationIssue]) -> None:
        if not collection or _COLLECTION_NAME_PATTERN.match(collection) is None:
            issues.append(
                ValidationIssue(
                    code="COLLECTION_NAME_INVALID",
                    message=f"El nombre de colección '{collection}' no es válido.",
                )
            )

    @staticmethod
    def _result(
        operation: DocumentOperationType,
        collection: str,
        issues: list[ValidationIssue],
    ) -> DocumentQueryValidationResult:
        executable = not issues
        return DocumentQueryValidationResult(
            valid=executable,
            executable=executable,
            operation=operation,
            collection=collection,
            blocked_reasons=tuple(issues),
            warnings=(),
        )
