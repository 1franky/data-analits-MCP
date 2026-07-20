"""HTML report exporter using the standard library only."""

from html import escape

from app.reporting.exporters.base import ReportData, ReportExporter

_STYLE = (
    "body{font-family:sans-serif;margin:1.5rem;}"
    "table{border-collapse:collapse;width:100%;}"
    "th,td{border:1px solid #ccc;padding:0.4rem 0.6rem;text-align:left;}"
    "th{background:#f0f0f0;}"
)


class HtmlReportExporter(ReportExporter):
    """Render a report as a self-contained HTML document with a metadata header."""

    content_type = "text/html; charset=utf-8"
    file_extension = "html"

    def export(self, data: ReportData) -> bytes:
        """Write an escaped metadata block, header and data rows as one HTML table."""
        lines = [
            "<!doctype html>",
            '<html lang="es">',
            "<head>",
            '<meta charset="utf-8">',
            f"<title>{escape(data.title)}</title>",
            f"<style>{_STYLE}</style>",
            "</head>",
            "<body>",
            f"<h1>{escape(data.title)}</h1>",
            f"<p>Generado: {escape(data.generated_at.isoformat())}</p>",
        ]
        if data.period_label:
            lines.append(f"<p>Periodo: {escape(data.period_label)}</p>")
        if data.applied_filters:
            lines.append(f"<p>Filtros: {escape('; '.join(data.applied_filters))}</p>")

        lines.append("<table>")
        lines.append("<thead><tr>")
        lines.extend(f"<th>{escape(column)}</th>" for column in data.columns)
        lines.append("</tr></thead>")
        lines.append("<tbody>")
        if data.rows:
            for row in data.rows:
                lines.append("<tr>")
                lines.extend(
                    f"<td>{'' if value is None else escape(str(value))}</td>" for value in row
                )
                lines.append("</tr>")
        else:
            lines.append(f'<tr><td colspan="{len(data.columns)}">Sin resultados</td></tr>')
        lines.append("</tbody>")
        lines.append("</table>")
        lines.append("</body>")
        lines.append("</html>")

        return "\n".join(lines).encode("utf-8")
