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
