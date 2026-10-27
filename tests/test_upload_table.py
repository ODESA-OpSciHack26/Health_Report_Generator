"""A reader's own cleaned table: checked, described honestly, never mixed with project data."""
import ast
import json
from pathlib import Path

import pandas as pd
import pytest

import upload_table

ROOT = Path(__file__).resolve().parents[1]


def table(**changes):
    rows = [dict(topic=t, source_system="mandatory_reporting_system", measure="cases", period=str(y),
                 period_type="year", place="CHFL", place_type="CHFL", age_group="all", sex="all", breakdown="",
                 value=float(10 + y - 2019), pop=9e6, incValue=0.1, is_stat_row=False, year=y)
            for t in ["influenza", "ehec", "wastewater_load"] for y in range(2019, 2026)]
    frame = pd.DataFrame(rows)
    for column, value in changes.items():
        frame[column] = value
    return frame


def save(frame, tmp_path, name="mine.csv"):
    path = tmp_path / name
    frame.to_parquet(path, index=False) if name.endswith(".parquet") else frame.to_csv(path, index=False)
    return path


def test_required_columns_match_what_the_reports_read():
    tree = ast.parse((ROOT / "reports/utils/helpers.py").read_text(encoding="utf-8"))
    columns = next(ast.literal_eval(n.value) for n in tree.body
                   if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "COLUMNS")
    assert upload_table.REQUIRED == columns


def test_good_table_gets_a_complete_results_folder(tmp_path):
    info = upload_table.prepare(save(table(), tmp_path), "mine.csv", tmp_path / "uploads")
    folder = tmp_path / "uploads" / info["sha256"][:12]
    assert info["diseases"] == ["influenza", "ehec"] and info["years"] == [2019, 2025] and info["rows"] == 21
    for name in ["harmonised.csv", "checks.csv", "datasets.csv", "harmonised_snapshot.json", "upload.json"]:
        assert (folder / name).is_file(), name
    checks = pd.read_csv(folder / "checks.csv")
    assert set(checks.status) == {"PASS"}
    snapshot = json.loads((folder / "harmonised_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["snapshot_id"] == f"upload-{info['sha256'][:12]}"
    assert pd.read_csv(folder / "datasets.csv").source_file.tolist() == ["mine.csv"]


def test_same_file_is_reused(tmp_path):
    path = save(table(), tmp_path)
    first = upload_table.prepare(path, "mine.csv", tmp_path / "uploads")
    assert upload_table.prepare(path, "renamed.csv", tmp_path / "uploads") == first


def test_parquet_upload_is_accepted(tmp_path):
    info = upload_table.prepare(save(table(), tmp_path, "mine.parquet"), "mine.parquet", tmp_path / "uploads")
    assert info["rows"] == 21


@pytest.mark.parametrize("frame,message", [
    (table().drop(columns=["incValue"]), "required_columns"),
    (table(value=-1.0), "nonnegative_counts"),
    (table(value="many"), "numeric_values"),
    (table(topic="something_else"), "known_diseases"),
    (table(year="unknown"), "integer_years"),
])
def test_unusable_tables_are_refused(tmp_path, frame, message):
    with pytest.raises(ValueError, match=message):
        upload_table.prepare(save(frame, tmp_path), "bad.csv", tmp_path / "uploads")
    assert not any((tmp_path / "uploads").glob("*/upload.json"))


def test_duplicates_only_warn(tmp_path):
    frame = table()
    info = upload_table.prepare(save(pd.concat([frame, frame.iloc[:1]]), tmp_path), "dup.csv", tmp_path / "uploads")
    checks = pd.read_csv(tmp_path / "uploads" / info["sha256"][:12] / "checks.csv").set_index("check")
    assert checks.loc["unique_keys", "status"] == "WARN"
