"""Default exporter registrations available in the running application."""

from app.models.reporting import ReportFormat
from app.reporting.exporters.csv_exporter import CsvReportExporter
from app.reporting.exporters.json_exporter import JsonReportExporter
from app.reporting.exporters.pdf_exporter import PdfReportExporter
from app.reporting.exporters.registry import ReportExporterFactory
from app.reporting.exporters.xlsx_exporter import XlsxReportExporter


def create_report_exporter_factory() -> ReportExporterFactory:
    """Create an isolated registry with all implemented report exporters."""
    factory = ReportExporterFactory()
    factory.register(ReportFormat.CSV, CsvReportExporter)
    factory.register(ReportFormat.JSON, JsonReportExporter)
    factory.register(ReportFormat.XLSX, XlsxReportExporter)
    factory.register(ReportFormat.PDF, PdfReportExporter)
    return factory
