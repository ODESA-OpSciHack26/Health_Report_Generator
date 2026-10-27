"""Contracts for explicit, side-effect-free tabular preparation."""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/health_pipeline"))

import tabular_input as ti  # noqa: E402
from tabular_prepare import prepare_table  # noqa: E402


def write_source(tmp_path, text, suffix=".csv"):
    path = tmp_path / ("input" + suffix)
    path.write_text(text, encoding="utf-8")
    return path


def snapshot(path, **changes):
    options = {
        "mapping": {"category": "group", "measure": "amount"},
        "mode": "snapshot",
        "period": None,
    }
    options.update(changes)
    return prepare_table(path, **options)


def test_snapshot_identity_missingness_and_no_outputs(tmp_path):
    path = write_source(tmp_path, "group,amount\nNA,10\n, \nBeta,-2\n")
    original = path.read_bytes()
    result = snapshot(path)
    assert result.source_bytes == original
    assert result.provenance["input"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert result.provenance["input"]["bytes"] == len(original)
    assert result.table["category"].iloc[0] == "NA"
    assert result.table["value"].dropna().tolist() == [10, -2]
    assert result.table["period"].isna().all()
    assert result.provenance["output"]["missing"] == {
        "category": 1, "value": 1, "period": None
    }
    assert result.provenance["filters"] == []
    assert result.provenance["aggregation"] == "none"
    assert path.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]
    json.dumps(result.provenance, allow_nan=False)


@pytest.mark.parametrize(
    "dates,period,expected",
    [
        (["2023-01-01", "2024-01-01"], "year",
         ["2023-01-01", "2024-01-01"]),
        (["2023", "2024"], "year",
         ["2023-01-01", "2024-01-01"]),
        (["2023-02-14", "2023-03-18"], "month",
         ["2023-02-01", "2023-03-01"]),
        (["2023-02-19", "2023-02-20"], "week",
         ["2023-02-13", "2023-02-20"]),
        (["2023-02-14", "2023-02-15"], "day",
         ["2023-02-14", "2023-02-15"]),
    ],
)
def test_explicit_temporal_mapping(tmp_path, dates, period, expected):
    path = write_source(
        tmp_path, f"group,amount,date\nBeta,20,{dates[0]}\nAlpha,10,{dates[1]}\n"
    )
    mapping = {"category": "group", "measure": "amount", "time": "date"}
    result = prepare_table(
        path, mapping=mapping, mode="timeseries", period=period
    )
    assert result.table["category"].tolist() == ["Beta", "Alpha"]
    assert result.table["value"].tolist() == [20, 10]
    assert result.table.index.tolist() == [0, 1]
    pd.testing.assert_series_equal(
        result.table["period"],
        pd.Series(pd.to_datetime(expected), name="period"),
    )
    assert result.provenance["parameters"] == {
        "mapping": mapping, "mode": "timeseries", "period": period
    }
    assert result.provenance["output"]["rows"] == 2


def test_normalization_does_not_aggregate(tmp_path):
    path = write_source(
        tmp_path,
        "group,amount,date\nAlpha,10,2023-02-01\nAlpha,20,2023-06-01\n",
    )
    result = prepare_table(
        path, mapping={"category": "group", "measure": "amount", "time": "date"},
        mode="timeseries", period="year",
    )
    assert len(result.table) == 2
    assert result.table["value"].tolist() == [10, 20]
    assert result.table["period"].nunique() == 1


def test_missing_date_is_preserved(tmp_path):
    path = write_source(
        tmp_path, "group,amount,date\nAlpha,10,\nBeta,20,2023-01-01\n"
    )
    result = prepare_table(
        path, mapping={"category": "group", "measure": "amount", "time": "date"},
        mode="timeseries", period="year",
    )
    assert len(result.table) == 2
    assert pd.isna(result.table["period"].iloc[0])
    assert result.provenance["output"]["missing"]["period"] == 1


@pytest.mark.parametrize("value", ["bad", "NA", "NaN", "inf", "-inf", "1,000"])
def test_invalid_measures_raise(tmp_path, value):
    path = write_source(tmp_path, f'group,amount\nAlpha,"{value}"\n')
    with pytest.raises(ValueError, match="numeric"):
        snapshot(path)


@pytest.mark.parametrize("value", ["bad", "2023-02-30", "NaT"])
def test_invalid_times_raise_without_row_loss(tmp_path, value):
    path = write_source(tmp_path, f"group,amount,date\nAlpha,10,{value}\n")
    with pytest.raises(ValueError):
        prepare_table(
            path,
            mapping={"category": "group", "measure": "amount", "time": "date"},
            mode="timeseries", period="day",
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "auto"},
        {"period": "year"},
        {"mapping": {"category": "group"}},
        {"mapping": {"category": "group", "measure": "absent"}},
        {"mapping": {"category": "group", "measure": "group"}},
        {"mapping": {"category": "group", "measure": "amount", "extra": "date"}},
        {"mapping": {"category": "group", "measure": ""}},
        {"mapping": None},
        {"mode": "timeseries", "period": "year"},
        {
            "mode": "timeseries", "period": None,
            "mapping": {"category": "group", "measure": "amount", "time": "date"},
        },
    ],
)
def test_invalid_requests_raise_without_outputs(tmp_path, changes):
    path = write_source(tmp_path, "group,amount,date\nAlpha,10,2023-01-01\n")
    with pytest.raises(ValueError):
        snapshot(path, **changes)
    assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]


def test_tsv_bom_and_quoted_fields(tmp_path):
    path = tmp_path / "input.tsv"
    path.write_bytes(b'\xef\xbb\xbfgroup\tamount\r\n"Alpha\tquoted"\t10\r\n')
    result = snapshot(path)
    assert result.table["category"].tolist() == ["Alpha\tquoted"]
    assert result.provenance["input"]["delimiter"] == "\t"


def test_structural_errors_are_not_bypassed(tmp_path):
    path = write_source(tmp_path, "group,amount\nAlpha,10,extra\n")
    with pytest.raises(ValueError, match="fields"):
        snapshot(path)


def test_parse_uses_captured_bytes_not_a_later_source_version(tmp_path, monkeypatch):
    path = write_source(tmp_path, "group,amount\nAlpha,10\n")
    original = path.read_bytes()
    read_bytes = Path.read_bytes
    reads = []

    def changed_after_capture(candidate):
        data = read_bytes(candidate)
        if candidate == path:
            reads.append(candidate)
            candidate.write_text("group,amount\nChanged,999\n")
        return data

    monkeypatch.setattr(Path, "read_bytes", changed_after_capture)
    result = snapshot(path)
    assert len(reads) == 1
    assert result.source_bytes == original
    assert result.table["category"].tolist() == ["Alpha"]
    assert result.table["value"].tolist() == [10]
    assert result.provenance["input"]["sha256"] == hashlib.sha256(original).hexdigest()


def test_byte_and_path_inspection_agree(tmp_path):
    path = write_source(tmp_path, "group,amount\nAlpha,10\n")
    assert ti.inspect_table(path) == ti.inspect_payload(
        path.read_bytes(), source_filename=path.name
    )


def test_provenance_has_timestamp_software_and_code_identity(tmp_path):
    path = write_source(tmp_path, "group,amount\nAlpha,10\n")
    provenance = snapshot(path).provenance
    assert pd.Timestamp(provenance["prepared_at_utc"]).tzinfo is not None
    assert provenance["software"]["pandas"] == pd.__version__
    assert set(provenance["code_files_on_disk"]) == {
        "tabular_prepare.py", "tabular_input.py"
    }
    for name, digest in provenance["code_files_on_disk"].items():
        code = ROOT / "scripts/health_pipeline" / name
        assert digest == hashlib.sha256(code.read_bytes()).hexdigest()
