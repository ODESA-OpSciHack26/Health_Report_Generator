"""Neutral CSV data layer: capture, interpretation, preparation, description, limits."""
import copy
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "health_pipeline"))

import neutral_describe as nd  # noqa: E402


def capture_csv(text, name="sample.csv"):
    return nd.capture_payload(text.encode("utf-8"), source_filename=name)


def conf(category="city", measure="value", time=None, **extra):
    payload = {"category": category, "measure": measure}
    if time:
        payload["time"] = time
    payload.update(extra)
    return nd.validate_interpretation(payload)


def test_capture_preserves_exact_bytes_and_structure():
    payload = "city,value,year\nZürich,12,2021\nBern ,9,2021\n".encode("utf-8")
    cap = nd.capture_payload(payload, source_filename="sample.csv")
    assert cap.input_sha256 == hashlib.sha256(payload).hexdigest()
    assert cap.columns == ("city", "value", "year")
    # header spelling is preserved exactly, including the trailing space
    assert cap.header == ("city", "value", "year")
    assert cap.logical_records == 2
    assert cap.delimiter == ","


def test_capture_accepts_utf8_bom_and_tsv():
    payload = "\ufeffa\tb\n1\t2\n".encode("utf-8")
    cap = nd.capture_payload(payload, source_filename="t.tsv")
    assert cap.delimiter == "\t" and cap.columns == ("a", "b")


@pytest.mark.parametrize("payload,reason", [
    (b"", "no header"),
    ("a\n".encode(), "no data rows"),
    ("a,a\n1,2\n".encode(), "duplicate headers"),
    ("a,b\n1,2,3\n".encode(), "width mismatch"),
    ("a,b\n\"unclosed,2\n".encode(), "malformed quoting"),
])
def test_capture_rejects_bad_structure(payload, reason):
    with pytest.raises(nd.NeutralError):
        nd.capture_payload(payload, source_filename="x.csv")


def test_capture_rejects_oversized_upload():
    payload = ("a,b\n" + "1,2\n" * 3).encode()
    with pytest.raises(nd.NeutralError):
        nd.capture_payload(payload, source_filename="x.csv",
                           limits={**nd.LIMITS, "max_upload_bytes": 10})


def test_suggestion_picks_numeric_measure_and_text_group():
    cap = capture_csv("city,value,year\nA,1.5,2021\nB,2.5,2022\nC,,2021\n")
    sug = nd.suggest_interpretation(cap)
    assert sug["measure"] == "value" and sug["category"] == "city"
    assert sug["time"] == "year"


def test_suggestion_never_turns_identifiers_into_dates():
    """A zero-padded identifier column must not be suggested as time (review finding D)."""
    payload = ("record_id,group,value\n001,North,12\n002,North,13\n"
               "003,South,14\n004,South,15\n")
    cap = capture_csv(payload)
    sug = nd.suggest_interpretation(cap)
    assert sug["category"] == "group"
    assert sug["measure"] == "value"
    assert sug["time"] is None, sug


@pytest.mark.parametrize("value", ["001", "01", "1", "0001", "12/01/2021", "2021-1-2",
                                   "jan 2021", "21"])
def test_period_parser_rejects_invented_dates(value):
    assert nd._parse_period_value(value) is None, value


@pytest.mark.parametrize("value,period", [("2021", "year"), ("2021-01-02", "day"),
                                          ("2021-01-02T03:04:05", "day")])
def test_period_parser_accepts_years_and_explicit_iso_dates(value, period):
    parsed = nd._parse_period_value(value)
    assert parsed is not None and parsed[0] == period


def test_selected_no_time_stays_no_time_through_preparation_and_description():
    """Choosing time=(none) must not invent a period anywhere (review finding D)."""
    payload = "record_id,group,value\n001,North,12\n002,South,13\n"
    cap = capture_csv(payload)
    interp = nd.validate_interpretation({"category": "group", "measure": "value",
                                         "time": None, "missing_tokens": []})
    prep = nd.prepare_payload_under(cap, payload.encode(), interp)
    assert [row["period"] for row in prep["rows"]] == [None, None]
    analysis = nd.describe(prep["rows"], interp)
    assert analysis["time"]["has_time"] is False
    assert analysis["time"]["column"] is None
    assert analysis["time"]["period_count"] == 0
    assert analysis["missing"]["periods"] == 0


def test_repeated_keys_exclude_missing_periods_and_count_records():
    """Fixture 3 shape: a missing period must not be counted as a repeated key (finding F)."""
    payload = ("group,value,year\n"
               "North,10,2021\nNorth,11,2022\nNorth,12,2022\nNorth,13,2023\n"
               "South,20,2021\nSouth,21,2022\nSouth,,2023\nSouth,23,2024\n"
               "East,30,2021\nEast,31,\nEast,32,2023\n")
    cap = capture_csv(payload)
    interp = nd.validate_interpretation({"category": "group", "measure": "value",
                                         "time": "year", "missing_tokens": []})
    prep = nd.prepare_payload_under(cap, payload.encode(), interp)
    analysis = nd.describe(prep["rows"], interp)
    assert analysis["row_count"] == 11
    assert analysis["missing"] == {"measure": 1, "group": 0, "periods": 1}
    # One duplicated key (North/2022) carried by two records; the East row with no period is
    # a gap, not a repeat.
    assert analysis["quality"]["repeated_group_period_keys"] == 1
    assert analysis["quality"]["records_in_repeated_keys"] == 2
    north = next(g for g in analysis["groups"] if g["group"] == "North")
    assert north["n"] == 4 and north["repeated_group_period_count"] == 1
    east = next(g for g in analysis["groups"] if g["group"] == "East")
    assert east["n"] == 3 and east["repeated_group_period_count"] == 0


def test_preparation_keeps_ordinals_raw_strings_and_missingness():
    payload = "city,value\nA,12\nB,oops-if-missing\nA,\n".encode()
    cap = nd.capture_payload(payload, source_filename="x.csv")
    interp = conf(missing_tokens=["oops-if-missing"])
    prep = nd.prepare_payload_under(cap, payload, interp)
    assert prep["row_count"] == 3
    assert prep["rows"][0]["ordinal"] == 1 and prep["rows"][0]["raw"] == ["A", "12"]
    # declared token becomes missing; blank becomes missing; literal numbers stay
    assert prep["rows"][1]["value"] is None and prep["rows"][2]["value"] is None
    assert prep["rows"][0]["value"] == 12.0


def test_preparation_rejects_undeclared_nonnumber():
    payload = "city,value\nA,12\nB,NaN-like\n".encode()
    cap = nd.capture_payload(payload, source_filename="x.csv")
    with pytest.raises(nd.NeutralError):
        nd.prepare_payload_under(cap, payload, conf())


def test_preparation_parses_years_and_iso_dates():
    payload = "g,val,d\nA,1,2021\nB,2,2021\nA,3,2024-01-02\n".encode("utf-8")
    cap = nd.capture_payload(payload, source_filename="x.csv")
    prep = nd.prepare_payload_under(cap, payload, conf(category="g", measure="val", time="d"))
    periods = [row["period"] for row in prep["rows"]]
    assert periods[:2] == ["2021-01-01T00:00:00", "2021-01-01T00:00:00"]
    assert periods[2].startswith("2024-01-02")


def test_describe_is_explicit_and_does_not_pool():
    payload = "g,val,d\nA,1,2021\nA,2,2021\nA,9,2022\nB,5,2021\nB,5,2021\n".encode("utf-8")
    cap = nd.capture_payload(payload, source_filename="x.csv")
    interp = conf(category="g", measure="val", time="d")
    prep = nd.prepare_payload_under(cap, payload, interp)
    analysis = nd.describe(prep["rows"], interp)
    assert analysis["row_count"] == 5
    assert analysis["quality"]["repeated_group_period_keys"] == 2  # A-2021, B-2021 duplicated
    group_by_name = {g["group"]: g for g in analysis["groups"]}
    assert group_by_name["A"]["n"] == 3
    # values preserved verbatim, never merged
    assert group_by_name["A"]["values"] == [1.0, 2.0, 9.0]
    # inclusive quartiles from the tabular route: n=3 -> median is the middle value
    assert group_by_name["A"]["summary"]["median"] == 2.0
    assert analysis["time"]["has_time"] is True


def test_verify_repeatable_agrees():
    payload = "g,val\nA,1\nA,2\nB,3\n".encode("utf-8")
    cap = nd.capture_payload(payload, source_filename="x.csv")
    interp = conf(category="g", measure="val")
    prep = nd.prepare_payload_under(cap, payload, interp)
    analysis = nd.describe(prep["rows"], interp)
    assert nd.verify_repeatable(prep, analysis) == []
    analysis["summary"]["mean"] = 999.0
    assert nd.verify_repeatable(prep, analysis)


def test_validate_interpretation_rejects_unknown_fields_and_duplicates():
    with pytest.raises(nd.NeutralError):
        nd.validate_interpretation({"category": "a", "measure": "b", "sneaky": True})
    with pytest.raises(nd.NeutralError):
        nd.validate_interpretation({"category": "a", "measure": "a"})

def test_compatibility_is_identity_and_integrity_not_version():
    """A matching calc_version must never authenticate a result on its own."""
    payload = "g,val\nA,1\nA,2\nB,3\n".encode()
    capture = nd.capture_payload(payload, source_filename="x.csv")
    interpretation = conf(category="g", measure="val")
    prepared = nd.prepare_payload_under(capture, payload, interpretation)
    analysis = nd.describe(prepared["rows"], interpretation,
                           dataset={"source_filename": "x.csv",
                                    "input_sha256": capture.input_sha256})
    analysis["method"] = {"calc_version": nd.CALC_VERSION}
    assert nd.analysis_compatible(prepared, analysis, interpretation) == (True, None)

    tampered = copy.deepcopy(analysis)
    tampered["groups"][0]["summary"]["median"] = 99.0
    assert tampered["method"]["calc_version"] == nd.CALC_VERSION
    ok, reason = nd.analysis_compatible(prepared, tampered, interpretation)
    assert not ok and "no longer matches" in reason

    wrong_capture = copy.deepcopy(prepared)
    wrong_capture["source"]["input_sha256"] = "0" * 64
    ok, reason = nd.analysis_compatible(wrong_capture, analysis, interpretation)
    assert not ok and "does not belong" in reason

    other = dict(interpretation)
    other["measure"] = "other"
    ok, reason = nd.analysis_compatible(prepared, analysis, other)
    assert not ok and "different confirmed settings" in reason

    newer = copy.deepcopy(analysis)
    newer["method"]["calc_version"] = nd.CALC_VERSION + 1
    ok, reason = nd.analysis_compatible(prepared, newer, interpretation)
    assert not ok and "newer calculation" in reason

    legacy = copy.deepcopy(analysis)
    legacy.pop("method")                     # analyses written before the marker existed
    assert nd.analysis_compatible(prepared, legacy, interpretation) == (True, None)
