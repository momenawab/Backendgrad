"""
F6 — render report data dicts/lists to a PDF (reportlab).
"""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)


def _flatten_rows(data):
    """Turn a report payload into (headers, rows) for tabular output."""
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # Find the first list value to tabulate; else show key/value pairs.
        list_val = next((v for v in data.values() if isinstance(v, list)), None)
        if list_val is not None:
            items = list_val
        else:
            return ['Field', 'Value'], [[str(k), str(v)] for k, v in data.items()]
    else:
        return ['Value'], [[str(data)]]

    if not items:
        return ['(no data)'], []
    if isinstance(items[0], dict):
        headers = list(items[0].keys())
        rows = [[str(it.get(h, '')) for h in headers] for it in items]
        return headers, rows
    return ['Value'], [[str(it)] for it in items]


def build_report_pdf(title, data):
    """Return PDF bytes for the given report title + data payload."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f'SafeSight — {title}', styles['Title']),
        Paragraph(f'Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}', styles['Normal']),
        Spacer(1, 8 * mm),
    ]

    headers, rows = _flatten_rows(data)
    table_data = [headers] + rows[:500]  # cap rows for a sane PDF
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EEF2FF')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()
