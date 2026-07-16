"""Shared contract implemented by every report exporter."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from app.models.query import SerializedValue


class ReportData(BaseModel):
    """Tabular result plus display metadata, ready to be exported."""

    model_config = ConfigDict(frozen=True)

    columns: tuple[str, ...]
    rows: tuple[tuple[SerializedValue, ...], ...]
    title: str
    generated_at: datetime
    period_label: str | None
    applied_filters: tuple[str, ...]


class ReportExporter(ABC):
    """Render a ReportData into the bytes of one downloadable file format."""

    content_type: ClassVar[str]
    file_extension: ClassVar[str]

    @abstractmethod
    def export(self, data: ReportData) -> bytes:
        """Render the report as bytes for the concrete file format."""
        raise NotImplementedError
