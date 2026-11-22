#!/usr/bin/env python3
"""Render the TailCache manuscript and its figures."""

import argparse
import csv
import json
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
FIGURES = (
    "fig08_cross_host_locality.svg",
    "fig09_mixed_collection_time.svg",
    "fig10_saturated_payload.svg",
    "fig11_response_pressure.svg",
)
DEFAULT_PDF = ROOT / "output/pdf/tailcache-preprint.pdf"
INK = colors.HexColor("#17242F")
MUTED = colors.HexColor("#495A67")
RULE = colors.HexColor("#CFD8DD")
TEAL = colors.HexColor("#026059")
RUST = colors.HexColor("#9A421F")
WHITE = colors.white
FRAME = 487
STYLES = {
    "title": ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=25, leading=30,
                            textColor=INK, spaceAfter=5, keepWithNext=True),
    "subtitle": ParagraphStyle("Subtitle", fontName="Helvetica-Bold", fontSize=14, leading=18,
                               textColor=INK, spaceAfter=13, keepWithNext=True),
    "section": ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=14, leading=17,
                              textColor=INK, spaceBefore=15, spaceAfter=6, keepWithNext=True),
    "subsection": ParagraphStyle("Subsection", fontName="Helvetica-Bold", fontSize=11.5,
                                 leading=14, textColor=INK, spaceBefore=12, spaceAfter=5,
                                 keepWithNext=True),
    "body": ParagraphStyle("Body", fontName="Times-Roman", fontSize=11, leading=14.5,
                           textColor=INK, spaceAfter=8, allowWidows=False, allowOrphans=False),
    "reference": ParagraphStyle("Reference", fontName="Times-Roman", fontSize=9.5, leading=12.5,
                                textColor=INK, spaceAfter=3.5, allowWidows=False, allowOrphans=False),
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


def plot_label(drawing, x, y, value, **options):
    style = dict(fillColor=MUTED, fontName="Helvetica", fontSize=8)
    style.update(options)
    drawing.add(String(x, y, value, **style))


def scatter_panel(drawing, bounds, groups, ticks, tick_text, log=False, left_axis=True, reference=None):
    left, right, bottom, top = bounds
    transform = math.log10 if log else float
    low, high = transform(ticks[0]), transform(ticks[-1])

    def y(value):
        return bottom + (transform(value) - low) / (high - low) * (top - bottom)

    step = (right - left) / len(groups)
    for tick in ticks:
        line = Line(left, y(tick), right, y(tick),
                    strokeColor=MUTED if tick == reference else RULE, strokeWidth=0.7)
        if tick == reference:
            line.strokeDashArray = [3, 3]
        drawing.add(line)
        if left_axis:
            plot_label(drawing, left - 6, y(tick) - 2.6, tick_text(tick), textAnchor="end")
    for i, (label, families) in enumerate(groups):
        x = left + step * (i + 0.5)
        for j, text in enumerate(label.split("|")):
            plot_label(drawing, x, bottom - 14 - 11 * j, text, textAnchor="middle")
        for cohort, family in enumerate(families):
            center = x + (cohort - (len(families) - 1) / 2) * min(step / 4, 16)
            for index, (value, color, clean) in enumerate(family):
                jitter = (index - (len(family) - 1) / 2) * 4.5
                drawing.add(Circle(center + jitter, y(value), 2.9, fillColor=color if clean else WHITE,
                                   strokeColor=color, strokeWidth=0.9))


def backend_marks(rows, measure):
    clean = lambda row: not (row["c"]["warnings"] or row["h"]["warnings"])
    return [
        [(measure(row[backend]), color, clean(row)) for row in rows]
        for backend, color in (("c", RUST), ("h", TEAL))
    ]


def panel_heading(drawing, mid, label):
    plot_label(drawing, mid, 162, label, textAnchor="middle", fontName="Helvetica-Bold",
               fillColor=INK, fontSize=10)


def measured_backend_legend(drawing):
    plot_label(drawing, FRAME - 123, 181, "Caffeine", fillColor=RUST, fontName="Helvetica-Bold")
    plot_label(drawing, FRAME - 64, 181, "Chronicle", fillColor=TEAL, fontName="Helvetica-Bold")


def mixed_figure(data):
    drawing = Drawing(FRAME, 193)
    plot_label(drawing, 4, 181, "Time in mixed GC pauses (ms)", fontName="Helvetica-Bold", fillColor=INK)
    measured_backend_legend(drawing)
    for index, (name, title) in enumerate((("second", "30-second windows"), ("long", "90-second windows"))):
        left, right = ((43, 250), (265, 480))[index]
        panel_heading(drawing, (left + right) / 2, title)
        rows = data["locality"][name]
        groups = [
            (f"{key:,} keys", backend_marks([r for r in rows if r["key"] == key], lambda fork: fork["mixed"]))
            for key in (2048, 32768)
        ]
        scatter_panel(drawing, (left, right, 36, 148), groups, [0, 30, 60, 90, 120], str,
                      left_axis=index == 0)
    return drawing


def payload_figure(data):
    drawing = Drawing(FRAME, 176)
    plot_label(drawing, 4, 163, "Chronicle / Caffeine combined service p99.9", fontName="Helvetica-Bold", fillColor=INK)
    plot_label(drawing, FRAME - 5, 163, "Lower ratios favor Chronicle", textAnchor="end")
    groups = []
    for payload, label in ((256, "256 B"), (4096, "4 KiB")):
        for heap in (0, 288):
            marks = []
            for row in data["payload"]:
                if (row["payload"], row["heap"], row["writes"]) == (payload, heap, 5):
                    ratio = row["h"]["service"][2] / row["c"]["service"][2]
                    marks.append((ratio, TEAL if ratio < 1 else RUST,
                                  not (row["c"]["warnings"] or row["h"]["warnings"])))
            groups.append((f"{label}|{heap} MiB", [marks]))
    scatter_panel(drawing, (40, 480, 38, 143), groups, [0.25, 0.5, 0.75, 1, 1.25],
                  str, reference=1)
    return drawing


def pressure_figure(data):
    drawing = Drawing(FRAME, 193)
    plot_label(drawing, 4, 181, "Scheduled-response p99.9 (log scale)", fontName="Helvetica-Bold", fillColor=INK)
    measured_backend_legend(drawing)
    for index, (name, title) in enumerate((("short", "Earlier short replay"), ("full", "Newer full-key updates"))):
        left, right = ((59, 252), (266, 483))[index]
        panel_heading(drawing, (left + right) / 2, title)
        rows = data["pressure"][name]
        groups = [
            (f"{heap} MiB", backend_marks([r for r in rows if r["heap"] == heap],
                                        lambda fork: fork["response"][2] / 1000))
            for heap in sorted({r["heap"] for r in rows})
        ]
        scatter_panel(drawing, (left, right, 36, 148), groups, [5, 10, 100, 1000, 10000, 30000],
                      lambda v: f"{v:g} µs" if v < 1000 else f"{v / 1000:g} ms",
                      log=True, left_axis=index == 0)
    return drawing


def inline(value):
    value = escape(value)
    value = re.sub(r"\[([^\]]+)\]\((https://[^)]+)\)", r'<a href="\2" color="#026059">\1</a>', value)
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", value)
    value = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', value)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)


def table(block):
    rows = []
    widths = {
        5: [115, 65, 99, 109, 99],
        6: [55, 89, 79, 88, 80, 96],
    }
    text_columns = {5: 1, 6: 2}
    for index, line in enumerate(block.splitlines()):
        if index == 1:
            continue
        fields = line.strip("|").split("|")
        text_count = text_columns[len(fields)]
        styles = ["cell"] * text_count + ["numeric"] * (len(fields) - text_count)
        entries = [inline(field.strip()) for field in fields]
        rows.append([Paragraph(f"<b>{value}</b>" if index == 0 else value, STYLES[style])
                     for value, style in zip(entries, styles, strict=True)])
    result = Table(rows, colWidths=widths[len(rows[0])], repeatRows=1, hAlign="LEFT", spaceAfter=12)
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
    canvas.drawString(doc.leftMargin, 32, "TailCache")
    canvas.drawRightString(A4[0] - doc.rightMargin, 32, str(doc.page))
    canvas.restoreState()


def render(output, charts):
    blocks = (PAPER / "MANUSCRIPT.md").read_text().strip().split("\n\n")
    title = blocks[0].removeprefix("# ")
    headline, _, subtitle = title.partition(": ")
    story = [Paragraph(inline(headline), STYLES["title"])]
    if subtitle:
        story.append(Paragraph(inline(subtitle), STYLES["subtitle"]))
    remaining = iter(blocks[1:])
    for block in remaining:
        if block.startswith("| "):
            story.append(table(block))
        elif block.startswith("!["):
            figure = re.fullmatch(r"!\[[^\]]+\]\(figures/([^()]+)\)", block)
            if not figure or figure[1] not in charts:
                raise ValueError(f"Unexpected manuscript figure: {block}")
            caption = Paragraph(inline(next(remaining)), STYLES["body"])
            story.append(KeepTogether([charts[figure[1]], caption]))
        else:
            heading = re.match(r"^(#{1,3}) ", block)
            if heading:
                style = ("title", "section", "subsection")[len(heading[1]) - 1]
            else:
                style = "reference" if re.match(r"^\[\d+\] ", block) else "body"
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
    data = json.loads((PAPER / "review-chart-data.json").read_text())
    charts = dict(zip(FIGURES, (
        locality_figure(), mixed_figure(data), payload_figure(data), pressure_figure(data)
    ), strict=True))
    if args.update_svg:
        titles = ("Scheduled-response p99.9 by update set", "G1 mixed-collection pause time",
                  "Saturated combined service p99.9 by payload", "Scheduled-response p99.9 by added heap data")
        for (name, chart), title in zip(charts.items(), titles, strict=True):
            renderSVG.drawToFile(chart, str(PAPER / "figures" / name), title=title)
    render(args.output, charts)


if __name__ == "__main__":
    main()
