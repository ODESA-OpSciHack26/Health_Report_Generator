"""Neutral "Your CSV" data layer: bounded capture, confirmed interpretation, prepared rows.

This module is deliberately independent of the health IDD machinery: it accepts a generic
UTF-8 CSV/TSV table, maps one category column, one numeric measure column and an optional
time column to a saved interpretation, prepares serialized rows with stable record identity,
and describes observed values without pooling or scientific inference. Nothing here
classifies a CSV as IDD or disease data; user-supplied labels are escaped and attributed,
never interpreted.

Slice B scope (see docs/build/composer/ROUND-CSV-PLAN.md): one group column, one measure,
optional time. Explicit ungrouped/count modes, multiple measures, grouping candidates,
declared missing tokens and actual filter predicates are Slice C and are rejected here with
clear messages rather than silently accepted.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_complex_dtype,
    is_numeric_dtype,
)

NEUTRAL_ANALYSIS_SCHEMA = "health-report/neutral-analysis/1"
NEUTRAL_INTERPRETATION_SCHEMA = "health-report/neutral-interpretation/1"
NEUTRAL_PREPARED_SCHEMA = "health-report/neutral-prepared/1"

# Centralised resource ceilings (configuration defaults, not performance claims). The same
# values are enforced by the site capture endpoint and by this module.
LIMITS = {
    "max_upload_bytes": 20 * 1024 * 1024,        # 20 MiB
    "max_records": 100_000,                       # nonblank logical records
    "max_columns": 100,
    "max_cells": 5_000_000,
    "max_field_bytes": 64 * 1024,                 # 64 KiB per decoded field
    "preview_rows": 100,
    "preview_columns": 20,
}

TIME_PERIODS = ("year", "month", "week", "day")
UNKNOWN = "not specified"

# Bumped only when a change alters analysed numbers or their meaning. Stored analyses written
# under an older version are refused for reuse instead of being relabelled as current.
CALC_VERSION = 2
CALC_DEFINITIONS = ("descriptive only: inclusive quartiles and sample standard deviation over "
                    "non-missing observed values; repeated group-period records stay separate; "
                    "a missing period is not a repeat")

# Explicit ISO calendar dates only: YYYY-MM-DD, optionally with a time part. Anything looser
# (bare numbers, "01/02/2021", "001") is not accepted as a period.
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$")


class NeutralError(ValueError):
    """A rejected capture, interpretation or preparation; message is reader-facing."""


@dataclass(frozen=True)
class Capture:
    """Captured immutable bytes plus structural inspection of that exact byte string.

    ``source_filename`` is display text only; identity is the content digest. The bytes
    inspected below are the bytes the caller captured; a later file read is never used.
    """
    source_filename: str
    input_sha256: str
    byte_count: int
    delimiter: str
    columns: tuple[str, ...]
    header: tuple[str, ...]
    logical_records: int
    preview_rows: list[list[str]]
    truncated_preview: bool

    def as_public(self, limit=None):
        columns = self.header[: limit or LIMITS["preview_columns"]]
        preview = [row[: limit or LIMITS["preview_columns"]]
                   for row in self.preview_rows[: LIMITS["preview_rows"]]]
        return {
            "source_filename": self.source_filename,
            "input_sha256": self.input_sha256,
            "byte_count": self.byte_count,
            "delimiter": self.delimiter,
            "columns": list(self.columns),
            "preview_columns": list(columns),
            "logical_records": self.logical_records,
            "preview_rows": preview,
            "preview_truncated_rows": max(0, self.logical_records - LIMITS["preview_rows"]),
            "preview_truncated_columns": max(0, len(self.header) - LIMITS["preview_columns"]),
            "limits_family": "csv-slice-b",
        }


_COLUMN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\- ]{0,119}$")


def validate_column_name(name):
    if not isinstance(name, str) or not _COLUMN_ID.fullmatch(name):
        raise NeutralError("Column names must be short text without control characters.")
    return name


def capture_payload(payload: bytes, *, source_filename: str,
                    limits: dict | None = None) -> Capture:
    """Inspect one bounded CSV/TSV payload without ever reopening a source file.

    Raises NeutralError for unsupported encodings, malformed quoting, empty/duplicate
    headers, inconsistent field widths and payloads beyond the configured ceilings.
    Missingness and invalid cells are NOT decided here; they are an interpretation concern.
    """
    limits = {**LIMITS, **(limits or {})}
    if not isinstance(payload, bytes):
        raise NeutralError("Captured input must be bytes.")
    if len(payload) > limits["max_upload_bytes"]:
        raise NeutralError(
            f"File is {len(payload)} bytes; the supported limit is "
            f"{limits['max_upload_bytes']} bytes.")
    name = Path(source_filename).name
    suffix = Path(name).suffix.lower()
    if suffix not in (".csv", ".tsv"):
        raise NeutralError("Supported files are .csv and .tsv (comma or tab separated).")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NeutralError("The file must be UTF-8 encoded.") from exc
    if "\x00" in text:
        raise NeutralError("The file contains NUL bytes; a text table is expected.")
    delimiter = "\t" if suffix == ".tsv" else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        header = next(reader, None)
        if not header or any(not cell.strip() for cell in header):
            raise NeutralError("The first row must be a header with non-empty column names.")
        columns = [cell.strip() for cell in header]
        if len(columns) > limits["max_columns"]:
            raise NeutralError(f"The table has {len(columns)} columns; the supported limit "
                               f"is {limits['max_columns']}.")
        if len(set(columns)) != len(columns):
            raise NeutralError("Duplicate column headers are not allowed.")
        records = []
        cells = 0
        for row in reader:
            if not row:
                continue                      # blank records are ignored, as in the tabular route
            if len(row) != len(columns):
                raise NeutralError(
                    f"Record ending at line {reader.line_num} has {len(row)} fields; "
                    f"expected {len(columns)}.")
            cells += len(row)
            if cells > limits["max_cells"]:
                raise NeutralError(
                    f"The table exceeds {limits['max_cells']} cells; reduce its size.")
            for cell in row:
                if len(cell.encode("utf-8")) > limits["max_field_bytes"]:
                    raise NeutralError("A single field exceeds the 64 KiB size limit.")
            records.append(list(row))
            if len(records) > limits["max_records"]:
                raise NeutralError(
                    f"The table has more than {limits['max_records']} nonblank records; "
                    "the supported limit is 100,000.")
    except csv.Error as exc:
        raise NeutralError("Malformed CSV/TSV quoting; check delimiters and quotes.") from exc
    if not records:
        raise NeutralError("The table contains no data records.")
    return Capture(
        source_filename=name,
        input_sha256=hashlib.sha256(payload).hexdigest(),
        byte_count=len(payload),
        delimiter=delimiter,
        columns=tuple(columns),
        header=tuple(header),
        logical_records=len(records),
        preview_rows=records[: limits["preview_rows"]],
        truncated_preview=len(records) > limits["preview_rows"],
    )


def _parse_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _looks_like_identifier(name, values, row_count):
    """A numeric column that is an identifier: dense 1..n, or a name like id/record/row."""
    if not values:
        return False
    if re.search(r"(^|[_\- ])(id|ids|record|record_id|row|row_id|index|no|nr)$",
                 name.strip().lower()):
        return True
    if len(values) != row_count or len(set(values)) != row_count:
        return False
    try:
        numbers = sorted(int(value) for value in values)
    except (TypeError, ValueError):
        return False
    return numbers == list(range(1, row_count + 1)) or numbers == list(range(0, row_count))


def suggest_interpretation(capture: Capture) -> dict:
    """Conservative role suggestions from structure only; never confirmed by suggesting.

    The measure is the numeric column with the fewest missing cells (ties: first in file
    order). The group is the first text column with at least 2 and at most 200 distinct
    values. Time is the first column whose values all parse under the supported periods
    (whole-year numerics or ISO dates). Suggestions may legitimately answer None; the
    confirmation card always states what one row represents explicitly, including the
    "not specified" default.
    """
    rows = capture.preview_rows
    n = len(rows)
    if not n:
        return {"category": None, "measure": None, "time": None, "note": "empty"}
    header = list(capture.columns)
    col_i = {name: idx for idx, name in enumerate(header)}
    stats: dict[str, dict] = {}
    for name in header:
        idx = col_i[name]
        values = [row[idx] if idx < len(row) else "" for row in rows]
        nonblank = [v for v in values if v.strip()]
        numeric = True
        for v in nonblank:
            if _parse_number(v) is None:
                numeric = False
                break
        stats[name] = {"nonblank": len(nonblank), "distinct": len(set(nonblank)),
                       "numeric": numeric,
                       "id_like": _looks_like_identifier(name, nonblank, n)}
    # measure: the first numeric, non-identifier column in file order (the documented
    # tie-break is conservative and stable; a period column is not a measurement).
    numeric_cols = [name for name in header if stats[name]["numeric"]
                    and not stats[name]["id_like"]]
    measure = None
    if numeric_cols:
        measure = min(numeric_cols, key=lambda name: col_i[name])
    # group: text (non-numeric) columns with 2..200 distinct values, first in order
    text_cols = [name for name in header
                 if not stats[name]["numeric"] and 2 <= stats[name]["distinct"] <= 200]
    category = text_cols[0] if text_cols else None
    # time: the first non-role, non-identifier column whose preview values all parse to a
    # supported period
    time = None
    for name in header:
        if name in {category, measure} or stats[name]["id_like"]:
            continue
        idx = col_i[name]
        values = [row[idx] if idx < len(row) else "" for row in rows]
        nonblank = [v for v in values if v.strip()]
        if nonblank and all(_parse_period_value(v) is not None for v in nonblank):
            time = name
            break
    return {"category": category, "measure": measure, "time": time}


def _parse_period_value(value):
    """One value -> (period, stamp-iso) or None. Whole years and explicit ISO dates only.

    Loose date parsing is deliberately refused: an identifier such as "001" or "01" must never
    become an observation date, so only a 4-digit year (1000-9999, written as such) or an
    explicit ISO calendar date is accepted.
    """
    value = value.strip()
    if not value:
        return None
    try:
        numeric = int(value)
        if str(numeric) != value:
            return None
        if 1000 <= numeric <= 9999:
            stamp = pd.Timestamp(year=numeric, month=1, day=1)
            return ("year", stamp)
        return None
    except (TypeError, ValueError):
        pass
    if not _ISO_DATE.fullmatch(value):
        return None
    try:
        stamp = pd.to_datetime(value, errors="raise")
    except (TypeError, ValueError):
        return None
    if pd.isna(stamp):
        return None
    if stamp.tzinfo is not None:
        return None
    if stamp.normalize() == stamp:
        return ("day", stamp.normalize())
    return ("day", stamp)


def prepare_payload_under(capture: Capture, payload: bytes, interpretation: dict, *,
                          limits: dict | None = None) -> dict:
    """Prepare rows from the exact payload that produced ``capture`` (never a re-read).

    One row per nonblank logical record, retaining source record identity (1-based ordinal
    within the captured table), raw source strings verbatim, the measure as float-or-null,
    the group as text-or-null and the period as ISO date-or-null. Invalid nonmissing
    conversions raise NeutralError so confirmation is blocked until the user corrects them
    or explicitly maps them as missing tokens. Blank cells and confirmed exact missing
    tokens become null; literal "NA"/"null" text is data unless declared missing.
    """
    limits = {**LIMITS, **(limits or {})}
    interpretation = dict(interpretation)
    category = validate_column_name(interpretation.get("category") or "")
    measure = validate_column_name(interpretation.get("measure") or "")
    time_col = interpretation.get("time") or None
    if time_col is not None:
        time_col = validate_column_name(time_col)
    columns = list(capture.columns)
    for name in (category, measure, *([time_col] if time_col else [])):
        if name not in columns:
            raise NeutralError(f"Column {name!r} does not exist in the captured table.")
    missing_tokens = interpretation.get("missing_tokens") or []
    if not isinstance(missing_tokens, list) or any(
            not isinstance(token, str) or not token.strip() for token in missing_tokens):
        raise NeutralError("Missing tokens must be a list of nonempty exact strings.")
    if len(missing_tokens) != len(set(missing_tokens)):
        raise NeutralError("Missing tokens must not repeat.")

    text = payload.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=capture.delimiter, strict=True)
    header = next(reader)
    columns = [column.strip() for column in header]
    index = {name: i for i, name in enumerate(columns)}
    rows: list[dict] = []
    for ordinal, row in enumerate(reader, start=1):
        if not row:
            continue
        raw = list(row)
        def cell(name):
            i = index[name]
            return raw[i] if i < len(raw) else ""
        cat_raw, val_raw = cell(category), cell(measure)
        per_raw = cell(time_col) if time_col else ""
        def is_missing(value):
            return (not value.strip()) or value in missing_tokens
        cat = None if is_missing(cat_raw) else cat_raw
        value = None
        if not is_missing(val_raw):
            try:
                value = float(val_raw)
            except (TypeError, ValueError):
                raise NeutralError(
                    f"Record {ordinal} has a measure value that is not a number "
                    f"({val_raw!r}). Confirm it as a declared missing token or fix the value.")
            if not math.isfinite(value):
                raise NeutralError(
                    f"Record {ordinal} has a non-finite measure value ({val_raw!r}).")
        period = None
        if time_col and per_raw.strip() and not is_missing(per_raw):
            parsed = _parse_period_value(per_raw)
            if parsed is None:
                raise NeutralError(
                    f"Record {ordinal} has a time value that cannot be read under the "
                    f"supported periods ({per_raw!r}).")
            period = parsed[1].isoformat()
        rows.append({"ordinal": ordinal, "raw": raw,
                     "category": cat, "value": value, "period": period})
    if len(rows) > limits["max_records"]:
        raise NeutralError("Prepared records exceed the supported limit.")
    return {
        "schema": NEUTRAL_PREPARED_SCHEMA,
        "source": {"filename": capture.source_filename,
                   "input_sha256": capture.input_sha256,
                   "delimiter": capture.delimiter, "columns": columns},
        "interpretation": {"category": category, "measure": measure,
                           "time": time_col, "missing_tokens": missing_tokens},
        "rows": rows, "row_count": len(rows),
    }


# ---------------------------------------------------------------- description

def _finite(value):
    if value is None:
        return None
    try:
        value = value.item() if hasattr(value, "item") else value
    except AttributeError:
        pass
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value if value == value and math.isfinite(value) else None
    return None


def _summary(values):
    values = [value for value in values if value is not None]
    result = {"n": len(values), "mean": None, "sd": None, "min": None,
              "q1": None, "median": None, "q3": None, "max": None}
    if not values:
        return result
    try:
        q = [values[0]] * 3 if len(values) == 1 else statistics.quantiles(
            values, n=4, method="inclusive")
    except statistics.StatisticsError:
        q = [values[0]] * 3
    result.update(min=min(values), max=max(values), q1=q[0], median=q[1], q3=q[2])
    try:
        result["mean"] = _finite(statistics.mean(values))
        result["sd"] = _finite(statistics.stdev(values)) if len(values) > 1 else None
    except (OverflowError, statistics.StatisticsError):
        pass
    return {key: _finite(value) for key, value in result.items()}


def describe(rows: list[dict], interpretation: dict, *, dataset: dict | None = None) -> dict:
    """Deterministic descriptive descriptor over prepared rows; no pooling, no inference.

    Methods are explicit and reused from the tabular route: inclusive quartiles and sample
    SD are calculated exactly as in tabular_describe. Repeated group-period pairs are
    preserved as separate observations (never summed, averaged or thinned).
    """
    category = interpretation.get("category")
    measure = interpretation.get("measure")
    time_col = interpretation.get("time")
    values = [row["value"] for row in rows]
    group_order: list = []
    per_group: dict = {}
    for row in rows:
        key = row["category"]
        if key not in per_group:
            per_group[key] = []
            group_order.append(key)
        per_group[key].append(row)
    groups = []
    for key in group_order:
        group_rows = per_group[key]
        member_values = [row["value"] for row in group_rows]
        periods = sorted({row["period"] for row in group_rows if row["period"]})
        # Every record keeps its own period entry: a repeated group-period key must stay
        # visible as separate observations, never thinned to the first value.
        pair_counts: dict = {}
        for row in group_rows:
            if row["period"]:
                pair_counts[row["period"]] = pair_counts.get(row["period"], 0) + 1
        period_records = [
            {"period": row["period"], "value": row["value"],
             "repeated": pair_counts[row["period"]] - 1}
            for row in group_rows if row["period"]]
        # A repeated key is one (group, period) pair carrying more than one record. Rows with
        # no period are missing periods, not repeats, and must never be counted here.
        repeated_keys = sum(1 for count in pair_counts.values() if count > 1)
        records_in_repeated = sum(count for count in pair_counts.values() if count > 1)
        groups.append({
            "group": key,
            "n": len(group_rows),
            "values": [row["value"] for row in group_rows],
            "summary": _summary(member_values),
            "periods": sorted(period_records, key=lambda item: item["period"]),
            "repeated_group_period_count": repeated_keys,
            "records_in_repeated_keys": records_in_repeated,
        })
    global_periods = sorted({row["period"] for row in rows if row["period"]})
    missing = {
        "measure": sum(1 for row in rows if row["value"] is None),
        "group": sum(1 for row in rows if row["category"] is None),
        # A period can only be missing when a time column was confirmed; without one there is
        # no observation date to be missing.
        "periods": (sum(1 for row in rows if row["period"] is None) if time_col else 0),
    }
    quality = {
        "repeated_group_period_keys": sum(group["repeated_group_period_count"]
                                          for group in groups),
        "records_in_repeated_keys": sum(group["records_in_repeated_keys"]
                                        for group in groups),
        "note": ("A repeated group-period key is one group-and-period pair carrying more than "
                 "one record. Repeated records are preserved as separate observations; they "
                 "are never summed, averaged or thinned. A missing period is not a repeat."),
    }
    return {
        "schema": NEUTRAL_ANALYSIS_SCHEMA,
        "method": {"calc_version": CALC_VERSION, "definitions": CALC_DEFINITIONS},
        "interpretation": dict(interpretation),
        "source": {"filename": (dataset or {}).get("source_filename"),
                   "input_sha256": (dataset or {}).get("input_sha256")},
        "row_count": len(rows),
        "measure": {
            "column": measure,
            "label": interpretation.get("measure_label") or measure,
            "unit": interpretation.get("unit") or UNKNOWN,
            "meaning": interpretation.get("meaning") or UNKNOWN,
        },
        "time": {"column": time_col,
                 "periods": global_periods,
                 "has_time": bool(time_col),
                 "period_count": len(global_periods)},
        "groups": groups,
        "group_count": len(groups),
        "groups_sorted": group_order,
        "summary": _summary(values),
        "missing": missing,
        "quality": quality,
    }


# ---------------------------------------------------------------- validation

def validate_interpretation(interpretation) -> dict:
    """Validate and normalise the confirmed interpretation payload."""
    if not isinstance(interpretation, dict):
        raise NeutralError("Interpretation must be an object.")
    unknown = set(interpretation) - {"category", "measure", "time", "measure_label",
                                     "unit", "meaning", "missing_tokens"}
    if unknown:
        raise NeutralError("Unknown interpretation fields: " + ", ".join(sorted(unknown)))
    category = validate_column_name(interpretation.get("category") or "")
    measure = validate_column_name(interpretation.get("measure") or "")
    time_col = interpretation.get("time") or None
    if time_col is not None:
        time_col = validate_column_name(time_col)
    if category == measure or time_col in (category, measure):
        raise NeutralError("Category, measure and time must be distinct columns.")
    label = interpretation.get("measure_label")
    if label is not None and (not isinstance(label, str) or len(label.strip()) > 200):
        raise NeutralError("The measure label must be short text.")
    unit = interpretation.get("unit")
    if unit is not None and (not isinstance(unit, str) or len(unit.strip()) > 100):
        raise NeutralError("The unit must be short text.")
    meaning = interpretation.get("meaning")
    if meaning is not None and (not isinstance(meaning, str) or len(meaning.strip()) > 500):
        raise NeutralError("The row-meaning statement must be short text.")
    tokens = interpretation.get("missing_tokens") or []
    if not isinstance(tokens, list) or any(
            not isinstance(token, str) or not token.strip() for token in tokens):
        raise NeutralError("Missing tokens must be a list of nonempty exact strings.")
    return {"category": category, "measure": measure, "time": time_col,
            "measure_label": (label or "").strip() or None,
            "unit": (unit or "").strip() or None,
            "meaning": (meaning or "").strip() or None,
            "missing_tokens": sorted(set(tokens))}


def analysis_compatible(prepared: dict, analysis: dict, interpretation: dict | None = None):
    """(ok, reason) — can this stored analysis be reused as current?

    Compatibility is a conjunction, never a version check:
      1. identity — the analysis and the prepared rows name the same captured bytes;
      2. confirmed-settings identity — the rows were prepared, and the analysis recorded, under
         the interpretation that is confirmed now;
      3. result integrity — re-running the declared method over the saved rows reproduces every
         analytical field.
    ``calc_version`` is only used to refuse a NEWER calculation; a matching version alone never
    authenticates a result. Analyses written before the marker existed are handled by the same
    recomputation, so no migration is required.
    """
    if not isinstance(analysis, dict) or not isinstance(prepared, dict):
        return False, "The saved analysis is not readable."
    version = (analysis.get("method") or {}).get("calc_version")
    if isinstance(version, int) and version > CALC_VERSION:
        return False, (f"This analysis was produced by a newer calculation (v{version}) than this "
                       f"service supports (v{CALC_VERSION}).")

    analysis_source = (analysis.get("source") or {}).get("input_sha256")
    prepared_source = (prepared.get("source") or {}).get("input_sha256")
    if not analysis_source or analysis_source != prepared_source:
        return False, ("The saved analysis does not belong to these prepared records. "
                       "Update the analysis to recompute it from the captured file.")

    roles = ("category", "measure", "time", "missing_tokens")

    def normalise(settings):
        settings = settings or {}
        return {key: (sorted(settings.get(key) or []) if key == "missing_tokens"
                      else settings.get(key)) for key in roles}

    confirmed = interpretation if interpretation is not None else analysis.get("interpretation")
    if normalise(prepared.get("interpretation")) != normalise(confirmed):
        return False, ("The prepared records were built under different confirmed settings. "
                       "Update the analysis to recompute them from the captured file.")
    if analysis.get("interpretation") and \
            normalise(analysis["interpretation"]) != normalise(confirmed):
        return False, ("The saved analysis records different settings from the confirmed "
                       "interpretation. Update the analysis.")

    try:
        fresh = describe(list(prepared["rows"]), analysis["interpretation"])
    except (KeyError, TypeError, ValueError) as error:
        return False, f"The saved analysis cannot be re-verified: {error}"
    fields = ("row_count", "groups", "group_count", "summary", "missing", "quality",
              "time", "measure", "groups_sorted")
    differing = [field for field in fields if fresh.get(field) != analysis.get(field)]
    if differing:
        return False, ("The saved analysis no longer matches the confirmed data and current "
                       "definitions (" + ", ".join(differing) + "). Update the analysis to "
                       "recompute it from the captured records.")
    return True, None


def verify_repeatable(prepared: dict, analysis: dict) -> list[str]:
    """Deterministic verification: re-derive the descriptor from the prepared rows.

    The prepared JSON rows are the recorded inputs; re-running describe over them must
    reproduce the recorded descriptor. Not a substitute for an independent implementation.
    """
    issues = []
    rows = prepared["rows"]
    if not isinstance(rows, list) or len(rows) != analysis.get("row_count"):
        issues.append("row count mismatch between prepared rows and analysis")
    try:
        recomputed = describe(rows, analysis["interpretation"],
                              dataset={"source_filename": prepared["source"]["filename"],
                                       "input_sha256": prepared["source"]["input_sha256"]})
        for field in ("row_count", "summary", "group_count", "groups", "missing", "quality"):
            if recomputed.get(field) != analysis.get(field):
                issues.append(f"{field} mismatch between prepared rows and analysis")
    except (KeyError, TypeError, NeutralError) as exc:
        issues.append(f"analysis cannot be re-derived: {exc}")
    return issues
