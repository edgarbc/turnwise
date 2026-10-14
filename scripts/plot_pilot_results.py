"""Render a compact SVG summary for a Turnwise evaluation run."""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any


WIDTH = 1720
HEIGHT = 1040
INK = "#18333A"
MUTED = "#62767A"
PAPER = "#F4F7F5"
WHITE = "#FFFFFF"
GRID = "#DFE8E5"
JEV = "#147D73"
OPENAI = "#D45E4C"
ACCENT = "#D9A441"


def text(x: float, y: float, value: str, *, size: int = 16, fill: str = INK,
         weight: int = 400, family: str = "Arial, sans-serif",
         anchor: str = "start", tracking: float = 0) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" '
        f'font-size="{size}px" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}" letter-spacing="{tracking}px">'
        f'{html.escape(value)}</text>'
    )


def rect(x: float, y: float, width: float, height: float, fill: str,
         radius: int = 0) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
        f'height="{height:.1f}" rx="{radius}" fill="{fill}"/>'
    )


def line(x1: float, y1: float, x2: float, y2: float,
         color: str = GRID, width: float = 1) -> str:
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
        f'y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"/>'
    )


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def money(value: float) -> str:
    return f"${value:.4f}"


def render_chart(data: dict[str, Any]) -> str:
    providers = data["provider_order"]
    summaries = data["summary"]
    jev = summaries[providers[0]]
    openai = summaries[providers[1]]
    prefix_count = int(data["dataset"]["prefix_count"])
    case_count = len(data["dataset"]["cases"])
    created = data["created_at"][:10]
    run_id = data["run_id"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        'aria-labelledby="title description">',
        '<title id="title">Turnwise structured extraction pilot results</title>',
        '<desc id="description">Jev and OpenAI both scored 100 percent on accuracy, '
        'macro F1, and evidence validity over 35 synthetic transcript prefixes. '
        'Jev was faster and less costly. OpenAI had a slightly higher evidence-event match.</desc>',
        '<style>text{font-kerning:normal} .serif{font-family:Georgia,serif}</style>',
        rect(0, 0, WIDTH, HEIGHT, PAPER),
        # Header
        text(72, 58, "TURNWISE  /  MODEL EVALUATION", size=13, fill=JEV,
             weight=700, tracking=1.8),
        text(72, 119, "Core scores tie. Latency and cost diverge.", size=43,
             fill=INK, weight=700, family="Georgia, serif"),
        text(74, 158, "Structured extraction across a 30-conversation synthetic pilot",
             size=19, fill=MUTED),
        text(1648, 58, f"RUN DATE   {created}", size=12, fill=MUTED,
             weight=700, anchor="end", tracking=1.2),
        text(1648, 84, f"RUN   {run_id}", size=12, fill=MUTED,
             anchor="end"),
        # KPI strip
        rect(72, 193, 1576, 116, WHITE, 8),
        line(596, 215, 596, 287),
        line(1120, 215, 1120, 287),
        text(104, 238, str(prefix_count), size=36, fill=INK, weight=700,
             family="Georgia, serif"),
        text(104, 274, "ANNOTATED PREFIXES", size=12, fill=MUTED,
             weight=700, tracking=1.1),
        text(628, 238, str(case_count), size=36, fill=INK, weight=700,
             family="Georgia, serif"),
        text(628, 274, "SYNTHETIC CONVERSATIONS", size=12, fill=MUTED,
             weight=700, tracking=1.1),
        text(1152, 238, str(jev["provider_errors"] + openai["provider_errors"]),
             size=36, fill=JEV, weight=700, family="Georgia, serif"),
        text(1152, 274, "PROVIDER ERRORS", size=12, fill=MUTED,
             weight=700, tracking=1.1),
    ]

    # Quality panel
    qx, qy, qw, qh = 72, 337, 720, 525
    parts.extend([
        rect(qx, qy, qw, qh, WHITE, 8),
        text(qx + 30, qy + 45, "Quality", size=25, weight=700,
             family="Georgia, serif"),
        text(qx + 30, qy + 72, "All measures shown on a 0-100% scale",
             size=14, fill=MUTED),
        rect(qx + 452, qy + 31, 10, 10, JEV, 3),
        text(qx + 469, qy + 41, "Jev", size=13, fill=MUTED, weight=700),
        rect(qx + 535, qy + 31, 10, 10, OPENAI, 3),
        text(qx + 552, qy + 41, "OpenAI", size=13, fill=MUTED, weight=700),
    ])
    quality_rows = [
        ("Accuracy", "overall_accuracy"),
        ("Macro-F1", "overall_macro_f1"),
        ("Evidence validity", "evidence_validity"),
        ("Evidence-event match", "evidence_matches_gold_event"),
    ]
    bar_x = qx + 236
    bar_w = 340
    value_x = qx + 687
    for index, (label, metric) in enumerate(quality_rows):
        row_y = qy + 136 + index * 91
        first = float(jev[metric])
        second = float(openai[metric])
        parts.append(text(qx + 30, row_y + 8, label, size=15, fill=INK,
                          weight=600))
        for tick in (0.0, 0.5, 1.0):
            gx = bar_x + bar_w * tick
            parts.append(line(gx, row_y + 18, gx, row_y + 61, GRID))
        parts.extend([
            rect(bar_x, row_y + 19, bar_w, 12, "#EDF2F0", 6),
            rect(bar_x, row_y + 19, max(2, bar_w * first), 12, JEV, 6),
            rect(bar_x, row_y + 43, bar_w, 12, "#EDF2F0", 6),
            rect(bar_x, row_y + 43, max(2, bar_w * second), 12, OPENAI, 6),
            text(value_x, row_y + 30, pct(first), size=13, fill=JEV,
                 weight=700, anchor="end"),
            text(value_x, row_y + 54, pct(second), size=13, fill=OPENAI,
                 weight=700, anchor="end"),
        ])
    parts.extend([
        text(qx + 30, qy + qh - 24,
             "Same ceiling scores; event-level evidence match differs slightly.",
             size=13, fill=MUTED),
    ])

    # Latency panel
    lx, ly, lw, lh = 816, 337, 470, 525
    parts.extend([
        rect(lx, ly, lw, lh, WHITE, 8),
        text(lx + 28, ly + 45, "Latency", size=25, weight=700,
             family="Georgia, serif"),
        text(lx + 28, ly + 72, "Milliseconds per prefix", size=14, fill=MUTED),
        rect(lx + 274, ly + 31, 10, 10, JEV, 3),
        text(lx + 291, ly + 41, "Jev", size=13, fill=MUTED, weight=700),
        rect(lx + 354, ly + 31, 10, 10, OPENAI, 3),
        text(lx + 371, ly + 41, "OpenAI", size=13, fill=MUTED, weight=700),
    ])
    latency_x = lx + 94
    latency_w = 250
    latency_label_x = lx + 28
    latency_value_x = lx + 438
    for tick in (0, 2000, 4000):
        gx = latency_x + latency_w * tick / 4500
        parts.append(line(gx, ly + 112, gx, ly + 408, GRID))
    for index, (label, key) in enumerate((("p50", "p50"), ("p95", "p95"))):
        row_y = ly + 156 + index * 150
        parts.append(text(latency_label_x, row_y + 10, label, size=18,
                          weight=700, family="Georgia, serif"))
        for offset, (provider, summary, color) in enumerate((
            (providers[0], jev, JEV), (providers[1], openai, OPENAI),
        )):
            value = float(summary["latency_ms"][key])
            bar_y = row_y + 28 + offset * 34
            bar_width = latency_w * min(value, 4500) / 4500
            parts.extend([
                rect(latency_x, bar_y, latency_w, 15, "#EDF2F0", 7),
                rect(latency_x, bar_y, max(3, bar_width), 15, color, 7),
                text(latency_value_x, bar_y + 13, f"{value:,.0f}", size=13,
                     fill=color, weight=700, anchor="end"),
            ])
        parts.append(line(lx + 28, row_y + 112, lx + lw - 28,
                          row_y + 112, GRID))
    parts.extend([
        text(latency_x, ly + 461, "0", size=12, fill=MUTED, anchor="middle"),
        text(latency_x + latency_w * 2000 / 4500, ly + 461, "2k", size=12,
             fill=MUTED, anchor="middle"),
        text(latency_x + latency_w * 4000 / 4500, ly + 461, "4k", size=12,
             fill=MUTED, anchor="middle"),
        text(lx + 28, ly + lh - 24, "Lower is faster", size=13, fill=MUTED),
    ])

    # Cost panel, log-scaled so both providers remain legible.
    cx, cy, cw, ch = 1310, 337, 338, 525
    costs = [float(jev["estimated_cost"]["usd"]),
             float(openai["estimated_cost"]["usd"])]
    ratio = max(costs) / min(costs)
    scale_min, scale_max = 0.001, 0.1
    cost_bar_x = cx + 30
    cost_bar_w = 276
    parts.extend([
        rect(cx, cy, cw, ch, WHITE, 8),
        text(cx + 28, cy + 45, "Estimated cost", size=23, weight=700,
             family="Georgia, serif"),
        text(cx + 28, cy + 72, "Per full 35-prefix run  /  USD",
             size=13, fill=MUTED),
        text(cx + 28, cy + 123, "LOG SCALE", size=11, fill=MUTED,
             weight=700, tracking=1.2),
    ])
    for tick_value in (scale_min, 0.01, scale_max):
        fraction = math.log10(tick_value / scale_min) / math.log10(scale_max / scale_min)
        gx = cost_bar_x + cost_bar_w * fraction
        parts.extend([
            line(gx, cy + 158, gx, cy + 372, GRID),
            text(gx, cy + 393, f"${tick_value:g}", size=11, fill=MUTED,
                 anchor="middle"),
        ])
    for index, (provider, value, color) in enumerate((
        (providers[0], costs[0], JEV), (providers[1], costs[1], OPENAI),
    )):
        row_y = cy + 190 + index * 111
        fraction = math.log10(max(value, scale_min) / scale_min) / math.log10(
            scale_max / scale_min
        )
        width = max(3, cost_bar_w * min(fraction, 1.0))
        parts.extend([
            text(cx + 28, row_y, provider.title(), size=15, fill=INK,
                 weight=700),
            text(cx + cw - 28, row_y, money(value), size=14, fill=color,
                 weight=700, anchor="end"),
            rect(cost_bar_x, row_y + 18, cost_bar_w, 17, "#EDF2F0", 8),
            rect(cost_bar_x, row_y + 18, width, 17, color, 8),
        ])
    parts.extend([
        rect(cx + 28, cy + 420, cw - 56, 56, "#F2F6F3", 6),
        text(cx + 44, cy + 443, f"{ratio:.0f}x cost difference",
             size=17, fill=INK, weight=700, family="Georgia, serif"),
        text(cx + 44, cy + 463, "Jev lower on this run", size=12, fill=MUTED),
        text(cx + 28, cy + ch - 24, "Estimated; standard pricing", size=12,
             fill=MUTED),
    ])

    # Footer
    parts.extend([
        line(72, 900, 1648, 900, "#CBD8D4"),
        text(72, 932, "PILOT CONTEXT", size=11, fill=JEV, weight=700,
             tracking=1.4),
        text(72, 961,
             "Synthetic dataset; perfect scores are pilot observations, not a general performance claim.",
             size=15, fill=INK),
        text(1648, 961, "35 prefixes  /  6 fields  /  2 providers", size=13,
             fill=MUTED, anchor="end"),
        "</svg>",
    ])
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True,
                        help="Run directory containing evaluation.json")
    parser.add_argument("--output", type=Path, required=True,
                        help="Output SVG path")
    args = parser.parse_args()
    evaluation_path = args.run / "evaluation.json"
    data = json.loads(evaluation_path.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_chart(data), encoding="utf-8")
    print(f"Chart written to {args.output}")


if __name__ == "__main__":
    main()