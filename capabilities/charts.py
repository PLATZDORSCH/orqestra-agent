"""Chart generation — create business visualizations.

Generates charts using matplotlib and saves them as PNG files.
Supports common business chart types: bar, line, pie, horizontal bar,
stacked bar, and waterfall charts.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from core.capabilities import Capability

log = logging.getLogger(__name__)

_OUTPUT_DIR = Path(os.getcwd()) / "charts"


def _ensure_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        return None


def _apply_business_style(plt, fig, ax):
    """Clean, professional chart style."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.tick_params(colors="#666666", labelsize=9)
    ax.yaxis.label.set_color("#666666")
    ax.xaxis.label.set_color("#666666")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")


_PALETTE = ["#2563eb", "#16a34a", "#dc2626", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"]


def _handle_generate_chart(args: dict) -> str:
    plt = _ensure_matplotlib()
    if plt is None:
        return json.dumps({"error": "matplotlib not installed. Run: pip install matplotlib"})

    chart_type = args.get("chart_type", "bar")
    title = args.get("title", "Chart")
    labels = args.get("labels", [])
    values = args.get("values", [])
    series = args.get("series")
    x_label = args.get("x_label", "")
    y_label = args.get("y_label", "")
    filename = args.get("filename", "")

    if not labels or not values:
        return json.dumps({"error": "Both 'labels' and 'values' are required"})

    try:
        # constrained_layout avoids tight_layout warnings with rotated labels / legends;
        # savefig(..., bbox_inches="tight") still trims the PNG.
        fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
        _apply_business_style(plt, fig, ax)

        if chart_type == "bar":
            if series and isinstance(values[0], list):
                _draw_grouped_bar(ax, labels, values, series)
            else:
                colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]
                bars = ax.bar(labels, values, color=colors, width=0.6)
                for bar, val in zip(bars, values):
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                            f"{val:,.1f}" if isinstance(val, float) else str(val),
                            ha="center", va="bottom", fontsize=8, color="#666666")

        elif chart_type == "barh":
            colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]
            ax.barh(labels, values, color=colors, height=0.6)
            for i, val in enumerate(values):
                ax.text(val, i, f" {val:,.1f}" if isinstance(val, float) else f" {val}",
                        va="center", fontsize=8, color="#666666")

        elif chart_type == "line":
            if series and isinstance(values[0], list):
                for i, (s, vals) in enumerate(zip(series, values)):
                    ax.plot(labels, vals, marker="o", color=_PALETTE[i % len(_PALETTE)],
                            linewidth=2, markersize=5, label=s)
                ax.legend(frameon=False, fontsize=9)
            else:
                ax.plot(labels, values, marker="o", color=_PALETTE[0], linewidth=2, markersize=5)

        elif chart_type == "pie":
            colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]
            ax.pie(values, labels=labels, colors=colors, autopct="%1.1f%%",
                   startangle=90, textprops={"fontsize": 9})
            ax.set_aspect("equal")

        elif chart_type == "stacked_bar":
            if not series or not isinstance(values[0], list):
                return json.dumps({"error": "stacked_bar requires 'series' and values as list of lists"})
            _draw_stacked_bar(ax, labels, values, series)

        elif chart_type == "waterfall":
            _draw_waterfall(ax, labels, values)

        else:
            return json.dumps({"error": f"Unknown chart_type: {chart_type}. Use: bar, barh, line, pie, stacked_bar, waterfall"})

        ax.set_title(title, fontsize=14, fontweight="bold", color="#333333", pad=15)
        if x_label:
            ax.set_xlabel(x_label, fontsize=10)
        if y_label:
            ax.set_ylabel(y_label, fontsize=10)

        if chart_type != "pie" and labels:
            plt.xticks(rotation=45 if len(labels) > 6 else 0, ha="right" if len(labels) > 6 else "center")

        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not filename:
            sanitized = title.lower().replace(" ", "-")[:40]
            filename = f"{sanitized}.png"
        if not filename.endswith(".png"):
            filename += ".png"

        out_path = _OUTPUT_DIR / filename
        fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return json.dumps({
            "success": True,
            "path": str(out_path),
            "filename": filename,
            "chart_type": chart_type,
        })

    except Exception as exc:
        plt.close("all")
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


def _draw_grouped_bar(ax, labels, values_lists, series):
    import numpy as np
    x = np.arange(len(labels))
    n = len(series)
    width = 0.8 / n
    for i, (s, vals) in enumerate(zip(series, values_lists)):
        offset = (i - n / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=s, color=_PALETTE[i % len(_PALETTE)])
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(frameon=False, fontsize=9)


def _draw_stacked_bar(ax, labels, values_lists, series):
    import numpy as np
    x = np.arange(len(labels))
    bottom = np.zeros(len(labels))
    for i, (s, vals) in enumerate(zip(series, values_lists)):
        ax.bar(x, vals, 0.6, bottom=bottom, label=s, color=_PALETTE[i % len(_PALETTE)])
        bottom += np.array(vals)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(frameon=False, fontsize=9)


def _draw_waterfall(ax, labels, values):
    cumulative = 0
    starts = []
    colors = []
    for v in values:
        starts.append(cumulative if v >= 0 else cumulative + v)
        cumulative += v
        colors.append("#16a34a" if v >= 0 else "#dc2626")
    colors[-1] = _PALETTE[0]
    starts[-1] = 0

    ax.bar(labels, [abs(v) for v in values], bottom=starts, color=colors, width=0.6)
    for i, (v, s) in enumerate(zip(values, starts)):
        y_pos = s + abs(v) if v >= 0 else s
        ax.text(i, y_pos, f"{v:+,.0f}" if i < len(values) - 1 else f"{values[-1]:,.0f}",
                ha="center", va="bottom", fontsize=8, color="#666666")


generate_chart = Capability(
    name="generate_chart",
    description=(
        "Generate a business chart and save it as a PNG file. "
        "Supported types: bar, barh (horizontal), line, pie, stacked_bar, waterfall. "
        "For grouped/stacked charts, pass multiple value lists in 'values' and series names in 'series'. "
        "Charts are saved to the ./charts/ directory."
    ),
    parameters={
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "enum": ["bar", "barh", "line", "pie", "stacked_bar", "waterfall"],
                "description": "Type of chart to generate",
            },
            "title": {"type": "string", "description": "Chart title"},
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Category labels (x-axis for bar/line, segments for pie)",
            },
            "values": {
                "description": "Data values. Single list for simple charts, list of lists for grouped/stacked",
            },
            "series": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Series names (for grouped bar, stacked bar, multi-line charts)",
            },
            "x_label": {"type": "string", "description": "X-axis label"},
            "y_label": {"type": "string", "description": "Y-axis label"},
            "filename": {"type": "string", "description": "Output filename (default: derived from title)"},
        },
        "required": ["title", "labels", "values"],
    },
    handler=_handle_generate_chart,
)
