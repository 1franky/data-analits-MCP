"""XLSX report exporter backed by openpyxl."""

import io

from openpyxl import Workbook

from app.reporting.exporters.base import ReportData, ReportExporter


class XlsxReportExporter(ReportExporter):
    """Render a report as a single-sheet Excel workbook with a metadata header."""

    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    file_extension = "xlsx"

    def export(self, data: ReportData) -> bytes:
        """Write metadata rows, a blank separator, the header and the data rows."""
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "Reporte"
        sheet.append([data.title])
        sheet.append([f"Generado: {data.generated_at.isoformat()}"])
        if data.period_label:
            sheet.append([f"Periodo: {data.period_label}"])
        if data.applied_filters:
            sheet.append([f"Filtros: {'; '.join(data.applied_filters)}"])
        sheet.append([])
        sheet.append(list(data.columns))
        if data.rows:
            for row in data.rows:
                sheet.append(["" if value is None else value for value in row])
        else:
            sheet.append(["Sin resultados"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()
