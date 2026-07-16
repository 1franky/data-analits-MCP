"""Registry-based exporter construction without format conditionals."""

from collections.abc import Callable
from dataclasses import dataclass

from app.exceptions import ReportFormatNotSupportedError
from app.models.reporting import ReportFormat
from app.reporting.exporters.base import ReportExporter

ReportExporterBuilder = Callable[[], ReportExporter]


@dataclass(frozen=True, slots=True)
class ReportExporterRegistration:
    """Builder registered for one report format."""

    builder: ReportExporterBuilder


class ReportExporterFactory:
    """Create exporters through an explicit format registry."""

    def __init__(self) -> None:
        self._registrations: dict[ReportFormat, ReportExporterRegistration] = {}

    def register(self, report_format: ReportFormat, builder: ReportExporterBuilder) -> None:
        """Register or replace one format exporter."""
        self._registrations[report_format] = ReportExporterRegistration(builder)

    def supports(self, report_format: ReportFormat) -> bool:
        """Return whether an exporter is registered for a format."""
        return report_format in self._registrations

    def create(self, report_format: ReportFormat) -> ReportExporter:
        """Construct the registered exporter for a requested format."""
        registration = self._registrations.get(report_format)
        if registration is None:
            raise ReportFormatNotSupportedError(report_format.value)
        return registration.builder()
