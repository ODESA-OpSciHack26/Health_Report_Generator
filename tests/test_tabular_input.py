"""Regression contracts for isolated tabular-input helpers."""
import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/health_pipeline"))

from tabular_input import inspect_table, normalize_periods  # noqa: E402


@pytest.mark.parametrize(
    "suffix,payload,delimiter",
    [
        (".csv", b"category,value\nAlpha,10\nBeta,20\n", ","),
        (".tsv", b"category\tvalue\nAlpha\t10\nBeta\t20\n", "\t"),
        (".csv", b'category,value\n"Alpha, quoted",10\nBeta,20\n', ","),
        (".csv", b"\xef\xbb\xbfcategory,value\r\nAlpha,10\r\nBeta,20\r\n", ","),
        (".csv", b"category,value\nAlpha,10\n\nBeta,20\n", ","),
    ],
)
def test_inspection_preserves_source_and_hashes_exact_bytes(
    tmp_path, suffix, payload, delimiter
):
    source = tmp_path / ("input" + suffix)
    source.write_bytes(payload)
    result = inspect_table(source)
    assert result.input_sha256 == hashlib.sha256(payload).hexdigest()
    assert result.byte_count == len(payload)
    assert result.source_filename == source.name
    assert result.columns == ("category", "value")
    assert result.row_count == 2
    assert result.delimiter == delimiter
    assert source.read_bytes() == payload
    assert sorted(p.name for p in tmp_path.iterdir()) == [source.name]


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"category,value\n",
        b"category, \nAlpha,10\n",
        b"category,category\nAlpha,10\n",
        b"category, category \nAlpha,10\n",
        b"category,value\nAlpha,10,extra\n",
        b"category,value\nAlpha\n",
        b'category,value\n"unclosed,10\n',
        b"category,value\n\xff,10\n",
    ],
)
def test_invalid_structure_is_rejected_without_outputs(tmp_path, payload):
    source = tmp_path / "input.csv"
    source.write_bytes(payload)
    with pytest.raises(ValueError):
        inspect_table(source)
    assert source.read_bytes() == payload
    assert sorted(p.name for p in tmp_path.iterdir()) == [source.name]


def test_unsupported_extension_is_rejected(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("category,value\nAlpha,10\n")
    with pytest.raises(ValueError, match="csv or .tsv"):
        inspect_table(source)


@pytest.mark.parametrize(
    "values,period,expected",
    [
        (["2023-01-01", "2024-01-01"], "year",
         ["2023-01-01", "2024-01-01"]),
        ([2023, 2024], "year", ["2023-01-01", "2024-01-01"]),
        (["2023", "2024"], "year", ["2023-01-01", "2024-01-01"]),
        (["2023-06-15", "2024-09-20"], "year",
         ["2023-01-01", "2024-01-01"]),
        (["2023-02-14", "2023-03-18"], "month",
         ["2023-02-01", "2023-03-01"]),
        (["2023-02-14", "2023-02-15"], "day",
         ["2023-02-14", "2023-02-15"]),
        (["2023-02-19", "2023-02-20"], "week",
         ["2023-02-13", "2023-02-20"]),
        (["2023-01-01", None], "year", ["2023-01-01", None]),
        ([2023, None], "year", ["2023-01-01", None]),
    ],
)
def test_temporal_normalization(values, period, expected):
    source = pd.Series(values, index=[4, 9], name="date")
    before = source.copy(deep=True)
    actual = normalize_periods(source, period=period)
    wanted = pd.Series(
        pd.to_datetime(expected), index=source.index, name=source.name
    )
    pd.testing.assert_series_equal(actual, wanted)
    pd.testing.assert_series_equal(source, before)


def test_snapshot_does_not_invent_dates():
    source = pd.Series(["Alpha", "Beta"], index=[4, 9], name="category")
    actual = normalize_periods(source, period=None)
    expected = pd.Series(
        pd.NaT, index=source.index, name=source.name, dtype="datetime64[ns]"
    )
    pd.testing.assert_series_equal(actual, expected)


@pytest.mark.parametrize(
    "values,period",
    [
        (["not-a-date"], "year"),
        (["2023-02-30"], "day"),
        ([2023.5], "year"),
        ([float("inf")], "year"),
        ([2023], "day"),
        ([True], "year"),
        ([2023 + 1j], "year"),
        (["2023-01-01T00:00:00+00:00"], "day"),
        (["2023-01-01"], "quarter"),
    ],
)
def test_invalid_temporal_values_are_not_silently_dropped(values, period):
    with pytest.raises(ValueError):
        normalize_periods(pd.Series(values), period=period)
