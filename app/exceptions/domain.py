"""Domain exceptions with stable, non-sensitive error codes."""


class DataPlatformError(Exception):
    """Base error safe to normalize at transport boundaries."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ConfigurationError(DataPlatformError):
    """Raised when project configuration is missing or invalid."""


class ConnectionNotFoundError(DataPlatformError):
    """Raised when a requested connection ID is unknown."""

    def __init__(self, connection_id: str) -> None:
        super().__init__(
            code="CONNECTION_NOT_FOUND",
            message=f"La conexión '{connection_id}' no existe.",
        )


class ConnectionDisabledError(DataPlatformError):
    """Raised when a disabled connection is requested."""

    def __init__(self, connection_id: str) -> None:
        super().__init__(
            code="CONNECTION_DISABLED",
            message=f"La conexión '{connection_id}' está deshabilitada.",
        )


class AdapterNotAvailableError(DataPlatformError):
    """Raised when no adapter is registered for an engine."""

    def __init__(self, engine_type: str) -> None:
        super().__init__(
            code="ADAPTER_NOT_AVAILABLE",
            message=f"No existe un adaptador disponible para '{engine_type}'.",
        )


class SecretNotConfiguredError(DataPlatformError):
    """Raised when an enabled connection cannot resolve its secret."""

    def __init__(self, variable_name: str) -> None:
        super().__init__(
            code="SECRET_NOT_CONFIGURED",
            message=f"La variable de entorno '{variable_name}' no está configurada.",
        )


class DatabaseOperationError(DataPlatformError):
    """Raised when a database metadata operation fails."""


class DatabaseObjectNotFoundError(DataPlatformError):
    """Raised when database metadata does not contain an object."""

    def __init__(self, schema: str, object_name: str) -> None:
        super().__init__(
            code="DATABASE_OBJECT_NOT_FOUND",
            message=f"El objeto '{schema}.{object_name}' no existe o no es visible.",
        )


class CatalogRequestError(DataPlatformError):
    """Raised when a catalog request violates its public contract."""


class CatalogSnapshotNotFoundError(DataPlatformError):
    """Raised when metadata exploration has no valid cached snapshot."""

    def __init__(self, connection_id: str) -> None:
        super().__init__(
            code="CATALOG_SNAPSHOT_NOT_FOUND",
            message=(
                f"La conexión '{connection_id}' no tiene un snapshot de catálogo; "
                "ejecuta refresh_schema_cache primero."
            ),
        )


class GenerationNotConfiguredError(DataPlatformError):
    """Raised when generation is requested without an enabled provider."""

    def __init__(self) -> None:
        super().__init__(
            code="GENERATION_NOT_CONFIGURED",
            message="La generación de SQL por lenguaje natural no está configurada o habilitada.",
        )


class GenerationRequestError(DataPlatformError):
    """Raised when a generation request violates its public contract."""


class GenerationProviderNotAvailableError(DataPlatformError):
    """Raised when no LLM provider is registered for the configured type."""

    def __init__(self, provider_type: str) -> None:
        super().__init__(
            code="GENERATION_PROVIDER_NOT_AVAILABLE",
            message=f"No existe un proveedor LLM disponible para '{provider_type}'.",
        )


class GenerationProviderError(DataPlatformError):
    """Raised on LLM provider timeouts, transport errors or invalid responses."""


class LlmGenerationParseError(DataPlatformError):
    """Raised when the LLM response cannot be parsed as a valid generation payload."""

    def __init__(self) -> None:
        super().__init__(
            code="GENERATION_RESPONSE_PARSE_ERROR",
            message="La respuesta del proveedor LLM no se pudo interpretar como generación válida.",
        )


class LlmExplanationParseError(DataPlatformError):
    """Raised when the LLM response cannot be parsed as a valid explanation payload."""

    def __init__(self) -> None:
        super().__init__(
            code="EXPLANATION_RESPONSE_PARSE_ERROR",
            message=(
                "La respuesta del proveedor LLM no se pudo interpretar como explicación válida."
            ),
        )


class ReportingNotConfiguredError(DataPlatformError):
    """Raised when report generation is requested without being enabled."""

    def __init__(self) -> None:
        super().__init__(
            code="REPORTING_NOT_CONFIGURED",
            message="La generación de reportes no está habilitada.",
        )


class ReportFormatNotSupportedError(DataPlatformError):
    """Raised when a requested report format is outside the configured allowlist."""

    def __init__(self, format_value: str) -> None:
        super().__init__(
            code="REPORT_FORMAT_NOT_SUPPORTED",
            message=f"El formato de reporte '{format_value}' no está permitido.",
        )


class ReportPeriodInvalidError(DataPlatformError):
    """Raised when a custom report period is missing an explicit date range."""

    def __init__(self) -> None:
        super().__init__(
            code="REPORT_PERIOD_INVALID",
            message="El periodo del reporte requiere fecha de inicio y fin explícitas.",
        )


class ReportTooLargeError(DataPlatformError):
    """Raised when a report cannot fit the configured inline size budget."""

    def __init__(self) -> None:
        super().__init__(
            code="REPORT_TOO_LARGE",
            message="El reporte excede el tamaño máximo permitido, incluso truncado.",
        )


class RagNotConfiguredError(DataPlatformError):
    """Raised when RAG is requested without an enabled embedding provider."""

    def __init__(self) -> None:
        super().__init__(
            code="RAG_NOT_CONFIGURED",
            message="El RAG documental no está configurado o habilitado.",
        )


class RagRequestError(DataPlatformError):
    """Raised when a RAG request violates its public contract."""


class EmbeddingProviderNotAvailableError(DataPlatformError):
    """Raised when no embedding provider is registered for the configured type."""

    def __init__(self, provider_type: str) -> None:
        super().__init__(
            code="EMBEDDING_PROVIDER_NOT_AVAILABLE",
            message=f"No existe un proveedor de embeddings disponible para '{provider_type}'.",
        )


class EmbeddingProviderError(DataPlatformError):
    """Raised on embedding provider timeouts, transport errors or invalid responses."""


class VectorStoreError(DataPlatformError):
    """Raised on vector store connectivity, collection or dimension errors."""


class DocumentNotFoundError(DataPlatformError):
    """Raised when a requested indexed document does not exist."""

    def __init__(self, document_id: str) -> None:
        super().__init__(
            code="DOCUMENT_NOT_FOUND",
            message=f"El documento '{document_id}' no existe en el índice.",
        )


class UnsupportedDocumentFormatError(DataPlatformError):
    """Raised when a document extension is outside the configured allowlist."""

    def __init__(self, extension: str) -> None:
        super().__init__(
            code="UNSUPPORTED_DOCUMENT_FORMAT",
            message=f"La extensión '{extension}' no está permitida para indexación.",
        )
