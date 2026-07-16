"""CSV report exporter using the standard library only."""

import csv
import io

from app.reporting.exporters.base import ReportData, ReportExporter


class CsvReportExporter(ReportExporter):
    """Render a report as UTF-8 CSV with a leading metadata block."""

    content_type = "text/csv"
    file_extension = "csv"

    def export(self, data: ReportData) -> bytes:
        """Write metadata rows, a blank separator, the header and the data rows."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([data.title])
        writer.writerow([f"Generado: {data.generated_at.isoformat()}"])
        if data.period_label:
            writer.writerow([f"Periodo: {data.period_label}"])
        if data.applied_filters:
            writer.writerow([f"Filtros: {'; '.join(data.applied_filters)}"])
        writer.writerow([])
        writer.writerow(data.columns)
        for row in data.rows:
            writer.writerow(["" if value is None else value for value in row])
        return buffer.getvalue().encode("utf-8")
