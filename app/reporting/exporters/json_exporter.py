"""JSON report exporter using the standard library only."""

import json

from app.reporting.exporters.base import ReportData, ReportExporter


class JsonReportExporter(ReportExporter):
    """Render a report as a self-describing UTF-8 JSON document."""

    content_type = "application/json"
    file_extension = "json"

    def export(self, data: ReportData) -> bytes:
        """Serialize metadata plus columns/rows as one deterministic JSON document."""
        payload = {
            "title": data.title,
            "generated_at": data.generated_at.isoformat(),
            "period_label": data.period_label,
            "applied_filters": list(data.applied_filters),
            "columns": list(data.columns),
            "rows": [list(row) for row in data.rows],
            "row_count": len(data.rows),
        }
        return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
