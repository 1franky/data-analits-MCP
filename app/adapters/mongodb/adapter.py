"""Read-only MongoDB metadata and query adapter.

Structural cero-escritura guarantee: this module never imports or calls any
pymongo write method (insert_one, update_many, delete_one, bulk_write, etc.).
Combined with a server-side `read`-only role for the configured user, write
access is blocked both at the code layer and at the database layer.
"""

import base64
import json
from datetime import datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, NoReturn, cast

from bson import Binary, Decimal128, ObjectId
from pydantic import JsonValue, SecretStr
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ExecutionTimeout, OperationFailure, PyMongoError

from app.adapters.base import DocumentDatabaseAdapter
from app.exceptions import ConfigurationError, DatabaseOperationError
from app.models.connections import (
    CollectionInfo,
    ConnectionCapabilities,
    ConnectionConfig,
    ConnectionTestResult,
    QueryLanguage,
)
from app.models.document_query import AdapterDocumentResult

_ALLOWED_MONGODB_OPTIONS = {
    "authSource",
    "tls",
    "tlsAllowInvalidCertificates",
    "directConnection",
    "appName",
    "readPreference",
}

_MAX_TIME_MS_EXPIRED_CODE = 50


class MongoDbAdapter(DocumentDatabaseAdapter):
    """MongoDB adapter protected by a readonly server role and bounded operations."""

    CAPABILITIES = ConnectionCapabilities(
        query_language=QueryLanguage.DOCUMENT,
        test_connection=True,
        list_collections=True,
        execute_find=True,
        execute_aggregation=True,
    )

    def __init__(self, config: ConnectionConfig, password: SecretStr) -> None:
        if config.type.value != "mongodb":
            raise ConfigurationError(
                code="MONGODB_CONFIG_TYPE_ERROR",
                message="MongoDbAdapter requiere una conexión de tipo mongodb.",
            )
        invalid_options = set(config.options).difference(_ALLOWED_MONGODB_OPTIONS)
        if invalid_options:
            names = ", ".join(sorted(invalid_options))
            raise ConfigurationError(
                code="MONGODB_OPTIONS_ERROR",
                message=f"Opciones MongoDB no soportadas: {names}",
            )
        self._config = config
        self._password = password

    @property
    def capabilities(self) -> ConnectionCapabilities:
        """Return MongoDB document capabilities."""
        return self.CAPABILITIES

    def test_connection(self) -> ConnectionTestResult:
        """Open a bounded session and ping the admin database."""
        started_at = perf_counter()
        client = self._connect()
        try:
            client.admin.command("ping")
        except PyMongoError as error:
            return ConnectionTestResult(
                connection_id=self._config.id,
                success=False,
                latency_ms=self._elapsed_ms(started_at),
                error_code="DATABASE_CONNECTION_ERROR",
                message=f"No fue posible conectar con MongoDB: {type(error).__name__}.",
            )
        finally:
            client.close()
        return ConnectionTestResult(
            connection_id=self._config.id,
            success=True,
            latency_ms=self._elapsed_ms(started_at),
            message="Conexión MongoDB disponible.",
        )

    def list_collections(self) -> tuple[CollectionInfo, ...]:
        """List visible, non-system collections in the connection's database."""
        client = self._connect()
        try:
            names = client[self._config.database].list_collection_names()
        except PyMongoError:
            client.close()
            self._raise_metadata_error()
        client.close()
        return tuple(
            CollectionInfo(name=name) for name in sorted(names) if not name.startswith("system.")
        )

    def execute_find(
        self,
        collection: str,
        filter: dict[str, JsonValue],
        projection: dict[str, JsonValue] | None,
        max_rows: int,
        timeout_seconds: int,
        max_serialized_bytes: int,
    ) -> AdapterDocumentResult:
        """Execute a prevalidated find() and serialize a bounded result."""
        started_at = perf_counter()
        client = self._connect(timeout_seconds)
        try:
            cursor = client[self._config.database][collection].find(
                filter,
                projection=projection,
                limit=max_rows,
                max_time_ms=timeout_seconds * 1000,
            )
            raw_documents = list(cursor)
        except ExecutionTimeout:
            client.close()
            raise DatabaseOperationError(
                code="QUERY_TIMEOUT",
                message="La consulta excedió el timeout permitido.",
            ) from None
        except OperationFailure as error:
            client.close()
            if error.code == _MAX_TIME_MS_EXPIRED_CODE:
                raise DatabaseOperationError(
                    code="QUERY_TIMEOUT",
                    message="La consulta excedió el timeout permitido.",
                ) from None
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="MongoDB no pudo ejecutar la consulta de lectura.",
            ) from None
        except (ConnectionFailure, PyMongoError):
            client.close()
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="MongoDB no pudo ejecutar la consulta de lectura.",
            ) from None
        client.close()
        documents, serialized_bytes, truncated = self._serialize_documents(
            raw_documents,
            max_serialized_bytes,
        )
        return AdapterDocumentResult(
            documents=documents,
            duration_ms=self._elapsed_ms(started_at),
            truncated=truncated or len(raw_documents) >= max_rows,
            serialized_bytes=serialized_bytes,
        )

    def execute_aggregation(
        self,
        collection: str,
        pipeline: list[dict[str, JsonValue]],
        max_rows: int,
        timeout_seconds: int,
        max_serialized_bytes: int,
    ) -> AdapterDocumentResult:
        """Execute a prevalidated aggregation pipeline and serialize a bounded result."""
        started_at = perf_counter()
        # Defense in depth: never trust the caller's pipeline to already be bounded,
        # even though DocumentQueryValidationService already ran before this method
        # is reachable (mirrors apply_row_limit for SQL).
        bounded_pipeline: list[dict[str, JsonValue]] = [*pipeline, {"$limit": max_rows}]
        client = self._connect(timeout_seconds)
        try:
            cursor = client[self._config.database][collection].aggregate(
                bounded_pipeline,
                maxTimeMS=timeout_seconds * 1000,
            )
            raw_documents = list(cursor)
        except ExecutionTimeout:
            client.close()
            raise DatabaseOperationError(
                code="QUERY_TIMEOUT",
                message="La agregación excedió el timeout permitido.",
            ) from None
        except OperationFailure as error:
            client.close()
            if error.code == _MAX_TIME_MS_EXPIRED_CODE:
                raise DatabaseOperationError(
                    code="QUERY_TIMEOUT",
                    message="La agregación excedió el timeout permitido.",
                ) from None
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="MongoDB no pudo ejecutar la agregación de lectura.",
            ) from None
        except (ConnectionFailure, PyMongoError):
            client.close()
            raise DatabaseOperationError(
                code="DATABASE_QUERY_ERROR",
                message="MongoDB no pudo ejecutar la agregación de lectura.",
            ) from None
        client.close()
        documents, serialized_bytes, truncated = self._serialize_documents(
            raw_documents,
            max_serialized_bytes,
        )
        return AdapterDocumentResult(
            documents=documents,
            duration_ms=self._elapsed_ms(started_at),
            truncated=truncated or len(raw_documents) >= max_rows,
            serialized_bytes=serialized_bytes,
        )

    def _connect(self, timeout_seconds: int | None = None) -> "MongoClient[dict[str, Any]]":
        effective_timeout = min(
            timeout_seconds or self._config.connect_timeout_seconds,
            self._config.connect_timeout_seconds,
        )
        driver_options = cast("dict[str, Any]", dict(self._config.options))
        try:
            return MongoClient(
                host=self._config.host,
                port=self._config.port,
                username=self._config.username,
                password=self._password.get_secret_value(),
                serverSelectionTimeoutMS=effective_timeout * 1000,
                connectTimeoutMS=effective_timeout * 1000,
                maxPoolSize=1,
                **driver_options,
            )
        except PyMongoError as error:
            raise DatabaseOperationError(
                code="DATABASE_CONNECTION_ERROR",
                message="No fue posible construir el cliente MongoDB.",
            ) from error

    @classmethod
    def _serialize_documents(
        cls,
        raw_documents: list[dict[str, Any]],
        max_serialized_bytes: int,
    ) -> tuple[tuple[JsonValue, ...], int, bool]:
        documents: list[JsonValue] = []
        serialized_bytes = 0
        truncated = False
        for raw_document in raw_documents:
            document = cls._to_json_safe(raw_document)
            document_bytes = len(
                json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            if serialized_bytes + document_bytes > max_serialized_bytes:
                truncated = True
                break
            documents.append(document)
            serialized_bytes += document_bytes
        return tuple(documents), serialized_bytes, truncated

    @classmethod
    def _to_json_safe(cls, value: object) -> JsonValue:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal128):
            return str(value.to_decimal())
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (Binary, bytes, bytearray)):
            return f"base64:{base64.b64encode(bytes(value)).decode('ascii')}"
        if isinstance(value, dict):
            return {str(key): cls._to_json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._to_json_safe(item) for item in value]
        return str(value)

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((perf_counter() - started_at) * 1000, 3)

    @staticmethod
    def _raise_metadata_error() -> NoReturn:
        raise DatabaseOperationError(
            code="DATABASE_METADATA_ERROR",
            message="No fue posible recuperar metadata de MongoDB.",
        ) from None
