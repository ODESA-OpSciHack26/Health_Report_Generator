"""Deterministic row descriptives and explicit within-series comparisons."""
import json
import math
import statistics
from collections import Counter

import pandas as pd
import tabular_bundle as bundles

SCHEMA = "health-report/descriptive-analysis/1"


def normalize_report_options(options=None):
    defaults = {"title": "Supplied observations", "measure_label": "Observed value",
                "unit": "not specified", "geography_label": "not specified",
                "source_label": "Reader-supplied table", "reference_period": None,
                "latest_period": None, "max_categories": 24, "context_notes": []}
    if options is None:
        return defaults
    if not isinstance(options, dict) or set(options) - set(defaults):
        raise ValueError("Unknown descriptive report options.")
    result = {**defaults, **options}
    for key in ("title", "measure_label", "unit", "geography_label", "source_label"):
        if not isinstance(result[key], str) or not result[key].strip() or len(result[key]) > 500:
            raise ValueError("Report labels must be nonempty text up to 500 characters.")
    if type(result["max_categories"]) is not int or not 1 <= result["max_categories"] <= 48:
        raise ValueError("max_categories must be an integer from 1 to 48.")
    notes = result["context_notes"]
    if not isinstance(notes, list) or len(notes) > 8 or any(not isinstance(x, str) or len(x) > 1000 for x in notes):
        raise ValueError("Context notes must be a short list of text annotations.")
    reference, latest = result["reference_period"], result["latest_period"]
    if (reference is None) != (latest is None):
        raise ValueError("Reference and latest comparison periods must be supplied together.")
    if reference is not None:
        for key in ("reference_period", "latest_period"):
            if not isinstance(result[key], str):
                raise ValueError("Comparison periods must be date strings.")
            stamp = pd.Timestamp(result[key])
            if pd.isna(stamp) or stamp.tzinfo is not None:
                raise ValueError("Comparison periods must be valid timezone-naive dates.")
            result[key] = stamp.isoformat()
        if result["reference_period"] >= result["latest_period"]:
            raise ValueError("Reference must precede latest period.")
    return result


def _finite(value):
    if value is None:
        return None
    value = value.item() if hasattr(value, "item") else value
    return value if math.isfinite(value) else None


def _summary(values):
    values = [value for value in values if value is not None]
    result = {"n": len(values), "mean": None, "sd": None, "min": None,
              "q1": None, "median": None, "q3": None, "max": None}
    if not values:
        return result
    q = [values[0]] * 3 if len(values) == 1 else statistics.quantiles(values, n=4, method="inclusive")
    result.update(min=min(values), max=max(values), q1=q[0], median=q[1], q3=q[2])
    try:
        result["mean"] = _finite(statistics.mean(values))
        result["sd"] = _finite(statistics.stdev(values)) if len(values) > 1 else None
    except (OverflowError, ValueError):
        pass
    return {key: _finite(value) for key, value in result.items()}


def describe(prepared, report_options=None):
    options = normalize_report_options(report_options)
    original = json.loads(bundles._table_bytes(prepared.table))["rows"]
    categories = list(dict.fromkeys(row[0] for row in original))
    groups = {category: [] for category in categories}
    for index, (category, value, period) in enumerate(original, 1):
        groups[category].append({"source_row": index, "value": value, "period": period})
    periods = sorted({row[2] for row in original if row[2] is not None})
    reference, latest = options["reference_period"], options["latest_period"]
    if reference is not None and (reference not in periods or latest not in periods):
        raise ValueError("Comparison periods must exist in the supplied observations.")
    frequency = {"year": "YS", "month": "MS", "week": "W-MON", "day": "D"}.get(
        prepared.provenance["parameters"]["period"])
    calendar = []
    if periods and frequency:
        # Keep calendar diagnostics bounded, without pretending an unevaluated grid is complete.
        start, end = pd.Timestamp(periods[0]), pd.Timestamp(periods[-1])
        estimate = (end - start).days + 1
        if estimate <= 5000 or frequency == "YS":
            calendar = [date.isoformat() for date in pd.date_range(start, end, freq=frequency)]
    calendar_index = {period: index for index, period in enumerate(calendar)}
    absent = [period for period in calendar if period not in periods]
    stats, comparisons, plot_rows = [], [], []
    selected = categories[:options["max_categories"]]
    for group_index, category in enumerate(categories):
        rows = groups[category]
        label = category if category is not None else "[Missing category]"
        identity = f"g{group_index + 1}"
        summary = _summary([row["value"] for row in rows])
        dated = sorted({row["period"] for row in rows if row["period"] is not None})
        stats.append({"category": label, "category_id": identity, "category_is_missing": category is None,
                      "rows": len(rows), "missing_values": sum(row["value"] is None for row in rows),
                      "missing_dates": sum(row["period"] is None for row in rows) if frequency else None,
                      "periods": len(dated), "first_period": dated[0] if dated else None,
                      "last_period": dated[-1] if dated else None,
                      "source_rows": [row["source_row"] for row in rows], **summary})
        dated_counts = Counter(row["period"] for row in rows if row["period"] is not None)
        duplicate_periods = any(count > 1 for count in dated_counts.values())
        previous = None
        segment = 0
        for row in sorted(rows, key=lambda x: (x["period"] or "", x["source_row"])):
            if category not in selected:
                continue
            valid = row["value"] is not None and row["period"] is not None
            position = calendar_index.get(row["period"])
            if not valid or previous is None or position is None or position != previous + 1:
                segment += 1
            plot_rows.append({"category": label, "category_id": identity, **row,
                              "segment": f"{identity}-s{segment}",
                              "line_allowed": bool(valid and not duplicate_periods and calendar)})
            previous = position if valid else None
        if reference is not None:
            before = [row for row in rows if row["period"] == reference]
            after = [row for row in rows if row["period"] == latest]
            eligible = (len(before) == len(after) == 1
                        and before[0]["value"] is not None and after[0]["value"] is not None)
            baseline = before[0]["value"] if len(before) == 1 else None
            final = after[0]["value"] if len(after) == 1 else None
            difference = _finite(final - baseline) if eligible else None
            percent = _finite((final - baseline) / baseline * 100) if eligible and baseline > 0 else None
            comparisons.append({"category": label, "category_id": identity,
                "baseline": baseline, "latest": final, "difference": difference, "percent": percent,
                "eligible": eligible, "source_rows": [row["source_row"] for row in before + after],
                "note": ("Comparable single observations" if eligible and baseline > 0 else
                         "Percentage unavailable: non-positive baseline" if eligible else
                         "Comparison unavailable: missing or repeated category-period observations")})
    values = [row[1] for row in original if row[1] is not None]
    histogram = []
    if values:
        low, high = min(values), max(values)
        bins = min(12, max(1, math.ceil(math.sqrt(len(values)))))
        width = (high - low) / bins
        if low == high:
            histogram = [{"left": low - 0.5, "right": high + 0.5, "count": len(values)}]
        elif math.isfinite(width) and width > 0:
            counts = [0] * bins
            for value in values:
                counts[min(bins - 1, int((value - low) / width))] += 1
            histogram = [{"left": low + index * width, "right": low + (index + 1) * width,
                          "count": count} for index, count in enumerate(counts)]
    result = {"schema": SCHEMA, "parameters": options,
        "policy": {"scope": "unweighted summaries of non-missing row values within each category",
                   "quantiles": "inclusive linear interpolation", "sd": "sample standard deviation; ddof=1",
                   "measure_aggregation": "no sums or category-period pooling",
                   "comparison": "one observed value per category at each explicitly requested period",
                   "percent": "100*(latest-reference)/reference; unavailable if reference <= 0",
                   "calendar_gaps": "absent from supplied selection, not necessarily missing at source",
                   "chart_selection": "first categories in source order, up to max_categories",
                   "annotations": "caller-supplied labels; not independently authenticated"},
        "overview": {"rows": len(original), "categories": len(categories), "periods": len(periods),
                     "missing_values": sum(row[1] is None for row in original),
                     "missing_dates": sum(row[2] is None for row in original) if frequency else None},
        "periods": periods, "unrepresented_calendar_periods": absent,
        "calendar_diagnostics_evaluated": bool(calendar),
        "category_statistics": stats, "comparisons": comparisons,
        "plot_rows": plot_rows, "histogram": histogram,
        "chart_categories": [value if value is not None else "[Missing category]" for value in selected]}
    bundles._json_bytes(result)
    return result
