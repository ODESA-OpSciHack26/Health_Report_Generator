"""Pilot figure generation with matplotlib (imported lazily, pilot path only).

Charts read saved analysis records. No analytical statistics are computed here.
"""
from __future__ import annotations

import io
import math
import os
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

from pilot_document import PilotDocumentError

INK = "#18343c"
MUTED = "#52656b"
GRID = "#dfe6e5"
TEAL = "#247c85"
RUST = "#b95d35"
ZERO = "#9fb0b2"
STEM = "#b7ced1"
FONT_NAME = "NotoSansCJKsc-Regular.otf"
FONT_RELATIVE = Path("assets") / "fonts" / "noto-cjk" / FONT_NAME
FONT_IMAGE = Path("/opt/pilot/fonts") / FONT_NAME
PROJECT = Path(__file__).resolve().parents[2]


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
    return matplotlib, plt, mdates


def _font_path() -> Path:
    override = os.environ.get("HEALTH_REPORT_PILOT_FONT")
    if override:
        path = Path(override)
        if not path.is_file():
            raise PilotDocumentError(f"configured pilot font is missing: {path}")
        return path
    for path in (FONT_IMAGE, PROJECT / FONT_RELATIVE):
        if path.is_file():
            return path
    raise PilotDocumentError(
        "the packaged CJK chart font is missing; expected /opt/pilot/fonts/"
        f"{FONT_NAME} or {PROJECT / FONT_RELATIVE}")


def _font_context(matplotlib):
    from matplotlib import font_manager
    path = _font_path()
    font_manager.fontManager.addfont(str(path))
    family = font_manager.FontProperties(fname=str(path)).get_name()
    return matplotlib.rc_context({
        "font.family": [family, "DejaVu Sans"],
        "font.sans-serif": [family, "DejaVu Sans"],
        "axes.unicode_minus": True,
    })


def _finish(fig, width, height, *, tight=True):
    buf = io.BytesIO()
    fig.set_size_inches(width, height)
    # The narrow-viewport variant keeps its exact intrinsic width: a tight bbox
    # would grow or shrink the canvas and silently change the text-to-width ratio
    # that makes its labels readable at 390 px.
    fig.savefig(buf, format="png", dpi=180, facecolor="white",
                bbox_inches="tight" if tight else None)
    _pyplot()[1].close(fig)
    return buf.getvalue()


def _parse(value):
    return datetime.fromisoformat(str(value)[:19])


def _theme(ax, labelsize=10):
    ax.set_facecolor("white")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=labelsize)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


TITLE_WIDTH = 24
NARROW_TITLE_WIDTH = 18
MAX_YEAR_TICKS = 6
DESKTOP_WIDTH = 9.0
NARROW_WIDTH = 4.0


def _wrap_title(label: str, width: int = TITLE_WIDTH) -> list[str]:
    """Wrap a full category label without dropping, abbreviating or reordering characters."""
    lines = textwrap.wrap(str(label), width=width, break_long_words=True,
                          break_on_hyphens=True)
    return lines or [""]


def _year_ticks(dates: list[datetime], max_ticks: int = MAX_YEAR_TICKS) -> list[int]:
    years = sorted({value.year for value in dates})
    if not years:
        return []
    if len(years) <= max_ticks:
        return years
    step = max(1, math.ceil((years[-1] - years[0]) / max_ticks))
    selected = [year for year in years if (year - years[0]) % step == 0]
    return selected[:max_ticks]


def _trend_plan(analysis: dict, period: str | None = None, *,
                narrow: bool = False) -> dict:
    rows = analysis.get("plot_rows") or []
    good = [row for row in rows if row.get("value") is not None and row.get("period")]
    categories = []
    for row in good:
        if row["category"] not in categories:
            categories.append(row["category"])
    counts = {category: len({row["period"] for row in good
                             if row["category"] == category}) for category in categories}
    sparse = [category for category in categories if counts[category] < 2]
    all_sparse = bool(categories) and len(sparse) == len(categories)
    mixed = bool(sparse) and not all_sparse
    if all_sparse:
        title = "Observed values over the supplied periods"
        figure_title = "Observed values in the supplied periods"
        note = ("Dots are observed values. Each panel has fewer than two observed periods, so "
                "temporal development cannot be assessed; the panels show values only. Separate "
                "vertical scales: compare values within a panel, not panel heights. Gaps are not "
                "zero; lines do not bridge absent periods.")
    elif mixed:
        title = "How have the supplied series developed?"
        figure_title = "Development over the supplied periods"
        note = ("Dots are observed values. Panels with fewer than two observed periods cannot show "
                "temporal development; panels with two or more show observed change. Separate "
                "vertical scales: compare shape only within panels with enough observations, not "
                "panel heights. Gaps are not zero; lines do not bridge absent periods.")
    else:
        title = "How have the supplied series developed?"
        figure_title = "Development over the supplied periods"
        note = ("Dots are observed values. Panels use separate vertical scales: compare shape "
                "within a panel, not panel heights.")
    annual = period == "year" or (
        period is None and bool(good)
        and all(str(row["period"]).endswith("-01-01") for row in good))
    dates = [_parse(row["period"]) for row in good]
    columns = 1 if narrow else (min(3, len(categories)) or 1)
    rows_n = math.ceil(len(categories) / columns) if categories else 1
    wrapped = {category: _wrap_title(
        category, NARROW_TITLE_WIDTH if narrow else TITLE_WIDTH)
        for category in categories}
    max_lines = max((len(lines) for lines in wrapped.values()), default=1)
    panel_height = 2.6 if narrow else 2.15
    height = max(5.0 if narrow else 4.2,
                 panel_height * rows_n + 0.35 * max(0, max_lines - 1))
    return {"categories": categories, "counts": counts, "sparse": sparse,
            "all_sparse": all_sparse, "mixed": mixed, "title": title,
            "figure_title": figure_title, "note": note, "annual": annual,
            "tick_years": _year_ticks(dates) if annual else None,
            "wrapped": wrapped, "columns": columns, "rows": rows_n, "height": height}


def _narrow_margins(height, title_lines, foot_lines):
    """Vertical bands for the narrow trend grid.

    The bottom band must hold both the shared x tick labels and the in-image
    footnote; 0.32 in covers the labels and 0.20 in per footnote line, with
    0.13 as the minimum. The top band holds the wrapped figure title.
    """
    foot_reserve = 0.32 + 0.20 * len(foot_lines)
    title_reserve = 0.55 + 0.30 * len(title_lines)
    return (max(0.55, 1 - title_reserve / height),
            max(0.13, foot_reserve / height))


def graphs(analysis: dict, technical: bool = False, period: str | None = None) -> list[dict]:
    """Return each figure with a wide and a narrow-viewport PNG.

    The narrow image is a separate layout (one panel per row, larger type,
    exact 4-inch canvas) so a 390 px viewport selects readable chart text
    instead of a 20%-scaled desktop figure.
    """
    matplotlib, plt, mdates = _pyplot()
    with _font_context(matplotlib):
        wide = _graphs(analysis, technical, plt, mdates, period)
        narrow = _graphs(analysis, technical, plt, mdates, period, narrow=True)
        if len(wide) != len(narrow):
            raise PilotDocumentError("wide and narrow chart layouts disagree on figure count")
        for item, small in zip(wide, narrow):
            item["narrow_png"] = small["png"]
        return wide


def _histogram_bounds(histogram: list[dict]):
    """Axis bounds for valid bins; None when there is nothing to draw."""
    if not histogram:
        return None
    lefts = [float(row["left"]) for row in histogram]
    rights = [float(row["right"]) for row in histogram]
    counts = [float(row["count"]) for row in histogram]
    low, high = min(lefts), max(rights)
    if not (math.isfinite(low) and math.isfinite(high)):
        return None
    if high <= low:
        pad = max(abs(low) * 0.05, 0.5)
    else:
        pad = (high - low) * 0.02
    top = max(counts) if counts else 0.0
    return low - pad, high + pad, 0.0, max(1.0, top * 1.1)


def _graphs(analysis: dict, technical: bool, plt, mdates, period=None,
            *, narrow: bool = False) -> list[dict]:
    parameters = analysis["parameters"]
    measure = parameters.get("measure_label") or ""
    output = []
    rows = analysis.get("plot_rows") or []
    good = [row for row in rows if row.get("value") is not None and row.get("period")]
    width = NARROW_WIDTH if narrow else DESKTOP_WIDTH
    tick_size = 13 if narrow else 10
    if good:
        plan = _trend_plan(analysis, period, narrow=narrow)
        title_lines = _wrap_title(plan["title"], 32) if narrow else [plan["title"]]
        height = plan["height"] + 0.32 * (len(title_lines) - 1)
        categories = plan["categories"]
        columns = plan["columns"]
        rows_n = plan["rows"]
        fig, axes = plt.subplots(rows_n, columns, squeeze=False, sharex=True)
        axes = axes.ravel()
        for index, category in enumerate(categories):
            ax = axes[index]
            _theme(ax, tick_size)
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
            ax.set_title("\n".join(plan["wrapped"][category]),
                         fontsize=14 if narrow else 10, color=INK)
            row_index = index // columns
            ax.tick_params(axis="x", labelbottom=(row_index == rows_n - 1),
                           labelsize=12 if narrow else 8)
            if plan["annual"]:
                ax.set_xticks([datetime(year, 1, 1) for year in plan["tick_years"]])
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
            else:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        if plan["annual"]:
            all_dates = [_parse(row["period"]) for row in good]
            pad = (timedelta(days=180) if min(all_dates) == max(all_dates)
                   else timedelta(days=15))
            axes[0].set_xlim(min(all_dates) - pad, max(all_dates) + pad)
        for ax in axes[len(categories):]:
            ax.set_visible(False)
        footnote = ("Separate vertical scales. Gaps are not zero; lines do not "
                    "bridge absent periods.")
        foot_lines = _wrap_title(footnote, 48) if narrow else [footnote]
        fig.suptitle("\n".join(title_lines), fontsize=15, color=INK,
                     x=0.01, ha="left")
        fig.text(0.01, 0.008, "\n".join(foot_lines),
                 fontsize=12 if narrow else 8.5, color=MUTED, ha="left", va="bottom")
        fig.supylabel(measure, fontsize=12 if narrow else 9, color=MUTED, x=0.01)
        if narrow:
            # Explicit margins, not tight_layout: the narrow grid stacks panels
            # with multi-line titles and tight_layout cannot satisfy that grid.
            top, bottom = _narrow_margins(height, title_lines, foot_lines)
            fig.subplots_adjust(left=0.18, right=0.98, top=top, bottom=bottom,
                                hspace=1.0)
        else:
            fig.tight_layout(rect=(0.03, 0.03, 1, 0.93))
        output.append({"title": plan["figure_title"], "note": plan["note"],
                       "png": _finish(fig, width, height, tight=not narrow)})
    else:
        valued = [row for row in rows if row.get("value") is not None]
        if valued:
            fig, ax = plt.subplots()
            _theme(ax, tick_size)
            ax.scatter([row["source_row"] for row in valued],
                       [float(row["value"]) for row in valued], color=TEAL, s=16)
            title = "Observed values in source order"
            lines = _wrap_title(title, 26) if narrow else [title]
            ax.set_title("\n".join(lines), fontsize=18 if narrow else 14,
                         color=INK, loc="left")
            ax.set_xlabel("Source data record", fontsize=13 if narrow else 9, color=MUTED)
            ax.set_ylabel(measure, fontsize=13 if narrow else 9, color=MUTED)
            fig.tight_layout()
            output.append({"title": "Supplied observations",
                           "note": "No observation dates or category totals have been invented.",
                           "png": _finish(fig, width, 4.4 + 0.35 * (len(lines) - 1),
                                          tight=not narrow)})
    comparisons = [row for row in analysis.get("comparisons") or []]
    chart_categories = analysis.get("chart_categories") or []
    comparisons = [row for row in comparisons if row.get("category") in chart_categories]
    latest = [row for row in comparisons if row.get("latest") is not None]
    if latest:
        latest.sort(key=lambda row: float(row["latest"]))
        fig, ax = plt.subplots()
        _theme(ax, tick_size)
        ax.barh([row["category"] for row in latest],
                [float(row["latest"]) for row in latest], color=TEAL, height=0.67)
        title = f"Observed values in {str(parameters.get('latest_period'))[:4]}"
        lines = _wrap_title(title, 26) if narrow else [title]
        ax.set_title("\n".join(lines),
                     fontsize=18 if narrow else 14, color=INK, loc="left")
        ax.set_xlabel(measure, fontsize=13 if narrow else 9, color=MUTED)
        ax.tick_params(axis="y", labelsize=13 if narrow else 9)
        fig.tight_layout()
        output.append({"title": "Latest selected period",
                       "note": ("Each bar is a separate observed category value. Categories are "
                                "not summed into a single combined total."),
                       "png": _finish(fig, width,
                                      max(4, 0.32 * len(latest) + 1.5)
                                      + 0.35 * (len(lines) - 1),
                                      tight=not narrow)})
    relative = [row for row in comparisons if row.get("percent") is not None]
    if relative:
        relative.sort(key=lambda row: float(row["percent"]))
        fig, ax = plt.subplots()
        _theme(ax, tick_size)
        ax.axvline(0, color=ZERO, linewidth=0.6)
        for index, row in enumerate(relative):
            ax.plot([0, float(row["percent"])], [index, index], color=STEM, linewidth=2)
        ax.scatter([float(row["percent"]) for row in relative],
                   range(len(relative)), color=RUST, s=30, zorder=3)
        ax.set_yticks(range(len(relative)), [row["category"] for row in relative])
        title = (f"{str(parameters.get('latest_period'))[:4]} versus "
                 f"{str(parameters.get('reference_period'))[:4]}")
        lines = _wrap_title(title, 26) if narrow else [title]
        ax.set_title("\n".join(lines),
                     fontsize=18 if narrow else 14, color=INK, loc="left")
        ax.set_xlabel("Change from the selected reference (%)",
                      fontsize=13 if narrow else 9, color=MUTED)
        fig.tight_layout()
        output.append({"title": "Within-category change",
                       "note": ("One observation at each selected period. Percentage changes are "
                                "not statistical significance."),
                       "png": _finish(fig, width,
                                      max(4, 0.32 * len(relative) + 1.5)
                                      + 0.35 * (len(lines) - 1),
                                      tight=not narrow)})
    histogram = [row for row in analysis.get("histogram") or []
                 if None not in (row.get("left"), row.get("right"), row.get("count"))]
    if technical:
        if histogram:
            fig, ax = plt.subplots()
            _theme(ax, tick_size)
            for row in histogram:
                ax.add_patch(plt.Rectangle((float(row["left"]), 0),
                                           float(row["right"]) - float(row["left"]),
                                           float(row["count"]), facecolor=TEAL,
                                           edgecolor="white", linewidth=0.8))
            bounds = _histogram_bounds(histogram)
            if bounds is not None:
                ax.set_xlim(bounds[0], bounds[1])
                ax.set_ylim(bounds[2], bounds[3])
            title = "Distribution of supplied row values"
            lines = _wrap_title(title, 26) if narrow else [title]
            ax.set_title("\n".join(lines),
                         fontsize=18 if narrow else 14, color=INK, loc="left")
            ax.set_xlabel(measure, fontsize=13 if narrow else 9, color=MUTED)
            ax.set_ylabel("Observations", fontsize=13 if narrow else 9, color=MUTED)
            fig.tight_layout()
            output.append({"title": "Distribution diagnostic",
                           "note": ("Unweighted row-value distribution across selected categories and "
                                    "periods; it describes only the supplied rows."),
                           "png": _finish(fig, width, 4.5 + 0.35 * (len(lines) - 1),
                                          tight=not narrow)})
        else:
            fig, ax = plt.subplots()
            ax.axis("off")
            title = "Distribution of supplied row values"
            lines = _wrap_title(title, 26) if narrow else [title]
            ax.set_title("\n".join(lines),
                         fontsize=18 if narrow else 14, color=INK, loc="left")
            ax.text(0.5, 0.5, "No distribution is available\nfor the supplied rows.",
                    ha="center", va="center", fontsize=14 if narrow else 12, color=MUTED,
                    transform=ax.transAxes)
            fig.tight_layout()
            output.append({"title": "Distribution diagnostic",
                           "note": ("No populated row-value bins are available for this selection; "
                                    "no values have been invented."),
                           "png": _finish(fig, width, 3.2, tight=not narrow)})
    return output
