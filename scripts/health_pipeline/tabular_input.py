"""Isolated tabular-input helpers; not enabled in the reporting workflow.

Design inputs:
- v2 CSV inspection: 6cbe222eb7edefe353d7370168c974c43b1a5350
- Nisha temporal regression: a1cba89bbb5e37b20b48e2df8b334aa4ba7d250b

Structural validity does not establish scientific validity or upload safety.
Inspection reads the complete file into memory. No publication occurs here.
"""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_complex_dtype,
    is_numeric_dtype,
)


@dataclass(frozen=True)
class TableInspection:
    source_filename: str
    input_sha256: str
    byte_count: int
    delimiter: str
    columns: tuple[str, ...]
    row_count: int


def inspect_table(path: str | Path) -> TableInspection:
    """Inspect one UTF-8 CSV/TSV snapshot without modifying the source.

    Blank records are ignored. Header spelling is preserved, but headers
    must be non-empty and unique after surrounding whitespace is stripped.
    The returned hash identifies the bytes inspected, not a future reread.
    """
    source = Path(path)
    if source.suffix.lower() not in {".csv", ".tsv"}:
        raise ValueError("Input must be a .csv or .tsv file.")
    return inspect_payload(source.read_bytes(), source_filename=source.name)


def inspect_payload(payload: bytes, *, source_filename: str) -> TableInspection:
    """Inspect captured bytes; never reopen the source file."""
    if not isinstance(payload, bytes):
        raise ValueError("Captured input must be bytes.")
    source = Path(source_filename)
    suffix = source.suffix.lower()
    if suffix not in {".csv", ".tsv"}:
        raise ValueError("Input must be a .csv or .tsv file.")

    delimiter = "\t" if suffix == ".tsv" else ","
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Input must be UTF-8 encoded.") from exc

    reader = csv.reader(
        io.StringIO(text, newline=""), delimiter=delimiter, strict=True
    )
    try:
        columns = next(reader, None)
        if not columns or any(not column.strip() for column in columns):
            raise ValueError("Input requires non-empty column headers.")
        normalized = [column.strip() for column in columns]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate column headers are not allowed.")

        rows = 0
        for row in reader:
            if not row:
                continue
            if len(row) != len(columns):
                raise ValueError(
                    f"Record ending at line {reader.line_num} has "
                    f"{len(row)} fields; expected {len(columns)}."
                )
            rows += 1
    except csv.Error as exc:
        raise ValueError("Malformed CSV/TSV quoting.") from exc

    if rows == 0:
        raise ValueError("Input contains no data rows.")

    return TableInspection(
        source_filename=source.name,
        input_sha256=hashlib.sha256(payload).hexdigest(),
        byte_count=len(payload),
        delimiter=delimiter,
        columns=tuple(columns),
        row_count=rows,
    )


def normalize_periods(
    values: pd.Series, *, period: str | None
) -> pd.Series:
    """Return period starts without changing input values.

    A None period denotes a snapshot and produces missing dates.
    Numeric values are supported only as whole calendar years.
    Date values must be parseable and timezone-naive.
    Weeks start on Monday (pandas W-SUN periods).
    Missing input dates remain missing; invalid dates raise ValueError.
    """
    frequencies = {
        "year": "Y", "month": "M", "week": "W-SUN", "day": "D"
    }
    if period is None:
        return pd.Series(
            pd.NaT, index=values.index,
            dtype="datetime64[ns]", name=values.name,
        )
    if period not in frequencies:
        raise ValueError("Unsupported temporal period.")

    try:
        if is_bool_dtype(values.dtype) or is_complex_dtype(values.dtype):
            raise ValueError("Boolean and complex temporal values are invalid.")
        if is_numeric_dtype(values.dtype):
            if period != "year":
                raise ValueError("Numeric temporal values require year periods.")
            encoded = values.astype("Int64").astype("string") + "-01-01"
            parsed = pd.to_datetime(encoded, errors="raise")
        else:
            parsed = pd.to_datetime(values, errors="raise", format="mixed")

        if parsed.dt.tz is not None:
            raise ValueError("Timezone-aware dates require an explicit policy.")
        result = parsed.dt.to_period(frequencies[period]).dt.start_time
    except (ValueError, TypeError, OverflowError, AttributeError) as exc:
        raise ValueError("Invalid temporal values or unsupported encoding.") from exc

    result.name = values.name
    return result
