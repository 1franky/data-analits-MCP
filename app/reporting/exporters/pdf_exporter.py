"""PDF report exporter backed by fpdf2."""

from fpdf import FPDF

from app.reporting.exporters.base import ReportData, ReportExporter

_PAGE_MARGIN_MM = 10.0
_ROW_HEIGHT_MM = 6.0
_MAX_COLUMN_TEXT_LENGTH = 40


class PdfReportExporter(ReportExporter):
    """Render a report as a paginated PDF table with a metadata header."""

    content_type = "application/pdf"
    file_extension = "pdf"

    def export(self, data: ReportData) -> bytes:
        """Write a metadata header followed by a paginated data table."""
        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=_PAGE_MARGIN_MM)
        pdf.add_page()
        pdf.set_font("Helvetica", style="B", size=14)
        _write_line(pdf, data.title)
        pdf.set_font("Helvetica", size=10)
        _write_line(pdf, f"Generado: {data.generated_at.isoformat()}")
        if data.period_label:
            _write_line(pdf, f"Periodo: {data.period_label}")
        if data.applied_filters:
            _write_line(pdf, f"Filtros: {'; '.join(data.applied_filters)}")
        pdf.ln(_ROW_HEIGHT_MM / 2)

        if not data.rows:
            pdf.set_font("Helvetica", style="I", size=10)
            _write_line(pdf, "Sin resultados.")
            return bytes(pdf.output())

        usable_width = pdf.w - 2 * _PAGE_MARGIN_MM
        column_width = usable_width / max(len(data.columns), 1)
        pdf.set_font("Helvetica", style="B", size=9)
        for column in data.columns:
            pdf.cell(column_width, _ROW_HEIGHT_MM, _truncate(column), border=1)
        pdf.ln(_ROW_HEIGHT_MM)

        pdf.set_font("Helvetica", size=8)
        for row in data.rows:
            for value in row:
                text = "" if value is None else str(value)
                pdf.cell(column_width, _ROW_HEIGHT_MM, _truncate(text), border=1)
            pdf.ln(_ROW_HEIGHT_MM)

        return bytes(pdf.output())


def _write_line(pdf: FPDF, text: str) -> None:
    """Write one full-width line and reset the cursor to the left margin."""
    pdf.multi_cell(0, _ROW_HEIGHT_MM, text, new_x="LMARGIN", new_y="NEXT")


def _truncate(text: str) -> str:
    if len(text) <= _MAX_COLUMN_TEXT_LENGTH:
        return text
    return text[: _MAX_COLUMN_TEXT_LENGTH - 1] + "…"
