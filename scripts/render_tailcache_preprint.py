#!/usr/bin/env python3
"""Render the TailCache review manuscript and its paired locality figure."""

import argparse
import csv
import math
import re
from html import escape
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "docs/preprint"
FIGURE = PAPER / "figures/fig08_cross_host_locality.svg"
DEFAULT_PDF = ROOT / "output/pdf/tailcache-preprint-review.pdf"
INK = colors.HexColor("#17242F")
MUTED = colors.HexColor("#495A67")
RULE = colors.HexColor("#CFD8DD")
TEAL = colors.HexColor("#026059")
RUST = colors.HexColor("#9A421F")
WHITE = colors.white
FRAME = 487
STYLES = {
    "title": ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=25, leading=30,
                            textColor=INK, spaceAfter=13, keepWithNext=True),
    "section": ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=14, leading=17,
                              textColor=INK, spaceBefore=15, spaceAfter=6, keepWithNext=True),
    "subsection": ParagraphStyle("Subsection", fontName="Helvetica-Bold", fontSize=11.5,
                                 leading=14, textColor=INK, spaceBefore=12, spaceAfter=5,
                                 keepWithNext=True),
    "body": ParagraphStyle("Body", fontName="Times-Roman", fontSize=11, leading=15,
                           textColor=INK, spaceAfter=8, allowWidows=False, allowOrphans=False),
    "cell": ParagraphStyle("Cell", fontName="Helvetica", fontSize=8.5, leading=11,
                           textColor=INK),
    "numeric": ParagraphStyle("Number", fontName="Helvetica", fontSize=8.5, leading=11,
                              textColor=INK, alignment=TA_RIGHT),
}


def locality_figure():
    with (PAPER / "locality-pairs.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    plots = [
        ("First host / 30 s", "first", "30"),
        ("Second host / 30 s", "second", "30"),
        ("Second host / 90 s", "second", "90"),
    ]
    graph = Drawing(FRAME, 267)
    left, right = 133, 468

    def x(ratio):
        return left + (math.log10(ratio) + 3) / 4 * (right - left)

    def label(xpos, ypos, content, **kwargs):
        style = dict(fillColor=INK, fontName="Helvetica", fontSize=9)
        style.update(kwargs)
        graph.add(String(xpos, ypos, content, **style))

    for index, (title, host, seconds) in enumerate(plots):
        top = 243 - index * 64
        graph.add(Rect(0, top - 52, FRAME, 58, fillColor=colors.HexColor("#F3F6F7"),
                       strokeColor=None))
        label(9, top - 1, title, fontName="Helvetica-Bold")
        for key, color, y in [("2048", RUST, top - 18), ("32768", TEAL, top - 39)]:
            label(21, y - 3, f"{int(key):,} keys", fillColor=MUTED)
            points = [r for r in rows if (r["host"], r["seconds"], r["update_keys"])
                      == (host, seconds, key)]
            if len(points) != (2 if index == 1 else 4):
                raise ValueError(f"Unexpected figure coverage for {title}, {key}")
            for n, row in enumerate(points):
                ratio = int(row["chronicle_p999_ns"]) / int(row["caffeine_p999_ns"])
                if not 0.001 <= ratio <= 10:
                    raise ValueError(f"Point outside figure range: {ratio}")
                dy = (n - (len(points) - 1) / 2) * 6.6
                fill = color if row["warning_free"] == "true" else WHITE
                graph.add(Circle(x(ratio), y + dy, 3, fillColor=fill, strokeColor=color, strokeWidth=1))

    for value, tick in [(0.001, "0.001"), (0.01, "0.01"), (0.1, "0.1"), (1, "1"), (10, "10")]:
        xpos = x(value)
        if value == 1:
            graph.add(Line(xpos, 50, xpos, 249, strokeColor=MUTED, strokeDashArray=[3, 3]))
        graph.add(Line(xpos, 46, xpos, 50, strokeColor=MUTED))
        label(xpos, 34, tick, textAnchor="middle", fillColor=MUTED)
    graph.add(Line(left, 50, right, 50, strokeColor=MUTED))
    label((left + right) / 2, 12, "Chronicle / Caffeine response p99.9 (log scale)",
          textAnchor="middle", fontName="Helvetica-Bold")
    label(left, 255, "Chronicle lower", fillColor=TEAL)
    label(right, 255, "Caffeine lower", textAnchor="end", fillColor=RUST)
    return graph


def inline(value):
    value = escape(value)
    value = re.sub(r"\[([^\]]+)\]\((https://[^)]+)\)", r'<a href="\2" color="#026059">\1</a>', value)
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", value)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)


def table(block):
    rows = []
    for index, line in enumerate(block.splitlines()):
        if index == 1:
            continue
        fields = line.strip("|").split("|")
        styles = ["cell"] + ["numeric"] * (len(fields) - 1)
        entries = [inline(field.strip()) for field in fields]
        rows.append([Paragraph(f"<b>{value}</b>" if index == 0 else value, STYLES[style])
                     for value, style in zip(entries, styles, strict=True)])
    widths = [115, 65, 99, 109, 99]
    result = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT", spaceAfter=12)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EFF1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F3F6F7")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return result


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(MUTED)
    canvas.setStrokeColor(RULE)
    canvas.line(doc.leftMargin, 47, A4[0] - doc.rightMargin, 47)
    canvas.drawString(doc.leftMargin, 32, "TailCache  |  Working draft for author review")
    canvas.drawRightString(A4[0] - doc.rightMargin, 32, str(doc.page))
    canvas.restoreState()


def render(output, chart):
    blocks = (PAPER / "MANUSCRIPT.md").read_text().strip().split("\n\n")
    title = blocks[0].removeprefix("# ")
    story = []
    remaining = iter(blocks)
    for block in remaining:
        if block.startswith("| "):
            story.append(table(block))
        elif block.startswith("!["):
            if not block.endswith(f"(figures/{FIGURE.name})"):
                raise ValueError(f"Unexpected manuscript figure: {block}")
            caption = Paragraph(inline(next(remaining)), STYLES["body"])
            story.append(KeepTogether([chart, caption]))
        else:
            heading = re.match(r"^(#{1,3}) ", block)
            style = ("title", "section", "subsection")[len(heading[1]) - 1] if heading else "body"
            value = block[heading.end():] if heading else block
            story.append(Paragraph(inline(value.replace("\n", " ")), STYLES[style]))

    output.parent.mkdir(parents=True, exist_ok=True)
    margin = (A4[0] - FRAME - 12) / 2
    document = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=margin, leftMargin=margin,
                                 topMargin=53, bottomMargin=63, title=title)
    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer,
                   canvasmaker=lambda *a, **kw: Canvas(*a, **(kw | {"invariant": True})))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--update-svg", action="store_true")
    args = parser.parse_args()
    chart = locality_figure()
    if args.update_svg:
        renderSVG.drawToFile(chart, str(FIGURE), title="Scheduled-response p99.9 by update set")
    render(args.output, chart)


if __name__ == "__main__":
    main()
