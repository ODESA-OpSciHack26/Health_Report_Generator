"""Any table: columns classified once, checked, and refused only when there is nothing to chart."""
import json

import pandas as pd
import pytest

import general_table


def save(tmp_path, text, name="mine.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_year_number_and_group_columns_are_found(tmp_path):
    path = save(tmp_path, "year,country,news_records\n2021,US,12400\n2021,DE,5300\n2022,US,13800\n2022,DE,5700\n")
    info = general_table.prepare(path, "mine.csv", tmp_path / "uploads")
    assert (info["time"], info["period"], info["years"]) == ("year", "year", [2021, 2022])
    assert info["measures"] == [{"name": "news_records", "how": "sum"}]
    assert info["groups"] == ["country"] and info["main_group_values"] == ["US", "DE"]
    folder = tmp_path / "uploads" / f"general-{info['sha256'][:12]}"
    for name in ["table.csv", "profile.json", "checks.csv", "upload.json"]:
        assert (folder / name).is_file(), name
    assert json.loads((folder / "profile.json").read_text(encoding="utf-8"))["time"] == "year"


def test_dates_semicolons_and_decimal_commas(tmp_path):
    path = save(tmp_path, "Datum;Kanton;cases;positivity rate\n2024-01-01;ZH;10;3,2\n2024-01-08;ZH;20;4,1\n"
                          "2024-01-01;BE;7;2,0\n2024-01-08;BE;9;2,5\n")
    info = general_table.prepare(path, "mine.csv", tmp_path / "uploads")
    assert (info["time"], info["period"]) == ("Datum", "week")
    assert info["measures"] == [{"name": "cases", "how": "sum"}, {"name": "positivity rate", "how": "mean"}]
    table = pd.read_csv(tmp_path / "uploads" / f"general-{info['sha256'][:12]}" / "table.csv")
    assert table["positivity rate"].tolist() == [3.2, 4.1, 2.0, 2.5]


def test_table_without_time_is_a_snapshot(tmp_path):
    info = general_table.prepare(save(tmp_path, "city,visits\nBern,3\nBasel,5\n"), "mine.csv", tmp_path / "uploads")
    assert info["time"] is None and info["years"] is None
    checks = pd.read_csv(tmp_path / "uploads" / f"general-{info['sha256'][:12]}" / "checks.csv").set_index("check")
    assert checks.loc["time_column", "status"] == "WARN"


def test_codes_are_not_added_up(tmp_path):
    info = general_table.prepare(save(tmp_path, "zip,city,visits\n3000,Bern,3\n4000,Basel,5\n"), "mine.csv",
                                 tmp_path / "uploads")
    assert [m["name"] for m in info["measures"]] == ["visits"] and "zip" in info["groups"]


def test_same_file_is_reused(tmp_path):
    path = save(tmp_path, "year,visits\n2020,1\n2021,2\n")
    assert general_table.prepare(path, "a.csv", tmp_path / "u") == general_table.prepare(path, "b.csv", tmp_path / "u")


def test_table_of_text_only_counts_rows(tmp_path):
    info = general_table.prepare(save(tmp_path, "city,kind\nBern,a\nBasel,b\nBern,b\n"), "mine.csv",
                                 tmp_path / "uploads")
    assert info["measures"] == [{"name": general_table.ROWS, "how": "sum", "counted": True}]
    assert info["main_group_values"] == ["Bern", "Basel"]
    checks = pd.read_csv(tmp_path / "uploads" / f"general-{info['sha256'][:12]}" / "checks.csv").set_index("check")
    assert checks.loc["number_columns", "status"] == "WARN"


def test_empty_table_is_refused(tmp_path):
    with pytest.raises(ValueError, match="not_empty"):
        general_table.prepare(save(tmp_path, "a,b\n"), "bad.csv", tmp_path / "uploads")
    assert not any((tmp_path / "uploads").glob("*/upload.json"))


def test_health_columns_are_recognised_for_routing(tmp_path):
    import upload_table
    header = ",".join(upload_table.REQUIRED) + "\n"
    assert set(upload_table.REQUIRED) <= set(general_table.columns_of(save(tmp_path, header)))
