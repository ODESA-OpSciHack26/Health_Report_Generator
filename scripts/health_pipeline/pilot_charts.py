"""Pilot figure generation with matplotlib (imported lazily, pilot path only).

Charts read saved analysis records. No analytical statistics are computed here.
"""
from __future__ import annotations

import io
import math
from datetime import datetime

from pilot_document import PilotDocumentError

INK = "#18343c"
MUTED = "#52656b"
GRID = "#dfe6e5"
TEAL = "#247c85"
RUST = "#b95d35"
ZERO = "#9fb0b2"
STEM = "#b7ced1"


def _pyplot():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import dates as mdates
    except ImportError as exc:  # explicit, no fallback to the R renderer
        raise PilotDocumentError(
            "the Python tabular renderer requires matplotlib; install the frozen pilot "
            "environment (requirements.pilot.lock.txt) or use --renderer r") from exc
    return plt, mdates


def _finish(fig, width, height):
    buf = io.BytesIO()
    fig.set_size_inches(width, height)
    fig.savefig(buf, format="png", dpi=180, facecolor="white", bbox_inches="tight")
    _pyplot()[0].close(fig)
    return buf.getvalue()


def _parse(value):
    return datetime.fromisoformat(str(value)[:19])


def _theme(ax):
    ax.set_facecolor("white")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def graphs(analysis: dict, technical: bool = False) -> list[dict]:
    plt, mdates = _pyplot()
    parameters = analysis["parameters"]
    measure = parameters.get("measure_label") or ""
    output = []
    rows = analysis.get("plot_rows") or []
    good = [row for row in rows if row.get("value") is not None and row.get("period")]
    if good:
        categories = []
        for row in good:
            if row["category"] not in categories:
                categories.append(row["category"])
        columns = min(3, len(categories))
        rows_n = math.ceil(len(categories) / columns)
        fig, axes = plt.subplots(rows_n, columns, squeeze=False, sharex=True)
        axes = axes.ravel()
        for index, category in enumerate(categories):
            ax = axes[index]
            _theme(ax)
            series = [row for row in good if row["category"] == category]
            for segment in sorted({row["segment"] for row in series}):
                part = [row for row in series if row["segment"] == segment
                        and str(row.get("line_allowed")).lower() == "true"]
                part.sort(key=lambda row: row["period"])
                if len(part) >= 2:
                    ax.plot([_parse(row["period"]) for row in part],
                            [float(row["value"]) for row in part],
                            color=TEAL, linewidth=0.9)
            ax.scatter([_parse(row["period"]) for row in series],
                       [float(row["value"]) for row in series],
                       color=RUST, s=14, zorder=3)
            ax.set_title(category, fontsize=10, color=INK)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
            for label in ax.get_xticklabels():
                label.set_fontsize(9)
        for ax in axes[len(categories):]:
            ax.set_visible(False)
        fig.suptitle("How have the supplied series developed?", fontsize=15,
                     color=INK, x=0.01, ha="left")
        fig.text(0.01, 0.005,
                 "Separate vertical scales. Gaps are not zero; lines do not bridge absent periods.",
                 fontsize=8.5, color=MUTED, ha="left")
        fig.supylabel(measure, fontsize=9, color=MUTED, x=0.01)
        fig.tight_layout(rect=(0.03, 0.03, 1, 0.95))
        output.append({"title": "Development over the supplied periods",
                       "note": ("Dots are observed values. Panels use separate vertical scales: "
                                "compare shape within a panel, not panel heights."),
                       "png": _finish(fig, 9, max(4.2, 2.15 * math.ceil(len(categories) / 3)))})
    else:
        valued = [row for row in rows if row.get("value") is not None]
        if valued:
            fig, ax = plt.subplots()
            _theme(ax)
            ax.scatter([row["source_row"] for row in valued],
                       [float(row["value"]) for row in valued], color=TEAL, s=16)
            ax.set_title("Observed values in source order", fontsize=14, color=INK, loc="left")
            ax.set_xlabel("Source data record", fontsize=9, color=MUTED)
            ax.set_ylabel(measure, fontsize=9, color=MUTED)
            fig.tight_layout()
            output.append({"title": "Supplied observations",
                           "note": "No observation dates or category totals have been invented.",
                           "png": _finish(fig, 9, 4.4)})
    comparisons = [row for row in analysis.get("comparisons") or []]
    chart_categories = analysis.get("chart_categories") or []
    comparisons = [row for row in comparisons if row.get("category") in chart_categories]
    latest = [row for row in comparisons if row.get("latest") is not None]
    if latest:
        latest.sort(key=lambda row: float(row["latest"]))
        fig, ax = plt.subplots()
        _theme(ax)
        ax.barh([row["category"] for row in latest],
                [float(row["latest"]) for row in latest], color=TEAL, height=0.67)
        ax.set_title(f"Observed values in {str(parameters.get('latest_period'))[:4]}",
                     fontsize=14, color=INK, loc="left")
        ax.set_xlabel(measure, fontsize=9, color=MUTED)
        ax.tick_params(axis="y", labelsize=9)
        fig.tight_layout()
        output.append({"title": "Latest selected period",
                       "note": ("Each bar is a separate observed category value. Categories are "
                                "not summed into a population burden."),
                       "png": _finish(fig, 9, max(4, 0.32 * len(latest) + 1.5))})
    relative = [row for row in comparisons if row.get("percent") is not None]
    if relative:
        relative.sort(key=lambda row: float(row["percent"]))
        fig, ax = plt.subplots()
        _theme(ax)
        ax.axvline(0, color=ZERO, linewidth=0.6)
        for index, row in enumerate(relative):
            ax.plot([0, float(row["percent"])], [index, index], color=STEM, linewidth=2)
        ax.scatter([float(row["percent"]) for row in relative],
                   range(len(relative)), color=RUST, s=30, zorder=3)
        ax.set_yticks(range(len(relative)), [row["category"] for row in relative])
        ax.set_title(f"{str(parameters.get('latest_period'))[:4]} versus "
                     f"{str(parameters.get('reference_period'))[:4]}",
                     fontsize=14, color=INK, loc="left")
        ax.set_xlabel("Change from the selected reference (%)", fontsize=9, color=MUTED)
        fig.tight_layout()
        output.append({"title": "Within-category change",
                       "note": ("One observation at each selected period. Percentage changes are "
                                "not statistical significance, severity or outbreak alerts."),
                       "png": _finish(fig, 9, max(4, 0.32 * len(relative) + 1.5))})
    histogram = [row for row in analysis.get("histogram") or []
                 if None not in (row.get("left"), row.get("right"), row.get("count"))]
    if technical and histogram:
        fig, ax = plt.subplots()
        _theme(ax)
        for row in histogram:
            ax.add_patch(plt.Rectangle((float(row["left"]), 0),
                                       float(row["right"]) - float(row["left"]),
                                       float(row["count"]), facecolor=TEAL,
                                       edgecolor="white", linewidth=0.8))
        ax.set_title("Distribution of supplied row values", fontsize=14, color=INK, loc="left")
        ax.set_xlabel(measure, fontsize=9, color=MUTED)
        ax.set_ylabel("Observations", fontsize=9, color=MUTED)
        fig.tight_layout()
        output.append({"title": "Distribution diagnostic",
                       "note": ("Unweighted row-value distribution across selected categories and "
                                "periods; not a distribution of individual health outcomes."),
                       "png": _finish(fig, 9, 4.5)})
    return output
