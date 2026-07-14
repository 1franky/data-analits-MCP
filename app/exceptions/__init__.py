"""Normalized domain exceptions."""

from app.exceptions.domain import (
    AdapterNotAvailableError,
    CatalogRequestError,
    ConfigurationError,
    ConnectionDisabledError,
    ConnectionNotFoundError,
    DatabaseObjectNotFoundError,
    DatabaseOperationError,
    DataPlatformError,
    SecretNotConfiguredError,
)

__all__ = [
    "AdapterNotAvailableError",
    "CatalogRequestError",
    "ConfigurationError",
    "ConnectionDisabledError",
    "ConnectionNotFoundError",
    "DataPlatformError",
    "DatabaseObjectNotFoundError",
    "DatabaseOperationError",
    "SecretNotConfiguredError",
]
