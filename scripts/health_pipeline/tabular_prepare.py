"""Explicit, in-memory preparation; not wired to the default workflow."""
from __future__ import annotations

import csv
import hashlib
import io
import math
import platform
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import tabular_input as ti


@dataclass
class PreparedTable:
    """Mutable in-memory result, not a verified publication or cache entry."""

    table: pd.DataFrame
    provenance: dict
    source_bytes: bytes


def _parameters(mapping, mode, period):
    if mode not in ("snapshot", "timeseries"):
        raise ValueError("Mode must be snapshot or timeseries.")
    if not isinstance(mapping, Mapping):
        raise ValueError("Mapping must name category and measure columns.")
    required = {"category", "measure"}
    if mode == "timeseries":
        required.add("time")
        if period not in ("year", "month", "week", "day"):
            raise ValueError("Time-series mode requires a supported period.")
    elif period is not None:
        raise ValueError("Snapshot mode requires period=None.")
    if set(mapping) != required:
        raise ValueError("Mapping keys do not match the explicit mode.")
    if any(not isinstance(value, str) or not value.strip()
           for value in mapping.values()):
        raise ValueError("Mapped column names must be non-empty strings.")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Mapped roles must use distinct columns.")
    return dict(mapping)


def _missing_blanks(series):
    """Only empty or whitespace-only fields are treated as missing."""
    return series.mask(series.str.strip().eq(""), pd.NA)


def prepare_table(source, *, mapping, mode, period):
    """Prepare one captured CSV/TSV without aggregation or filesystem writes.

    Output columns are category, value and period. Original bytes are retained.
    Literal NA/null tokens are not automatically interpreted as missing.
    Numeric precision follows pandas; this is not an exact-decimal contract.
    """
    mapping = _parameters(mapping, mode, period)
    source = Path(source)
    if source.suffix.lower() not in {".csv", ".tsv"}:
        raise ValueError("Input must be a .csv or .tsv file.")
    return prepare_payload(source.read_bytes(), source_filename=source.name,
                           mapping=mapping, mode=mode, period=period)


def prepare_payload(payload, *, source_filename, mapping, mode, period):
    """Prepare captured bytes without reopening or publishing a source file."""
    mapping = _parameters(mapping, mode, period)
    inspected = ti.inspect_payload(payload, source_filename=source_filename)
    if any(column not in inspected.columns for column in mapping.values()):
        raise ValueError("A mapped column is absent from the input.")

    reader = csv.reader(
        io.StringIO(payload.decode("utf-8-sig"), newline=""),
        delimiter=inspected.delimiter, strict=True,
    )
    columns = next(reader)
    records = [row for row in reader if row]
    raw = pd.DataFrame(records, columns=columns, dtype="string")
    if len(raw) != inspected.row_count:
        raise ValueError("Inspection and parsing row counts differ.")

    category = _missing_blanks(raw[mapping["category"]])
    measure = _missing_blanks(raw[mapping["measure"]])
    try:
        numeric = pd.to_numeric(measure, errors="raise")
        if any(not math.isfinite(value) for value in numeric.dropna()):
            raise ValueError("Non-finite measures are not supported.")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid or non-finite numeric measure.") from exc

    if mode == "timeseries":
        times = _missing_blanks(raw[mapping["time"]])
        periods = ti.normalize_periods(times, period=period)
        if (times.notna() & periods.isna()).any():
            raise ValueError("A non-missing time value became missing.")
    else:
        periods = ti.normalize_periods(category, period=None)

    table = pd.DataFrame({
        "category": category,
        "value": numeric,
        "period": periods,
    })
    code_paths = [Path(__file__), Path(ti.__file__)]
    provenance = {
        "schema": "health-report/tabular-preparation/1",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": {
            "source_filename": inspected.source_filename,
            "sha256": inspected.input_sha256,
            "bytes": inspected.byte_count,
            "delimiter": inspected.delimiter,
            "columns": list(inspected.columns),
            "rows": inspected.row_count,
        },
        "parameters": {
            "mapping": mapping,
            "mode": mode,
            "period": period,
        },
        "filters": [],
        "aggregation": "none",
        "missing_policy": "empty or whitespace-only fields",
        "temporal_policy": {
            "timezone": "naive only",
            "week_start": "Monday",
            "snapshot_date": None,
        },
        "output": {
            "rows": len(table),
            "columns": list(table.columns),
            "row_order": "source order; blank records excluded",
            "missing": {
                "category": int(category.isna().sum()),
                "value": int(numeric.isna().sum()),
                "period": int(periods.isna().sum())
                if mode == "timeseries" else None,
            },
        },
        "software": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
        },
        "code_files_on_disk": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in code_paths
        },
        "limitations": [
            "No scientific interpretation or aggregation.",
            "No upload-size or security acceptance.",
            "Mutable result; not a verified publication.",
            "Code hashes identify files on disk, not a Git attestation.",
            "Numeric precision follows pandas, not exact decimal arithmetic.",
        ],
    }
    return PreparedTable(table, provenance, payload)
