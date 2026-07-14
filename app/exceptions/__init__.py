"""Normalized domain exceptions."""

from app.exceptions.domain import (
    AdapterNotAvailableError,
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
    "ConfigurationError",
    "ConnectionDisabledError",
    "ConnectionNotFoundError",
    "DataPlatformError",
    "DatabaseObjectNotFoundError",
    "DatabaseOperationError",
    "SecretNotConfiguredError",
]
