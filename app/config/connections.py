"""Load and validate secret-free connection declarations from YAML."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.exceptions import ConfigurationError
from app.models.connections import ConnectionsConfig


class ConnectionsConfigLoader:
    """Read a YAML file and produce a fully validated root model."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ConnectionsConfig:
        """Load YAML without resolving or storing secret values."""
        try:
            content = self._path.read_text(encoding="utf-8")
        except OSError as error:
            raise ConfigurationError(
                code="CONFIG_READ_ERROR",
                message=f"No se pudo leer el archivo de conexiones: {self._path}",
            ) from error

        try:
            raw_config: Any = yaml.safe_load(content)
        except yaml.YAMLError as error:
            raise ConfigurationError(
                code="CONFIG_YAML_ERROR",
                message="El archivo de conexiones no contiene YAML válido.",
            ) from error

        if not isinstance(raw_config, dict):
            raise ConfigurationError(
                code="CONFIG_ROOT_ERROR",
                message="El archivo de conexiones debe contener un objeto raíz.",
            )

        try:
            return ConnectionsConfig.model_validate(raw_config)
        except ValidationError as error:
            raise ConfigurationError(
                code="CONFIG_VALIDATION_ERROR",
                message=f"La configuración de conexiones es inválida: {error}",
            ) from error
