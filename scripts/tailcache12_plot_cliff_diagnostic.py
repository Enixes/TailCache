#!/usr/bin/env python3
"""
Generates publication-grade SVG and PNG figures for the TailCache 90-99% Heap Cliff Diagnostic.
Reads docs/TAILCACHE_12_CLIFF_DIAGNOSTIC_EVIDENCE.json and writes SVG + PNG files to docs/figures/
and copies PNGs into the artifact directory.
"""
import json
import math
import pathlib
import subprocess

ROOT = pathlib.Path("/home/y/TailCache")
EVIDENCE = ROOT / "docs" / "TAILCACHE_12_CLIFF_DIAGNOSTIC_EVIDENCE.json"
FIG_DIR = ROOT / "docs" / "figures"
ARTIFACT_DIR = pathlib.Path("/home/y/.gemini/antigravity-cli/brain/813eaaaa-7714-484f-8709-5826310287c3")

FIG_DIR.mkdir(parents=True, exist_ok=True)
data = json.loads(EVIDENCE.read_text())

COLORS = {
    "CAFFEINE": "#dc2626",            # crimson red
    "CHRONICLE_GET": "#d97706",       # amber/orange
    "CHRONICLE_GET_USING": "#059669", # emerald green
}

LABELS = {
    "CAFFEINE": "Caffeine (On-Heap)",
    "CHRONICLE_GET": "Chronicle Map get() (Off-Heap, Allocating)",
    "CHRONICLE_GET_USING": "Chronicle Map getUsing() (Off-Heap, Zero-Alloc Read)",
}


def by_key(payload: int, live: int, mode: str):
    for r in data:
        if r["payloadBytes"] == payload and r["liveMiB"] == live and r["mode"] == mode:
            return r
    return None


def esc(s: str) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def svg_header(w: int, h: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<style>',
        '  text { font-family: "Inter", "Segoe UI", "DejaVu Sans", Arial, sans-serif; fill: #1e293b; }',
        '  .title { font-size: 17px; font-weight: 700; fill: #0f172a; }',
        '  .subtitle { font-size: 12.5px; font-weight: 400; fill: #475569; }',
        '  .panel-title { font-size: 14px; font-weight: 700; fill: #0f172a; }',
        '  .axis-label { font-size: 12px; font-weight: 600; fill: #334155; }',
        '  .tick { font-size: 11px; fill: #475569; }',
        '  .annot { font-size: 11px; font-weight: 600; }',
        '  .legend { font-size: 12px; font-weight: 600; fill: #1e293b; }',
        '  .grid { stroke: #e2e8f0; stroke-width: 1; stroke-dasharray: 3,3; }',
        '  .axis { stroke: #64748b; stroke-width: 1.5; }',
        '</style>',
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="#ffffff" rx="8"/>',
    ]


def draw_legend(lines: list[str], x: int, y: int):
    lines.append(f'<rect x="{x}" y="{y}" width="920" height="36" fill="#f8fafc" stroke="#cbd5e1" rx="6"/>')
    offsets = [24, 240, 575]
    for idx, mode in enumerate(["CAFFEINE", "CHRONICLE_GET", "CHRONICLE_GET_USING"]):
        lx = x + offsets[idx]
        ly = y + 18
        c = COLORS[mode]
        lines.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+26}" y2="{ly}" stroke="{c}" stroke-width="3"/>')
        lines.append(f'<circle cx="{lx+13}" cy="{ly}" r="4.5" fill="{c}"/>')
        lines.append(f'<text x="{lx+34}" y="{ly+4}" class="legend">{esc(LABELS[mode])}</text>')


def build_fig1_4kib_latency():
    w, h = 1140, 560
    lines = svg_header(w, h)
    lines.append('<text x="570" y="32" text-anchor="middle" class="title">'
                 '4 KiB Payloads (512 MiB G1 Heap): Closed-Loop Service vs. Open-Loop Response p99.9 Across the 89%–98% Cliff</text>')
    lines.append('<text x="570" y="52" text-anchor="middle" class="subtitle">'
                 'Why Task 12 missed the crossover: closed-loop service time hides STW Full GCs, while open-loop response latency explodes 2,418x</text>')
    draw_legend(lines, 110, 66)

    lives = [288, 312, 328, 340, 352]
    caff_occs = [by_key(4096, lv, "CAFFEINE")["steadyPostGcPct"] for lv in lives]

    # Left panel: Closed-loop service p99.9 (linear 0 -> 17 us)
    px1, py1, pw, ph = 85, 145, 430, 320
    lines.append(f'<rect x="{px1}" y="{py1}" width="{pw}" height="{ph}" fill="#fcfdff" stroke="#cbd5e1"/>')
    lines.append(f'<text x="{px1 + pw/2}" y="{py1 - 14}" text-anchor="middle" class="panel-title">'
                 'A. Closed-Loop Service p99.9 (µs) — Linear Scale</text>')

    y_max = 17.0
    for yv in [0, 4, 8, 12, 16]:
        yy = py1 + ph - (yv / y_max) * ph
        lines.append(f'<line x1="{px1}" y1="{yy:.1f}" x2="{px1+pw}" y2="{yy:.1f}" class="grid"/>')
        lines.append(f'<text x="{px1-8}" y="{yy+4:.1f}" text-anchor="end" class="tick">{yv} µs</text>')

    for i, lv in enumerate(lives):
        xx = px1 + 35 + i * ((pw - 70) / (len(lives) - 1))
        lines.append(f'<line x1="{xx:.1f}" y1="{py1}" x2="{xx:.1f}" y2="{py1+ph}" class="grid"/>')
        lines.append(f'<text x="{xx:.1f}" y="{py1+ph+18}" text-anchor="middle" class="tick">{lv} MiB</text>')
        lines.append(f'<text x="{xx:.1f}" y="{py1+ph+33}" text-anchor="middle" class="tick" fill="#dc2626">({caff_occs[i]}%)</text>')

    lines.append(f'<text x="{px1 + pw/2}" y="{py1+ph+54}" text-anchor="middle" class="axis-label">'
                 'Retained Application Ballast (and Caffeine Post-GC Heap Occupancy)</text>')
    lines.append(f'<text x="{px1-50}" y="{py1+ph/2}" text-anchor="middle" transform="rotate(-90 {px1-50} {py1+ph/2})" class="axis-label">'
                 'Closed-Loop Service p99.9 (µs)</text>')

    for mode in ["CAFFEINE", "CHRONICLE_GET", "CHRONICLE_GET_USING"]:
        pts = []
        for i, lv in enumerate(lives):
            r = by_key(4096, lv, mode)
            val = r["closedLoopSvcP999Us"]
            xx = px1 + 35 + i * ((pw - 70) / (len(lives) - 1))
            yy = py1 + ph - (val / y_max) * ph
            pts.append((xx, yy, val))
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
        c = COLORS[mode]
        lines.append(f'<path d="{path_d}" fill="none" stroke="{c}" stroke-width="2.8"/>')
        for i, (x, y, val) in enumerate(pts):
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{c}"/>')
            if i == 0:
                dy = -9 if mode != "CAFFEINE" else 15
                lines.append(f'<text x="{x:.1f}" y="{y+dy:.1f}" text-anchor="middle" class="annot" fill="{c}">{val:.1f}µs</text>')
            elif i == 3:
                if mode == "CAFFEINE":
                    lines.append(f'<text x="{x:.1f}" y="{y+16:.1f}" text-anchor="middle" class="annot" fill="{c}">{val:.1f}µs</text>')
                elif mode == "CHRONICLE_GET":
                    lines.append(f'<text x="{x:.1f}" y="{y-10:.1f}" text-anchor="middle" class="annot" fill="{c}">{val:.1f}µs</text>')
                elif mode == "CHRONICLE_GET_USING":
                    lines.append(f'<text x="{x:.1f}" y="{y+15:.1f}" text-anchor="middle" class="annot" fill="{c}">{val:.1f}µs</text>')
            elif i == 4:
                if mode == "CAFFEINE":
                    lines.append(f'<text x="{x:.1f}" y="{y-10:.1f}" text-anchor="middle" class="annot" fill="{c}">{val:.1f}µs</text>')
                elif mode == "CHRONICLE_GET":
                    lines.append(f'<text x="{x-6:.1f}" y="{y-7:.1f}" text-anchor="end" class="annot" fill="{c}">{val:.1f}µs</text>')
                elif mode == "CHRONICLE_GET_USING":
                    lines.append(f'<text x="{x:.1f}" y="{y+16:.1f}" text-anchor="middle" class="annot" fill="{c}">{val:.1f}µs</text>')

    # Callout box placed at the bottom-left empty space of Panel A (around 2-5 us)
    lines.append(f'<rect x="{px1+18}" y="{py1+ph-76}" width="320" height="48" fill="#fff1f2" stroke="#fecdd3" rx="4"/>')
    lines.append(f'<text x="{px1+28}" y="{py1+ph-56}" class="annot" fill="#be123c">At 340 MiB (97.3% heap, 58 Full GCs, 808 ms paused):</text>')
    lines.append(f'<text x="{px1+28}" y="{py1+ph-38}" class="annot" fill="#be123c">Caffeine closed-loop p99.9 is still 8.4 µs (hides the cliff)!</text>')

    # Right panel: Open-loop response p99.9 (log10 scale: 5 us -> 80,000 us)
    px2, py2 = 640, 145
    lines.append(f'<rect x="{px2}" y="{py2}" width="{pw}" height="{ph}" fill="#fcfdff" stroke="#cbd5e1"/>')
    lines.append(f'<text x="{px2 + pw/2}" y="{py2 - 14}" text-anchor="middle" class="panel-title">'
                 'B. Open-Loop Response p99.9 (Log Scale, 50k QPS Schedule)</text>')

    log_min, log_max = math.log10(5.0), math.log10(80000.0)

    def y_log(val_us: float) -> float:
        lv = math.log10(max(5.0, min(80000.0, val_us)))
        return py2 + ph - ((lv - log_min) / (log_max - log_min)) * ph

    for yv, lbl in [(10, "10 µs"), (100, "100 µs"), (1000, "1 ms"), (10000, "10 ms"), (30000, "30 ms")]:
        yy = y_log(yv)
        lines.append(f'<line x1="{px2}" y1="{yy:.1f}" x2="{px2+pw}" y2="{yy:.1f}" class="grid"/>')
        lines.append(f'<text x="{px2-8}" y="{yy+4:.1f}" text-anchor="end" class="tick">{lbl}</text>')

    lines.append(f'<text x="{px2-54}" y="{py2+ph/2}" text-anchor="middle" transform="rotate(-90 {px2-54} {py2+ph/2})" class="axis-label">'
                 'Open-Loop Response p99.9 (Log Scale)</text>')

    # Shade cliff zone (340 - 352 MiB)
    x_cliff = px2 + 35 + 2.5 * ((pw - 70) / (len(lives) - 1))
    lines.append(f'<rect x="{x_cliff:.1f}" y="{py2}" width="{px2+pw-x_cliff:.1f}" height="{ph}" fill="#fef2f2" opacity="0.55"/>')
    lines.append(f'<text x="{px2+pw-8:.1f}" y="{py2+16}" text-anchor="end" class="annot" fill="#b91c1c">'
                 'G1 Full-GC Cliff (&gt;97% Heap)</text>')

    for i, lv in enumerate(lives):
        xx = px2 + 35 + i * ((pw - 70) / (len(lives) - 1))
        lines.append(f'<line x1="{xx:.1f}" y1="{py2}" x2="{xx:.1f}" y2="{py2+ph}" class="grid"/>')
        lines.append(f'<text x="{xx:.1f}" y="{py2+ph+18}" text-anchor="middle" class="tick">{lv} MiB</text>')
        lines.append(f'<text x="{xx:.1f}" y="{py2+ph+33}" text-anchor="middle" class="tick" fill="#dc2626">({caff_occs[i]}%)</text>')

    lines.append(f'<text x="{px2 + pw/2}" y="{py2+ph+54}" text-anchor="middle" class="axis-label">'
                 'Retained Application Ballast (and Caffeine Post-GC Heap Occupancy)</text>')

    for mode in ["CAFFEINE", "CHRONICLE_GET", "CHRONICLE_GET_USING"]:
        pts = []
        for i, lv in enumerate(lives):
            r = by_key(4096, lv, mode)
            val = r["openLoopRespP999Us"]
            xx = px2 + 35 + i * ((pw - 70) / (len(lives) - 1))
            yy = y_log(val)
            pts.append((xx, yy, val))
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
        c = COLORS[mode]
        lines.append(f'<path d="{path_d}" fill="none" stroke="{c}" stroke-width="2.8"/>')
        for i, (x, y, val) in enumerate(pts):
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{c}"/>')
            if mode == "CAFFEINE" and i in (0, 2, 3, 4):
                txt = f"{val/1000:.1f} ms" if val >= 1000 else f"{val:.0f} µs"
                dy = -10 if i != 4 else 16
                lines.append(f'<text x="{x:.1f}" y="{y+dy:.1f}" text-anchor="middle" class="annot" fill="{c}">{txt}</text>')
            elif mode == "CHRONICLE_GET" and i in (0, 4):
                lines.append(f'<text x="{x:.1f}" y="{y+16:.1f}" text-anchor="middle" class="annot" fill="{c}">{val:.0f} µs</text>')
            elif mode == "CHRONICLE_GET_USING" and i in (0, 3, 4):
                lines.append(f'<text x="{x:.1f}" y="{y-9:.1f}" text-anchor="middle" class="annot" fill="{c}">{val:.1f} µs</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def build_fig2_gc_and_allocation():
    w, h = 1140, 540
    lines = svg_header(w, h)
    lines.append('<text x="570" y="32" text-anchor="middle" class="title">'
                 '4 KiB Payloads: Total STW GC Pause Time, Full GC Count, and Per-Operation Allocation</text>')
    lines.append('<text x="570" y="52" text-anchor="middle" class="subtitle">'
                 'Why Chronicle getUsing() wins by 2,418x: it eliminates both Caffeine\'s 98% retained-heap cliff and Chronicle get()\'s 4.1 KiB/op read allocation</text>')
    draw_legend(lines, 110, 66)

    lives = [288, 312, 328, 340, 352]
    caff_occs = [by_key(4096, lv, "CAFFEINE")["steadyPostGcPct"] for lv in lives]

    # Left panel: Total GC pause time in 8s measured window (0 -> 2500 ms)
    px1, py1, pw, ph = 90, 145, 450, 310
    lines.append(f'<rect x="{px1}" y="{py1}" width="{pw}" height="{ph}" fill="#fcfdff" stroke="#cbd5e1"/>')
    lines.append(f'<text x="{px1 + pw/2}" y="{py1 - 14}" text-anchor="middle" class="panel-title">'
                 'A. Total Stop-The-World GC Pause Time (ms per 8s Window)</text>')

    y_max = 2500.0
    for yv in [0, 500, 1000, 1500, 2000, 2500]:
        yy = py1 + ph - (yv / y_max) * ph
        lines.append(f'<line x1="{px1}" y1="{yy:.1f}" x2="{px1+pw}" y2="{yy:.1f}" class="grid"/>')
        lines.append(f'<text x="{px1-8}" y="{yy+4:.1f}" text-anchor="end" class="tick">{yv} ms</text>')

    group_w = pw / len(lives)
    bar_w = 20
    modes = ["CAFFEINE", "CHRONICLE_GET", "CHRONICLE_GET_USING"]
    for i, lv in enumerate(lives):
        gx = px1 + i * group_w + group_w / 2
        lines.append(f'<text x="{gx:.1f}" y="{py1+ph+18}" text-anchor="middle" class="tick">{lv} MiB</text>')
        lines.append(f'<text x="{gx:.1f}" y="{py1+ph+33}" text-anchor="middle" class="tick" fill="#dc2626">({caff_occs[i]}%)</text>')
        for m_idx, mode in enumerate(modes):
            r = by_key(4096, lv, mode)
            gc_ms = r["gcTimeMs"]
            fulls = r["fullGcs"]
            bh = (gc_ms / y_max) * ph
            bx = gx + (m_idx - 1.5) * (bar_w + 3) + 1.5
            by = py1 + ph - bh
            c = COLORS[mode]
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w}" height="{max(2.0, bh):.1f}" fill="{c}" rx="2"/>')
            if mode == "CAFFEINE":
                lbl = f"{gc_ms}ms" + (f" ({fulls} Full)" if fulls >= 2 else "")
                lines.append(f'<text x="{bx+bar_w/2:.1f}" y="{by-6:.1f}" text-anchor="middle" class="annot" fill="{c}">{lbl}</text>')
            elif i in (0, 4):
                lines.append(f'<text x="{bx+bar_w/2:.1f}" y="{by-5:.1f}" text-anchor="middle" class="tick" fill="{c}">{gc_ms}</text>')

    lines.append(f'<text x="{px1 + pw/2}" y="{py1+ph+54}" text-anchor="middle" class="axis-label">'
                 'Retained Application Ballast (and Caffeine Post-GC Heap Occupancy)</text>')
    lines.append(f'<text x="{px1-62}" y="{py1+ph/2}" text-anchor="middle" transform="rotate(-90 {px1-62} {py1+ph/2})" class="axis-label">'
                 'Total GC Pause Time in 8s (ms)</text>')

    # Right panel: Worker Allocation Rate (B/op) & Post-GC Occupancy at 352 MiB
    px2, py2, pw2 = 635, 145, 435
    lines.append(f'<rect x="{px2}" y="{py2}" width="{pw2}" height="{ph}" fill="#fcfdff" stroke="#cbd5e1"/>')
    lines.append(f'<text x="{px2 + pw2/2}" y="{py2 - 14}" text-anchor="middle" class="panel-title">'
                 'B. Worker Heap Allocation per Operation (4 KiB Workload)</text>')

    alloc_max = 4600.0
    for yv in [0, 1000, 2000, 3000, 4000]:
        yy = py2 + ph - (yv / alloc_max) * ph
        lines.append(f'<line x1="{px2}" y1="{yy:.1f}" x2="{px2+pw2}" y2="{yy:.1f}" class="grid"/>')
        lines.append(f'<text x="{px2-8}" y="{yy+4:.1f}" text-anchor="end" class="tick">{yv} B/op</text>')

    short_names = ["Caffeine", "Chronicle get()", "Chronicle getUsing()"]
    notes = ["(5% writes only)", "(95% reads + 5% writes!)", "(5% writes only; 0 B/read)"]
    for idx, mode in enumerate(modes):
        r = by_key(4096, 352, mode)
        b_op = r["workerAllocBytesPerOp"]
        bh = (b_op / alloc_max) * ph
        bx = px2 + 52 + idx * 130
        by = py2 + ph - bh
        c = COLORS[mode]
        lines.append(f'<rect x="{bx}" y="{by:.1f}" width="70" height="{max(3.0, bh):.1f}" fill="{c}" rx="4"/>')
        lines.append(f'<text x="{bx+35}" y="{by-20:.1f}" text-anchor="middle" class="annot" fill="{c}">{b_op:.1f} B/op</text>')
        lines.append(f'<text x="{bx+35}" y="{by-6:.1f}" text-anchor="middle" class="tick" fill="#475569">{notes[idx]}</text>')
        lines.append(f'<text x="{bx+35}" y="{py2+ph+20}" text-anchor="middle" class="axis-label">{short_names[idx]}</text>')
        lines.append(f'<text x="{bx+35}" y="{py2+ph+36}" text-anchor="middle" class="tick">'
                     f'Heap @352M: {r["steadyPostGcPct"]}%</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def build_fig3_256b_cliff():
    w, h = 1140, 550
    lines = svg_header(w, h)
    lines.append('<text x="570" y="32" text-anchor="middle" class="title">'
                 '256 B Payloads (256 MiB G1 Heap): Reaching the Actual 82%–99% Cliff &amp; OOM Boundary</text>')
    lines.append('<text x="570" y="52" text-anchor="middle" class="subtitle">'
                 'In Task 12, 256 B never exceeded 62% heap. On a 256 MiB heap, Caffeine hits 529 Full GCs at 232 MiB and OOMs at 238 MiB while Chronicle survives</text>')
    draw_legend(lines, 110, 66)

    lives = [192, 220, 232, 238]
    caff_occs = ["82.4%", "93.0%", "98.4%", "99.2% (OOM)"]

    # Left panel: Open-loop p99.9 (log scale 1 us -> 50,000 us)
    px1, py1, pw, ph = 85, 145, 440, 315
    lines.append(f'<rect x="{px1}" y="{py1}" width="{pw}" height="{ph}" fill="#fcfdff" stroke="#cbd5e1"/>')
    lines.append(f'<text x="{px1 + pw/2}" y="{py1 - 14}" text-anchor="middle" class="panel-title">'
                 'A. 256 B Open-Loop Response p99.9 (Log Scale, 100k QPS)</text>')

    log_min, log_max = math.log10(1.0), math.log10(80000.0)

    def y_log(val_us: float) -> float:
        lv = math.log10(max(1.0, min(80000.0, val_us)))
        return py1 + ph - ((lv - log_min) / (log_max - log_min)) * ph

    for yv, lbl in [(1, "1 µs"), (10, "10 µs"), (100, "100 µs"), (1000, "1 ms"), (10000, "10 ms")]:
        yy = y_log(yv)
        lines.append(f'<line x1="{px1}" y1="{yy:.1f}" x2="{px1+pw}" y2="{yy:.1f}" class="grid"/>')
        lines.append(f'<text x="{px1-8}" y="{yy+4:.1f}" text-anchor="end" class="tick">{lbl}</text>')

    for i, lv in enumerate(lives):
        xx = px1 + 50 + i * ((pw - 100) / (len(lives) - 1))
        lines.append(f'<line x1="{xx:.1f}" y1="{py1}" x2="{xx:.1f}" y2="{py1+ph}" class="grid"/>')
        lines.append(f'<text x="{xx:.1f}" y="{py1+ph+18}" text-anchor="middle" class="tick">{lv} MiB</text>')
        lines.append(f'<text x="{xx:.1f}" y="{py1+ph+33}" text-anchor="middle" class="tick" fill="#dc2626">{caff_occs[i]}</text>')

    lines.append(f'<text x="{px1 + pw/2}" y="{py1+ph+54}" text-anchor="middle" class="axis-label">'
                 'Retained Application Ballast on 256 MiB Heap (and Caffeine Occupancy)</text>')

    for mode in ["CAFFEINE", "CHRONICLE_GET", "CHRONICLE_GET_USING"]:
        pts = []
        for i, lv in enumerate(lives):
            r = by_key(256, lv, mode)
            xx = px1 + 50 + i * ((pw - 100) / (len(lives) - 1))
            if r["status"] != "OK":
                lines.append(f'<rect x="{xx-56:.1f}" y="{py1+8}" width="112" height="20" fill="#fee2e2" stroke="#dc2626" rx="4"/>')
                lines.append(f'<text x="{xx:.1f}" y="{py1+22}" text-anchor="middle" class="annot" fill="#dc2626">✖ Caffeine OOM</text>')
                continue
            val = r["openLoopRespP999Us"]
            yy = y_log(val)
            pts.append((xx, yy, val, i))
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in pts)
        c = COLORS[mode]
        lines.append(f'<path d="{path_d}" fill="none" stroke="{c}" stroke-width="2.8"/>')
        for x, y, val, i in pts:
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{c}"/>')
            txt = f"{val/1000:.1f} ms" if val >= 1000 else f"{val:.2f} µs"
            if mode == "CAFFEINE":
                dy = -10
                dx = -4 if i == 2 else 0
                anchor = "end" if i == 2 else "middle"
            elif mode == "CHRONICLE_GET":
                dy = 16 if i == 2 else (-10 if i < 2 else 3)
                dx = -10 if i == 3 else 0
                anchor = "end" if i == 3 else "middle"
            else:  # CHRONICLE_GET_USING
                dy = 17
                dx = 0
                anchor = "middle"
            lines.append(f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" text-anchor="{anchor}" class="annot" fill="{c}">{txt}</text>')

    # Right panel: Total GC pause time in 6s window (0 -> 4200 ms)
    px2, py2, pw2 = 620, 145, 445
    lines.append(f'<rect x="{px2}" y="{py2}" width="{pw2}" height="{ph}" fill="#fcfdff" stroke="#cbd5e1"/>')
    lines.append(f'<text x="{px2 + pw2/2}" y="{py2 - 14}" text-anchor="middle" class="panel-title">'
                 'B. 256 B Total GC Pause Time (ms in 6s Window)</text>')

    y_max = 4200.0
    for yv in [0, 1000, 2000, 3000, 4000]:
        yy = py2 + ph - (yv / y_max) * ph
        lines.append(f'<line x1="{px2}" y1="{yy:.1f}" x2="{px2+pw2}" y2="{yy:.1f}" class="grid"/>')
        lines.append(f'<text x="{px2-8}" y="{yy+4:.1f}" text-anchor="end" class="tick">{yv} ms</text>')

    group_w = pw2 / len(lives)
    bar_w = 22
    modes = ["CAFFEINE", "CHRONICLE_GET", "CHRONICLE_GET_USING"]
    for i, lv in enumerate(lives):
        gx = px2 + i * group_w + group_w / 2
        lines.append(f'<text x="{gx:.1f}" y="{py2+ph+18}" text-anchor="middle" class="tick">{lv} MiB</text>')
        lines.append(f'<text x="{gx:.1f}" y="{py2+ph+33}" text-anchor="middle" class="tick" fill="#dc2626">{caff_occs[i]}</text>')
        for m_idx, mode in enumerate(modes):
            r = by_key(256, lv, mode)
            bx = gx + (m_idx - 1.5) * (bar_w + 4) + 2
            c = COLORS[mode]
            if r["status"] != "OK":
                lines.append(f'<rect x="{bx:.1f}" y="{py2+25}" width="{bar_w}" height="{ph-25}" fill="#fee2e2" stroke="#dc2626" stroke-dasharray="4,2"/>')
                lines.append(f'<text x="{bx+bar_w/2:.1f}" y="{py2+18}" text-anchor="middle" class="annot" fill="#dc2626">OOM</text>')
                continue
            gc_ms = r["gcTimeMs"]
            bh = (gc_ms / y_max) * ph
            by = py2 + ph - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w}" height="{max(2.0, bh):.1f}" fill="{c}" rx="2"/>')
            lines.append(f'<text x="{bx+bar_w/2:.1f}" y="{by-5:.1f}" text-anchor="middle" class="tick" fill="{c}">{gc_ms}</text>')

    lines.append(f'<text x="{px2 + pw2/2}" y="{py2+ph+54}" text-anchor="middle" class="axis-label">'
                 'Retained Application Ballast on 256 MiB Heap (and Caffeine Occupancy)</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def save_svg_and_png(name: str, svg_text: str):
    svg_path = FIG_DIR / f"{name}.svg"
    png_path = FIG_DIR / f"{name}.png"
    art_png = ARTIFACT_DIR / f"{name}.png"
    svg_path.write_text(svg_text)
    subprocess.run(["rsvg-convert", "-w", "2280", str(svg_path), "-o", str(png_path)], check=True)
    subprocess.run(["cp", str(png_path), str(art_png)], check=True)
    print(f"Generated {svg_path}, {png_path}, and {art_png}")


def main():
    save_svg_and_png("cliff_4kib_latency_crossover", build_fig1_4kib_latency())
    save_svg_and_png("cliff_4kib_gc_and_allocation", build_fig2_gc_and_allocation())
    save_svg_and_png("cliff_256b_crossover_and_oom", build_fig3_256b_cliff())


if __name__ == "__main__":
    main()
