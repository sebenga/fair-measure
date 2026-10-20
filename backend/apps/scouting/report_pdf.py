"""Render a talent report document (see talent_reports.py) as a PDF.

The PDF is drawn from the same document the screen shows, so the two never
disagree. The organisation's logo heads every page when it can be fetched.
"""

from __future__ import annotations

import io
import logging
from xml.sax.saxutils import escape

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.spider import SpiderChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#6b7785")
ACCENT = colors.HexColor("#0f766e")
LIGHT = colors.HexColor("#eef2f5")
MARK = colors.HexColor("#dcfce7")
SERIES = [ACCENT, colors.HexColor("#c2410c"), colors.HexColor("#4338ca"), colors.HexColor("#a16207")]

_base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("title", parent=_base["Title"], fontSize=18, leading=22, textColor=INK, alignment=0),
    "subtitle": ParagraphStyle("subtitle", parent=_base["Normal"], fontSize=11, textColor=MUTED, leading=14),
    "heading": ParagraphStyle("heading", parent=_base["Heading3"], fontSize=11.5, textColor=ACCENT, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", parent=_base["Normal"], fontSize=9, leading=12, textColor=INK),
    "cell": ParagraphStyle("cell", parent=_base["Normal"], fontSize=8, leading=10, textColor=INK),
    "head": ParagraphStyle("head", parent=_base["Normal"], fontSize=8, leading=10, textColor=colors.white),
    "note": ParagraphStyle("note", parent=_base["Normal"], fontSize=7.5, leading=10, textColor=MUTED),
}
WIDTH = A4[0] - 30 * mm


def _p(text, style: str = "body") -> Paragraph:
    return Paragraph(escape(str(text if text is not None else "—")), STYLES[style])


def _logo(url: str):
    if not url:
        return None
    try:
        import requests

        response = requests.get(url, timeout=3)
        response.raise_for_status()
        image = Image(io.BytesIO(response.content))
        ratio = image.imageWidth / image.imageHeight if image.imageHeight else 1
        image.drawHeight = 14 * mm
        image.drawWidth = 14 * mm * ratio
        return image
    except Exception:  # A missing logo never stops an export.
        logger.info("Report logo could not be loaded from %s", url)
        return None


def _header(report: dict) -> list:
    organisation = report.get("organisation") or {}
    lines = [
        _p(organisation.get("name") or "Fair Measure", "subtitle"),
        Paragraph(escape(report["title"]), STYLES["title"]),
        _p(report.get("subtitle", ""), "subtitle"),
    ]
    logo = _logo(organisation.get("logo_url", ""))
    if logo is None:
        return [*lines, Spacer(1, 6)]
    block = Table([[logo, lines]], colWidths=[logo.drawWidth + 4 * mm, None])
    block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return [block, Spacer(1, 6)]


def _facts(section: dict) -> list:
    rows = []
    for row in section["rows"]:
        detail = []
        if row.get("date"):
            detail.append(row["date"])
        if row.get("verified") is not None:
            detail.append("verified" if row["verified"] else "self-reported")
        if row.get("source"):
            detail.append(row["source"])
        rows.append([_p(row["label"], "cell"), _p(row["value"], "cell"), _p(" · ".join(detail), "note")])
    if not rows:
        return []
    grid = Table(rows, colWidths=[WIDTH * 0.3, WIDTH * 0.35, WIDTH * 0.35])
    grid.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return [grid]


def _table(section: dict) -> list:
    columns = section["columns"]
    data = [[_p(column, "head") for column in columns]]
    data += [[_p(cell, "cell") for cell in row] for row in section["rows"]]
    if len(data) == 1:
        return [_p("Nothing to show yet.", "note")]
    first = WIDTH * (0.28 if len(columns) > 3 else 0.4)
    rest = (WIDTH - first) / max(len(columns) - 1, 1)
    grid = Table(data, colWidths=[first, *[rest] * (len(columns) - 1)], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]
    for index in section.get("highlight") or []:
        style.append(("BACKGROUND", (0, index + 1), (-1, index + 1), MARK))
    grid.setStyle(TableStyle(style))
    return [grid]


def _radar(section: dict) -> list:
    series = [row for row in section["series"] if any(value is not None for value in row["values"])]
    if not series:
        return [_p("No ratings yet.", "note")]
    drawing = Drawing(WIDTH, 210)
    chart = SpiderChart()
    chart.x, chart.y, chart.width, chart.height = WIDTH / 2 - 95, 15, 190, 180
    chart.data = [[value or 0 for value in row["values"]] for row in series]
    chart.labels = section["axes"]
    chart.spokeLabels.fontSize = 7
    for index in range(len(series)):
        chart.strands[index].strokeColor = SERIES[index % len(SERIES)]
        chart.strands[index].fillColor = colors.Color(*SERIES[index % len(SERIES)].rgb(), alpha=0.15)
        chart.strands[index].strokeWidth = 1.2
    drawing.add(chart)
    for index, row in enumerate(series):
        drawing.add(String(4, 195 - index * 11, f"■ {row['name']}", fontSize=7.5, fillColor=SERIES[index % len(SERIES)]))
    return [drawing]


def _line(section: dict) -> list:
    points = [row for row in section["points"] if row.get("value") is not None]
    if len(points) < 2:
        return [_p(f"{len(points)} dated rating(s) so far; a chart needs two.", "note")] if points else []
    drawing = Drawing(WIDTH, 150)
    chart = LinePlot()
    chart.x, chart.y, chart.width, chart.height = 30, 25, WIDTH - 50, 110
    chart.data = [[(index, row["value"]) for index, row in enumerate(points)]]
    chart.lines[0].strokeColor = ACCENT
    chart.lines[0].strokeWidth = 1.5
    chart.yValueAxis.valueMin = 0
    chart.yValueAxis.valueMax = section.get("max") or max(row["value"] for row in points)
    chart.xValueAxis.valueMin = 0
    chart.xValueAxis.valueMax = max(len(points) - 1, 1)
    chart.xValueAxis.valueSteps = list(range(len(points)))
    chart.xValueAxis.labelTextFormat = lambda value: points[int(value)]["date"] if int(value) < len(points) else ""
    chart.xValueAxis.labels.fontSize = 6
    chart.xValueAxis.labels.angle = 30
    chart.yValueAxis.labels.fontSize = 7
    drawing.add(chart)
    return [drawing]


def _notes(section: dict) -> list:
    if not section["items"]:
        return [_p("No notes.", "note")]
    return [
        _p(f"{item['date']} · {item['author']}: {item['text']}")
        for item in section["items"]
    ]


def _links(section: dict) -> list:
    return [
        Paragraph(f'{escape(item["label"])}: <link href="{escape(item["url"])}" color="#0f766e">{escape(item["url"])}</link>', STYLES["body"])
        for item in section["items"]
    ]


def _highlights(section: dict) -> list:
    return [_p(f"• {item}") for item in section["items"]]


RENDER = {
    "facts": _facts,
    "table": _table,
    "radar": _radar,
    "line": _line,
    "notes": _notes,
    "links": _links,
    "highlights": _highlights,
}


def render(report: dict) -> bytes:
    buffer = io.BytesIO()
    generated = str(report.get("generated_at", ""))[:16].replace("T", " ")

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            15 * mm,
            10 * mm,
            f"Built from stored data on Fair Measure · exported {generated}"
            f"{' for ' + report['generated_for'] if report.get('generated_for') else ''} · this export is logged",
        )
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    template = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"{report['title']} · {report.get('subtitle', '')}",
        author=(report.get("organisation") or {}).get("name") or "Fair Measure",
    )
    story = _header(report)
    for section in report["sections"]:
        body = RENDER.get(section["type"], lambda _section: [])(section)
        block = [_p(section["heading"], "heading"), *body]
        if section.get("note"):
            block.append(_p(section["note"], "note"))
        if section["type"] in {"radar", "line", "facts"}:
            story.append(KeepTogether(block))
        else:
            story.extend(block)
    template.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
