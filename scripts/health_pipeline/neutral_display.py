"""Neutral per-instance display settings: one small contract shared by every neutral block.

Scope: presentation only. Nothing here can change an analysed value; it chooses which already
analysed groups and periods are shown, which already computed statistics are printed, how they
are formatted, and how the block is laid out. Analytical scope (which rows the analysis covers)
is decided at confirmation and never by these settings.

The contract is deliberately per block: a block declares which capabilities it supports, and a
setting outside those capabilities is rejected rather than ignored.
"""
from __future__ import annotations

SCHEMA = "health-report/neutral-display/1"

# Statistics that already exist in the saved analysis, in display order.
STATISTIC_ORDER = ("n", "median", "middle50", "range", "missing", "q1q3", "minmax", "mean", "sd")
DEFAULT_STATISTICS = ("n", "median", "middle50", "range")

STATISTIC_LABELS = {
    "n": "Valid observations",
    "median": "Median",
    "middle50": "Middle 50%",
    "range": "Observed range",
    "missing": "Missing measure",
    "q1q3": "Q1 and Q3",
    "minmax": "Minimum and maximum",
    "mean": "Mean",
    "sd": "Sample SD",
}

LAYOUTS = ("table", "chart", "chart-and-table", "panels", "combined")
AXIS_MODES = ("auto", "every", "every_n")
PANEL_SCALES = ("shared", "independent")

# Block -> capabilities. Only these keys may appear in that block's display object.
CAPABILITIES = {
    "values-by-group": {"groups", "statistics", "layout", "precision"},
    "values-over-time": {"groups", "periods", "axis_labels", "layout", "precision", "height",
                         "columns", "panel_scale"},
    "coverage-over-time": {"groups", "periods"},
}

LAYOUTS_FOR = {
    "values-by-group": ("table", "chart", "chart-and-table"),
    "values-over-time": ("table", "chart", "chart-and-table", "panels", "combined"),
    "coverage-over-time": ("table",),
}

PRECISION_MAX_PLACES = 6


class DisplayError(ValueError):
    """A rejected display setting; the message is reader-facing."""


def defaults(block: str) -> dict:
    """The compact default used when a recipe omits display settings entirely.

    Only keys the block actually supports are present: the defaults must pass the same
    validation as a user-supplied object.
    """
    if block not in CAPABILITIES:
        return {}
    if block == "coverage-over-time":
        return {"schema": SCHEMA, "groups": None, "periods": {"mode": "all"}}
    if block == "values-by-group":
        return {"schema": SCHEMA, "groups": None,
                "statistics": list(DEFAULT_STATISTICS),
                "layout": "chart-and-table",
                "precision": {"mode": "decimal", "places": 1}}
    # values-over-time
    return {"schema": SCHEMA, "groups": None, "periods": {"mode": "all"},
            "axis_labels": {"mode": "auto"}, "layout": "chart-and-table",
            "precision": {"mode": "decimal", "places": 1},
            "height": 3.6, "columns": 2, "panel_scale": "shared"}


def _is_iso(value) -> bool:
    import re
    return isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?:T[\d:.]+)?", value) is not None


def validate(block: str, display) -> dict:
    """Validate and normalise one block's display settings.

    Unknown keys, unsupported capabilities and impossible combinations are rejected with a
    message the editor can show; nothing is silently dropped.
    """
    allowed = CAPABILITIES.get(block)
    if allowed is None:
        raise DisplayError(f"Block {block!r} has no display settings.")
    if not isinstance(display, dict):
        raise DisplayError("Display settings must be an object.")
    unknown = set(display) - (allowed | {"schema"})
    if unknown:
        raise DisplayError(f"Unsupported display settings for this block: {sorted(unknown)}")
    if "schema" in display and display["schema"] != SCHEMA:
        raise DisplayError(f"Unsupported display schema: {display['schema']!r}.")

    result: dict = {"schema": SCHEMA}

    if "groups" in allowed:
        groups = display.get("groups", None)
        if groups is not None:
            if not isinstance(groups, list) or not groups:
                raise DisplayError("Choose at least one group to show, or all groups.")
            if any(not isinstance(item, str) or not item for item in groups):
                raise DisplayError("Group names must be non-empty text.")
            if len(set(groups)) != len(groups):
                raise DisplayError("A group can only be shown once.")
            groups = list(groups)
        result["groups"] = groups

    if "periods" in allowed:
        periods = display.get("periods", {"mode": "all"})
        if not isinstance(periods, dict):
            raise DisplayError("Period settings must be an object.")
        mode = periods.get("mode")
        if mode == "all":
            result["periods"] = {"mode": "all"}
        elif mode == "range":
            if set(periods) != {"mode", "from", "to"}:
                raise DisplayError("A period range needs exactly from and to.")
            if not _is_iso(periods["from"]) or not _is_iso(periods["to"]):
                raise DisplayError("Period range bounds must be ISO dates.")
            if periods["from"] > periods["to"]:
                raise DisplayError("The period range starts after it ends.")
            result["periods"] = {"mode": "range", "from": periods["from"], "to": periods["to"]}
        elif mode == "list":
            if set(periods) != {"mode", "values"}:
                raise DisplayError("A period selection needs exactly mode and values.")
            values = periods["values"]
            if not isinstance(values, list) or not values:
                raise DisplayError("Choose at least one period to show.")
            if any(not _is_iso(item) for item in values):
                raise DisplayError("Selected periods must be ISO dates.")
            if len(set(values)) != len(values):
                raise DisplayError("A period can only be shown once.")
            result["periods"] = {"mode": "list", "values": list(values)}
        else:
            raise DisplayError("Period mode must be all, range or list.")

    if "axis_labels" in allowed:
        axis = display.get("axis_labels", {"mode": "auto"})
        if not isinstance(axis, dict):
            raise DisplayError("Axis-label settings must be an object.")
        mode = axis.get("mode")
        if mode not in AXIS_MODES:
            raise DisplayError(f"Axis-label mode must be one of {AXIS_MODES}.")
        if mode == "every_n":
            if set(axis) != {"mode", "n"}:
                raise DisplayError("Every-N labels need exactly mode and n.")
            number = axis["n"]
            if not isinstance(number, int) or not 2 <= number <= 20:
                raise DisplayError("Show a label every 2 to 20 periods.")
            result["axis_labels"] = {"mode": "every_n", "n": number}
        else:
            if set(axis) != {"mode"}:
                raise DisplayError("This axis-label mode takes no extra fields.")
            result["axis_labels"] = {"mode": mode}

    if "statistics" in allowed:
        statistics = display.get("statistics", list(DEFAULT_STATISTICS))
        if not isinstance(statistics, list) or any(
                item not in STATISTIC_ORDER for item in statistics):
            raise DisplayError("Unknown statistics column requested.")
        if len(set(statistics)) != len(statistics):
            raise DisplayError("A statistics column can only be shown once.")
        result["statistics"] = [item for item in STATISTIC_ORDER if item in statistics]

    if "layout" in allowed:
        layout = display.get("layout", "table")
        if layout not in LAYOUTS_FOR[block]:
            raise DisplayError(
                f"Layout {layout!r} is not available for this block "
                f"(supported: {', '.join(LAYOUTS_FOR[block])}).")
        result["layout"] = layout

    if "precision" in allowed:
        precision = display.get("precision", {"mode": "decimal", "places": 1})
        if not isinstance(precision, dict):
            raise DisplayError("Precision settings must be an object.")
        mode = precision.get("mode")
        if mode == "full":
            if set(precision) != {"mode"}:
                raise DisplayError("Full precision takes no extra fields.")
            result["precision"] = {"mode": "full"}
        elif mode == "decimal":
            if set(precision) != {"mode", "places"}:
                raise DisplayError("Decimal precision needs exactly mode and places.")
            places = precision["places"]
            if not isinstance(places, int) or not 0 <= places <= PRECISION_MAX_PLACES:
                raise DisplayError(f"Choose 0 to {PRECISION_MAX_PLACES} decimal places.")
            result["precision"] = {"mode": "decimal", "places": places}
        else:
            raise DisplayError("Precision mode must be decimal or full.")

    if "height" in allowed:
        height = display.get("height")
        if height is not None:
            if not isinstance(height, (int, float)) or not 2.0 <= float(height) <= 8.0:
                raise DisplayError("Chart height must be between 2 and 8 inches.")
            result["height"] = round(float(height), 2)

    if "columns" in allowed:
        columns = display.get("columns")
        if columns is not None:
            if not isinstance(columns, int) or not 1 <= columns <= 3:
                raise DisplayError("Panel columns must be 1, 2 or 3.")
            result["columns"] = columns

    if "panel_scale" in allowed:
        scale = display.get("panel_scale", "shared")
        if scale not in PANEL_SCALES:
            raise DisplayError(f"Panel scale must be one of {PANEL_SCALES}.")
        result["panel_scale"] = scale

    return result


def resolve(block: str, display) -> dict:
    """Effective settings: block defaults with the saved object applied on top.

    A partial saved object (older request or a single control changed) inherits the block's
    default for every key it omits, so the stored object is always complete and a future default
    change cannot reinterpret it.
    """
    if display is None:
        return defaults(block)
    if not isinstance(display, dict):
        raise DisplayError("Display settings must be an object.")
    merged = dict(defaults(block))
    merged.update(display)
    return validate(block, merged)


def group_labels(analysis: dict) -> list[tuple]:
    """(key, label) pairs for the analysed groups, in analysis order.

    A blank group is shown as "missing". If a real group is literally named "missing", the blank
    one is labelled "missing (blank group)" so the two stay distinguishable.
    """
    keys = [group.get("group") for group in analysis.get("groups") or []]
    collision = "missing" in [str(key) for key in keys if key is not None]
    labels = []
    for key in keys:
        if key is None:
            labels.append((None, "missing (blank group)" if collision else "missing"))
        else:
            labels.append((str(key), str(key)))
    return labels


def group_key_for(label: str, analysis: dict):
    for key, name in group_labels(analysis):
        if name == label:
            return key
    return None


def selection_problem(display: dict, analysis: dict) -> str | None:
    """Check a display selection against the saved analysis; None when it fits.

    Display selections may only choose from what was analysed. A group or period that the
    analysis does not contain is a stale editor, not something to render as empty.
    """
    if display.get("groups") is not None:
        known = {name for _key, name in group_labels(analysis)}
        missing = [name for name in display["groups"] if name not in known]
        if missing:
            return ("These groups are not in the saved analysis: "
                    + ", ".join(missing) + ". Update the analysis or the selection.")
    periods = display.get("periods") or {"mode": "all"}
    if periods["mode"] != "all":
        known_periods = {record["period"] for group in analysis.get("groups") or []
                         for record in group.get("periods") or []}
        if periods["mode"] == "list":
            missing = [item for item in periods["values"] if item not in known_periods]
            if missing:
                return ("These periods are not in the saved analysis: "
                        + ", ".join(missing) + ".")
        elif periods["mode"] == "range":
            if not any(periods["from"] <= item <= periods["to"] + "T23:59:59"
                       for item in known_periods):
                return "The chosen period range contains no analysed period."
    return None


def summary(display: dict, analysis: dict) -> str:
    """The effective-scope sentence the editor and the report both use."""
    total_groups = len(analysis.get("groups") or [])
    shown = display.get("groups")
    group_text = (f"Showing {len(shown)} of {total_groups} analysed groups."
                  if shown is not None else f"Showing all {total_groups} analysed groups.")
    periods = display.get("periods") or {"mode": "all"}
    total_periods = analysis.get("time", {}).get("period_count", 0)
    if periods["mode"] == "all" or not analysis.get("time", {}).get("has_time"):
        period_text = (f"Showing all {total_periods} analysed periods."
                       if analysis.get("time", {}).get("has_time") else "")
    elif periods["mode"] == "list":
        period_text = f"Showing {len(periods['values'])} of {total_periods} analysed periods."
    else:
        period_text = f"Showing a period window of {total_periods} analysed periods."
    return " ".join(part for part in (group_text, period_text) if part)
