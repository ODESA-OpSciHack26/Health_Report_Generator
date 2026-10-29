"""Saved annual series block: contract, binding, gap handling and identity.

The synthetic bundles here are test fixtures, not real dataset findings. Gap and
malformed-value cases are labelled as such; they were not observed in the retained data.
"""
import copy
import csv
import json
import subprocess
from pathlib import Path

import pytest

import composer_contracts as cc
import publish
from test_composer_contracts import read_fixture, sha256, SNAPSHOT_ID

ROOT = Path(__file__).resolve().parents[1]
SCOPE = read_fixture("valid/instance.json")["analysis"]["scope"]
DEFAULT_ROWS = (
    (2019, "7253.0"),
    (2021, "6802.0"),
    (2022, "7645.0"),
    (2023, "6784.0"),
    (2024, "8360.0"),
    (2025, "8716.0"),
)


def _write_csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_recipe(tmp_path, blocks, contract=publish.COMPOSITION_CONTRACT_V2,
                 audience="researcher", name="recipe.json"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"contract": contract, "audience": audience,
                                "blocks": blocks}))
    return path


def build_series_bundle(tmp_path, rows=None, *, topic="virus", label="Virus",
                        measure="cases", geography="CHFL", selection_status="included",
                        include_topics=None, dataset_ids=None, duplicate_year=False,
                        extra_topics=(), archive=True, root=None):
    """A small saved bundle with annual series rows and their count metrics."""
    results = Path(root or tmp_path) / "results"
    bundle = results / "reports" / "researcher" / "data"
    bundle.mkdir(parents=True)
    scope = copy.deepcopy(SCOPE)
    scope.update(years=[2021, 2025], reference_year=2019, geography=geography)
    stakeholder = {"id": "researcher", "title": "Series test", "question": "Q?",
                   "outputs": ["change_table"],
                   "presentation": {"display_name": "Researcher", "layout": "technical",
                                    "detail_level": "full", "version": "1.0"}}
    stakeholder.update(scope)
    if include_topics is not None:
        stakeholder["include_topics"] = list(include_topics)

    rows = list(DEFAULT_ROWS if rows is None else rows)
    if duplicate_year:
        rows.append((rows[2][0], "7000.0"))
    series, metrics, lineage, selection = [], [], [], []
    for index, (year, value) in enumerate(rows):
        dataset_id = dataset_ids[index] if dataset_ids else "ds1"
        metric_id = f"{topic}:{year}:count" if not (duplicate_year and index == len(rows) - 1) \
            else f"{topic}:{year}:count_alt"
        series.append({"topic": topic, "label": label, "pathogen_class": "viral",
                       "dataset_id": dataset_id, "source_system": "mandatory_reporting_system",
                       "measure": measure, "geography": geography, "year": year,
                       "value": value, "population": 100000, "incidence": 1.0,
                       "count_metric_id": metric_id,
                       "incidence_metric_id": "", "coverage": "complete",
                       "aggregation": "reported annual"})
        metrics.append({"metric_id": metric_id, "metric_type": "count", "subject": topic,
                        "year": year, "unit": measure, "value": value,
                        "formula": "raw_sum", "inputs_json": "[]"})
        lineage.append({"metric_id": metric_id, "input_kind": "raw", "input_id": "",
                        "source_file": "data/virus/data.csv",
                        "source_row": str(index + 2), "source_column": "value",
                        "sha256": "b" * 64, "metadata_sha256": "c" * 64})
    selection.append({"dataset_id": "ds1", "topic": topic,
                      "source_system": "mandatory_reporting_system",
                      "status": selection_status,
                      "reason": "Complete compatible series; explicit source priority",
                      "group_eligible": "True"})

    for extra_topic, extra_rows in extra_topics:
        for year, value in extra_rows:
            metric_id = f"{extra_topic}:{year}:count"
            series.append({"topic": extra_topic, "label": extra_topic.title(),
                           "pathogen_class": "bacterial", "dataset_id": "ds2",
                           "source_system": "mandatory_reporting_system",
                           "measure": measure, "geography": geography, "year": year,
                           "value": value, "population": 100000, "incidence": 1.0,
                           "count_metric_id": metric_id, "incidence_metric_id": "",
                           "coverage": "complete", "aggregation": "reported annual"})
            metrics.append({"metric_id": metric_id, "metric_type": "count",
                            "subject": extra_topic, "year": year, "unit": measure,
                            "value": value, "formula": "raw_sum", "inputs_json": "[]"})
            lineage.append({"metric_id": metric_id, "input_kind": "raw", "input_id": "",
                            "source_file": "data/extra/data.csv",
                            "source_row": "2", "source_column": "value",
                            "sha256": "b" * 64, "metadata_sha256": "c" * 64})
        selection.append({"dataset_id": "ds2", "topic": extra_topic,
                          "source_system": "mandatory_reporting_system",
                          "status": "included", "reason": "Complete compatible series",
                          "group_eligible": "True"})

    reference_rows = [row for row in rows if row[0] in (2019, 2025)]
    if len(reference_rows) == 2 and len({row[0] for row in reference_rows}) == 2:
        lookup = {year: value for year, value in rows}
        if 2019 in lookup and 2025 in lookup:
            metrics.append({"metric_id": f"{topic}:reference_change",
                            "metric_type": "reference_change", "subject": topic,
                            "year": 2025, "unit": "percent",
                            "value": "20.170963739142426", "formula": "percent_change",
                            "inputs_json": json.dumps([f"{topic}:2019:count",
                                                       f"{topic}:2025:count"])})
            lineage.append({"metric_id": f"{topic}:reference_change", "input_kind": "metric",
                            "input_id": f"{topic}:2019:count", "source_file": "",
                            "source_row": "", "source_column": "", "sha256": "",
                            "metadata_sha256": ""})
            lineage.append({"metric_id": f"{topic}:reference_change", "input_kind": "metric",
                            "input_id": f"{topic}:2025:count", "source_file": "",
                            "source_row": "", "source_column": "", "sha256": "",
                            "metadata_sha256": ""})

    _write_csv(bundle / "metrics.csv",
               ["metric_id", "metric_type", "subject", "year", "unit", "value",
                "formula", "inputs_json"], metrics)
    _write_csv(bundle / "series.csv",
               ["topic", "label", "pathogen_class", "dataset_id", "source_system",
                "measure", "geography", "year", "value", "population", "incidence",
                "count_metric_id", "incidence_metric_id", "coverage", "aggregation"],
               series)
    _write_csv(bundle / "selection.csv",
               ["dataset_id", "topic", "source_system", "status", "reason",
                "group_eligible"], selection)
    _write_csv(bundle / "lineage.csv",
               ["metric_id", "input_kind", "input_id", "source_file", "source_row",
                "source_column", "sha256", "metadata_sha256"], lineage)
    (bundle / "stakeholder.json").write_text(json.dumps(stakeholder))
    (bundle / "snapshot.json").write_text(json.dumps(
        {"snapshot_id": SNAPSHOT_ID, "snapshot_path": f"snapshots/{SNAPSHOT_ID}"}))
    files = {name: sha256(bundle / name) for name in
             ("metrics.csv", "series.csv", "selection.csv", "lineage.csv",
              "snapshot.json", "stakeholder.json")}
    (bundle / "bundle.json").write_text(json.dumps(
        {"schema_version": "2.0", "files": files}))
    if archive:
        archived = results / "snapshots" / SNAPSHOT_ID / "data" / "virus"
        archived.mkdir(parents=True)
        (archived / "data.csv").write_text("value\n10\n16\n")
    return {"bundle": bundle, "results": results}


def build(bundle, *, topic="virus", measure="cases", years=None, instance="series-test",
          presentation=None):
    return publish.build_series_block(bundle["bundle"], ROOT, instance, topic, measure,
                                      years, presentation)


def document_from(record, bundle):
    """Reassemble the authored contract document from a verified record for doctoring."""
    loaded = cc.load_bundle(bundle["bundle"])
    return {
        "contract": record["contract"]["series"],
        "component": record["component"],
        "instance_id": record["instance_id"],
        "analysis": {"snapshot_id": record["snapshot"]["snapshot_id"],
                     "scope": cc.scope_of(loaded.stakeholder)},
        "selection": record["selection"],
        "periods": record["periods"],
        "observations": record["observations"],
        "missing_years": record["missing_years"],
        "artifact": record["artifact"],
        "implementation": record["implementation"],
        "presentation": record["presentation"],
    }


def check_document(document, bundle):
    loaded = cc.load_bundle(bundle["bundle"])
    return cc.check_series_block(document, loaded, project_root=ROOT)


# ---------------------------------------------------------------------------
# Recipe interface
# ---------------------------------------------------------------------------

def test_v2_accepts_one_series_trend_instance(tmp_path):
    recipe = publish.load_composition(write_recipe(tmp_path, [
        {"block": "series-trend", "instance_id": "series-0001",
         "topic": "virus", "measure": "cases"}]))
    assert recipe["contract"] == publish.COMPOSITION_CONTRACT_V2
    assert recipe["blocks"] == [{"block": "series-trend", "instance_id": "series-0001",
                                "topic": "virus", "measure": "cases"}]
    assert "series-trend" in publish.KNOWN_BLOCKS


def test_second_series_trend_instance_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Repeated series-trend"):
        publish.load_composition(write_recipe(tmp_path, [
            {"block": "series-trend", "instance_id": "series-0001",
             "topic": "virus", "measure": "cases"},
            {"block": "series-trend", "instance_id": "series-0002",
             "topic": "virus", "measure": "cases", "years": [2022, 2024]}]))


def test_v2_series_entry_with_range_is_valid(tmp_path):
    recipe = publish.load_composition(write_recipe(tmp_path, [
        {"block": "series-trend", "instance_id": "series-0001",
         "topic": "virus", "measure": "cases", "years": [2022, 2024]}]))
    assert recipe["contract"] == publish.COMPOSITION_CONTRACT_V2
    assert recipe["blocks"][0]["years"] == [2022, 2024]


@pytest.mark.parametrize("entry,message", [
    ({"block": "series-trend", "instance_id": "series-0001", "measure": "cases"},
     "Invalid fields"),
    ({"block": "series-trend", "instance_id": "series-0001", "topic": "virus"},
     "Invalid fields"),
    ({"block": "series-trend", "instance_id": "series-0001", "topic": "virus",
      "measure": "cases", "options": {"smooth": True}}, "Invalid fields"),
    ({"block": "series-trend", "instance_id": "series-0001", "topic": "Virus!",
      "measure": "cases"}, "Invalid topic id"),
    ({"block": "series-trend", "instance_id": "series-0001", "topic": "virus",
      "measure": "Cases!"}, "Invalid measure"),
    ({"block": "series-trend", "instance_id": "series-0001", "topic": "virus",
      "measure": "cases", "years": [2025, 2021]}, "start is after end"),
    ({"block": "series-trend", "instance_id": "series-0001", "topic": "virus",
      "measure": "cases", "years": [2021]}, "expected \\[start, end\\] integers"),
    ({"block": "series-trend", "instance_id": "series-0001", "topic": "virus",
      "measure": "cases", "years": [2021.0, 2025]}, "expected \\[start, end\\] integers"),
    ({"block": "series-trend", "instance_id": "series-0001", "topic": "virus",
      "measure": "cases", "years": ["2021", 2025]}, "expected \\[start, end\\] integers"),
])
def test_invalid_series_recipe_entries_are_rejected(tmp_path, entry, message):
    with pytest.raises(ValueError, match=message):
        publish.load_composition(write_recipe(tmp_path, [entry]))


def test_v1_rejects_series_trend(tmp_path):
    with pytest.raises(ValueError, match="requires composition contract"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": "series-trend", "instance_id": "series-0001",
                        "topic": "virus", "measure": "cases"}],
            contract=publish.COMPOSITION_CONTRACT))


# ---------------------------------------------------------------------------
# Binding against saved rows
# ---------------------------------------------------------------------------

def test_default_window_binds_exact_saved_observations(tmp_path):
    record = build(build_series_bundle(tmp_path))
    assert record["status"] == "verified"
    assert record["periods"]["requested"] == [2021, 2025]
    assert record["periods"]["effective"] == [2021, 2022, 2023, 2024, 2025]
    assert record["periods"]["reference_year"] == 2019
    assert record["periods"]["reference_outside_window"] is True
    assert record["missing_years"] == []
    assert [item["value"] for item in record["observations"]] == [
        "6802.0", "7645.0", "6784.0", "8360.0", "8716.0"]
    assert all(item["count_metric_id"] == f"virus:{item['year']}:count"
               for item in record["observations"])
    assert record["selection"]["dataset_id"] == "ds1"
    assert record["artifact"]["file"] == "series.csv"


def test_narrower_range_selects_exact_saved_observations(tmp_path):
    record = build(build_series_bundle(tmp_path), years=[2022, 2024])
    assert record["status"] == "verified"
    assert record["periods"]["requested"] == [2022, 2024]
    assert [item["year"] for item in record["observations"]] == [2022, 2023, 2024]
    assert record["missing_years"] == []


def test_unknown_topic_fails_without_fallback(tmp_path):
    record = build(build_series_bundle(tmp_path), topic="bacterium")
    assert record["status"] == "failed"
    assert record["code"] == "selection"
    assert "bacterium" in record["detail"]
    assert "observations" not in record


def test_excluded_topic_fails_with_recorded_reason(tmp_path):
    record = build(build_series_bundle(tmp_path, selection_status="excluded"))
    assert record["status"] == "failed"
    assert record["code"] == "selection"
    assert "not included" in record["detail"]
    assert "Complete compatible series" in record["detail"]


def test_measure_mismatch_lists_saved_measures(tmp_path):
    record = build(build_series_bundle(tmp_path), measure="consultations")
    assert record["status"] == "failed"
    assert record["code"] == "measure"
    assert "saved measures: ['cases']" in record["detail"]


def test_measure_is_never_silently_substituted(tmp_path):
    record = build(build_series_bundle(tmp_path, measure="cases"), measure="consultations")
    assert record["status"] == "failed"
    assert not record.get("observations")


@pytest.mark.parametrize("years", [[2019, 2025], [2021, 2026], [2020, 2024], [2025, 2021]])
def test_years_outside_the_report_window_or_unordered_fail(tmp_path, years):
    record = build(build_series_bundle(tmp_path), years=years)
    assert record["status"] == "failed"
    assert record["code"] == "periods"


# ---------------------------------------------------------------------------
# Saved series edge cases (synthetic fixtures)
# ---------------------------------------------------------------------------

def test_true_zero_is_preserved(tmp_path):
    rows = [(2019, "7253.0"), (2021, "6802.0"), (2022, "0.0"), (2023, "6784.0"),
            (2024, "8360.0"), (2025, "8716.0")]
    record = build(build_series_bundle(tmp_path, rows), years=[2022, 2022])
    assert record["status"] == "verified"
    assert record["observations"][0]["value"] == "0.0"
    assert record["missing_years"] == []


def test_single_observation_is_allowed_with_explicit_gaps(tmp_path):
    rows = [(2019, "7253.0"), (2022, "7645.0"), (2025, "8716.0")]
    record = build(build_series_bundle(tmp_path, rows), years=[2021, 2023])
    assert record["status"] == "verified"
    assert [item["year"] for item in record["observations"]] == [2022]
    assert record["missing_years"] == [2021, 2023]
    assert record["periods"]["effective"] == [2022]


def test_internal_missing_year_is_explicit(tmp_path):
    rows = [(2019, "7253.0"), (2021, "6802.0"), (2022, "7645.0"),
            (2024, "8360.0"), (2025, "8716.0")]
    record = build(build_series_bundle(tmp_path, rows))
    assert record["status"] == "verified"
    assert record["missing_years"] == [2023]
    assert [item["year"] for item in record["observations"]] == [2021, 2022, 2024, 2025]


def test_missing_endpoint_is_explicit(tmp_path):
    rows = [(2019, "7253.0"), (2021, "6802.0"), (2022, "7645.0"), (2023, "6784.0"),
            (2024, "8360.0")]
    record = build(build_series_bundle(tmp_path, rows))
    assert record["status"] == "verified"
    assert record["missing_years"] == [2025]


def test_range_without_saved_observations_fails(tmp_path):
    rows = [(2019, "7253.0"), (2025, "8716.0")]
    record = build(build_series_bundle(tmp_path, rows), years=[2021, 2024])
    assert record["status"] == "failed"
    assert record["code"] == "selection"
    assert "no saved observations" in record["detail"]


def test_duplicate_topic_year_is_rejected(tmp_path):
    record = build(build_series_bundle(tmp_path, duplicate_year=True), years=[2022, 2022])
    assert record["status"] == "failed"
    assert record["code"] == "duplicate_row"


def test_ambiguous_dataset_is_rejected(tmp_path):
    rows = [(2019, "7253.0"), (2021, "10"), (2022, "11"), (2023, "12"),
            (2024, "13"), (2025, "16")]
    ids = ["ds1", "ds1", "ds2", "ds1", "ds1", "ds1"]
    record = build(build_series_bundle(tmp_path, rows, dataset_ids=ids))
    assert record["status"] == "failed"
    assert record["code"] == "selection_ambiguous"


@pytest.mark.parametrize("value,code", [("inf", "nonfinite"), ("nan", "nonfinite"),
                                        ("abc", "invalid_value")])
def test_nonfinite_or_malformed_saved_value_is_rejected(tmp_path, value, code):
    rows = [(2019, "7253.0"), (2021, value), (2022, "7645.0"), (2023, "6784.0"),
            (2024, "8360.0"), (2025, "8716.0")]
    record = build(build_series_bundle(tmp_path, rows), years=[2021, 2021])
    assert record["status"] == "failed"
    assert record["code"] == code


def test_negative_count_is_rejected(tmp_path):
    rows = [(2019, "7253.0"), (2021, "-5.0"), (2022, "7645.0"), (2023, "6784.0"),
            (2024, "8360.0"), (2025, "8716.0")]
    record = build(build_series_bundle(tmp_path, rows), years=[2021, 2021])
    assert record["status"] == "failed"
    assert record["code"] == "count_value"


def test_mismatched_bound_metric_is_rejected(tmp_path):
    bundle = build_series_bundle(tmp_path)
    document = document_from(build(bundle), bundle)
    document["observations"][0]["count_metric_id"] = "virus:2019:count"
    with pytest.raises(cc.ContractError) as excinfo:
        check_document(document, bundle)
    assert excinfo.value.code == "series_inconsistent"
    assert "series_row" in str(excinfo.value)
    assert "metric_year" in str(excinfo.value)


def test_declared_value_must_match_the_saved_row_and_metric(tmp_path):
    bundle = build_series_bundle(tmp_path)
    document = document_from(build(bundle), bundle)
    document["observations"][0]["value"] = "9999.0"
    with pytest.raises(cc.ContractError) as excinfo:
        check_document(document, bundle)
    assert "series_value_disagreement" in str(excinfo.value)
    assert "metric_value" in str(excinfo.value)


def test_bound_metric_subject_must_match_the_topic(tmp_path):
    bundle = build_series_bundle(tmp_path, extra_topics=(("bacterium", [(2021, "5")]),))
    document = document_from(build(bundle), bundle)
    document["observations"][0]["count_metric_id"] = "bacterium:2021:count"
    with pytest.raises(cc.ContractError) as excinfo:
        check_document(document, bundle)
    assert "metric_subject" in str(excinfo.value)


def test_observation_unit_must_match_the_measure(tmp_path):
    bundle = build_series_bundle(tmp_path)
    document = document_from(build(bundle), bundle)
    document["observations"][0]["unit"] = "percent"
    with pytest.raises(cc.ContractError, match="unit differs from the requested measure"):
        cc.validate_series(document)


def test_omitted_saved_row_in_the_window_is_reported(tmp_path):
    bundle = build_series_bundle(tmp_path)
    document = document_from(build(bundle), bundle)
    removed = document["observations"].pop(1)
    document["periods"]["effective"] = [item["year"] for item in document["observations"]]
    document["missing_years"] = [removed["year"]]
    with pytest.raises(cc.ContractError) as excinfo:
        check_document(document, bundle)
    assert "series_row" in str(excinfo.value)


def test_observation_outside_the_requested_years_is_rejected(tmp_path):
    bundle = build_series_bundle(tmp_path)
    document = document_from(build(bundle), bundle)
    document["periods"]["requested"] = [2022, 2025]
    with pytest.raises(cc.ContractError, match="outside the requested years"):
        cc.validate_series(document)


def test_stale_series_artifact_digest_is_rejected(tmp_path):
    bundle = build_series_bundle(tmp_path)
    assert build(bundle)["status"] == "verified"
    with (bundle["bundle"] / "series.csv").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    record = build(bundle)
    assert record["status"] == "failed"
    assert record["code"] == "series_inconsistent"
    assert "digest_disagreement" in record["detail"]


def test_optional_topic_scope_disagreement_is_reported(tmp_path):
    bundle = build_series_bundle(tmp_path, include_topics=["virus"])
    document = document_from(build(bundle), bundle)
    document["analysis"]["scope"].pop("include_topics")
    with pytest.raises(cc.ContractError) as excinfo:
        check_document(document, bundle)
    assert "scope_disagreement" in str(excinfo.value)


def test_unsorted_observations_are_rejected_structurally(tmp_path):
    bundle = build_series_bundle(tmp_path)
    document = document_from(build(bundle), bundle)
    document["observations"] = list(reversed(document["observations"]))
    document["periods"]["effective"] = [item["year"] for item in document["observations"]]
    with pytest.raises(cc.ContractError, match="ascending year"):
        cc.validate_series(document)


def test_inexplicit_missing_periods_are_rejected_structurally(tmp_path):
    rows = [(2019, "7253.0"), (2021, "10"), (2022, "11"), (2024, "13"), (2025, "16")]
    bundle = build_series_bundle(tmp_path, rows)
    document = document_from(build(bundle), bundle)
    assert document["missing_years"] == [2023]
    document["missing_years"] = []
    with pytest.raises(cc.ContractError, match="missing_years must be exactly"):
        cc.validate_series(document)


# ---------------------------------------------------------------------------
# Identity boundaries
# ---------------------------------------------------------------------------

def test_same_inputs_produce_same_identities(tmp_path):
    bundle = build_series_bundle(tmp_path)
    first = build(bundle)
    second = build(bundle)
    assert first["identities"] == second["identities"]
    assert set(first["identities"]) == {"analytical", "rows", "instance"}


def test_value_change_changes_rows_and_instance_not_analytical(tmp_path):
    first = build(build_series_bundle(tmp_path / "a"))
    rows = list(DEFAULT_ROWS)
    rows[-2] = (2024, "8300.0")
    second = build(build_series_bundle(tmp_path / "b", rows))
    assert first["identities"]["analytical"] == second["identities"]["analytical"]
    assert first["identities"]["rows"] != second["identities"]["rows"]
    assert first["identities"]["instance"] != second["identities"]["instance"]


def test_range_change_changes_instance_identity(tmp_path):
    bundle = build_series_bundle(tmp_path)
    full = build(bundle)
    narrowed = build(bundle, years=[2021, 2024])
    assert full["identities"]["analytical"] == narrowed["identities"]["analytical"]
    assert full["identities"]["rows"] != narrowed["identities"]["rows"]
    assert full["identities"]["instance"] != narrowed["identities"]["instance"]


def test_topic_change_changes_analytical_identity(tmp_path):
    bundle = build_series_bundle(tmp_path, extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),))
    virus = build(bundle)
    other = build(bundle, topic="bacterium")
    assert other["status"] == "verified"
    assert virus["identities"]["analytical"] != other["identities"]["analytical"]


def _render(tmp_path, monkeypatch, bundle, blocks, name="render"):
    work = tmp_path / name
    work.mkdir(parents=True)
    recipe = write_recipe(work, blocks)
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append(list(command))
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    out = work / "report.html"
    sidecar = work / "provenance.json"
    publish.render(bundle["bundle"], out, "html", "quarto",
                   provenance={"schema": "test"}, provenance_out=sidecar,
                   composition=recipe)
    return json.loads(sidecar.read_text())


def test_recipe_reordering_keeps_series_and_reference_identities(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path)
    forward = [{"block": "intro", "instance_id": "intro-0001"},
               {"block": "series-trend", "instance_id": "series-0001",
                "topic": "virus", "measure": "cases"},
               {"block": "reference-comparison", "instance_id": "ref-0001",
                "topic": "virus"}]
    backward = [{"block": "reference-comparison", "instance_id": "ref-0001", "topic": "virus"},
                {"block": "intro", "instance_id": "intro-0001"},
                {"block": "series-trend", "instance_id": "series-0001",
                 "topic": "virus", "measure": "cases"}]
    first = _render(tmp_path, monkeypatch, bundle, forward, "forward")
    second = _render(tmp_path, monkeypatch, bundle, backward, "backward")
    by_id = lambda sidecar: {block["instance_id"]: block for block in sidecar["blocks"]}
    assert by_id(first)["series-0001"]["identities"] == by_id(second)["series-0001"]["identities"]
    assert by_id(first)["ref-0001"]["identities"] == by_id(second)["ref-0001"]["identities"]


def test_adding_series_block_does_not_change_reference_identity(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path)
    reference_only = [{"block": "reference-comparison", "instance_id": "ref-0001",
                       "topic": "virus"}]
    with_series = [{"block": "series-trend", "instance_id": "series-0001",
                    "topic": "virus", "measure": "cases"}] + reference_only
    first = _render(tmp_path, monkeypatch, bundle, reference_only, "ref-only")
    second = _render(tmp_path, monkeypatch, bundle, with_series, "with-series")
    assert first["blocks"][0]["identities"] == second["blocks"][1]["identities"]
    assert first["blocks"][0]["component"]["type"] == "reference-comparison"
    assert second["blocks"][0]["component"]["type"] == "series-trend"


def test_provenance_records_series_instance_and_contract_reference(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path, rows=[(2019, "7253.0"), (2021, "10"),
                                                (2023, "14"), (2025, "16")])
    sidecar = _render(tmp_path, monkeypatch, bundle, [
        {"block": "series-trend", "instance_id": "series-0001",
         "topic": "virus", "measure": "cases", "years": [2021, 2024]}])
    entry = next(item for item in sidecar["composition"]["instances"]
                 if item["block"] == "series-trend")
    series = next(block for block in sidecar["blocks"]
                  if block["component"]["type"] == "series-trend")
    assert entry["topic"] == "virus" and entry["measure"] == "cases"
    assert entry["requested_years"] == [2021, 2024]
    assert entry["effective_years"] == [2021, 2023]
    assert entry["missing_years"] == [2022, 2024]
    assert entry["contract"] == "health-report/series-component/1"
    assert entry["contract_instance_id"] == "series-0001"
    assert entry["contract_status"] == "verified"
    assert entry["instance_identity"] == series["identities"]["instance"]


def test_failed_series_binding_fails_the_render(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path)
    with pytest.raises(ValueError, match="failed series binding"):
        _render(tmp_path, monkeypatch, bundle, [
            {"block": "series-trend", "instance_id": "series-0001",
             "topic": "bacterium", "measure": "cases"}])
    sidecar = json.loads((tmp_path / "render" / "provenance.json").read_text())
    failed = next(block for block in sidecar["blocks"]
                  if block["component"]["type"] == "series-trend")
    assert failed["status"] == "failed"
    assert failed["code"] == "selection"


# ---------------------------------------------------------------------------
# Closed presentation style (display only; never rows or analytical identity)
# ---------------------------------------------------------------------------

def test_omitted_style_preserves_b2_effective_settings_and_trace(tmp_path):
    record = build(build_series_bundle(tmp_path))
    assert record["status"] == "verified"
    assert record["presentation"] == {"unit": "cases"}
    assert record["effective"] == {"presentation": {"unit": "cases"}}
    assert record["trace"] == [{"field": "presentation.unit", "source": "author",
                                "value": "cases"}]


@pytest.mark.parametrize("style", ["standard", "compact"])
def test_explicit_style_is_recorded_in_settings_and_trace(tmp_path, style):
    record = build(build_series_bundle(tmp_path), presentation={"style": style})
    assert record["status"] == "verified"
    assert record["presentation"] == {"unit": "cases", "style": style}
    assert record["effective"]["presentation"] == {"unit": "cases", "style": style}
    assert {"field": "presentation.style", "source": "author", "value": style} in record["trace"]


def test_style_only_changes_instance_identity(tmp_path):
    bundle = build_series_bundle(tmp_path)
    standard = build(bundle, presentation={"style": "standard"})
    compact = build(bundle, presentation={"style": "compact"})
    assert standard["identities"]["analytical"] == compact["identities"]["analytical"]
    assert standard["identities"]["rows"] == compact["identities"]["rows"]
    assert standard["identities"]["instance"] != compact["identities"]["instance"]


@pytest.mark.parametrize("presentation", [
    {"style": "fancy"},
    {"style": "compact", "font": "large"},
    {"style": None},
    {},
    "compact",
])
def test_recipe_rejects_unknown_or_malformed_presentation(tmp_path, presentation):
    entry = {"block": "series-trend", "instance_id": "series-0001",
             "topic": "virus", "measure": "cases", "presentation": presentation}
    with pytest.raises(ValueError, match="presentation"):
        publish.load_composition(write_recipe(tmp_path, [entry]))


@pytest.mark.parametrize("presentation", [{"style": "fancy"},
                                          {"style": "compact", "font": "large"}])
def test_builder_rejects_invalid_presentation_without_fallback(tmp_path, presentation):
    record = build(build_series_bundle(tmp_path), presentation=presentation)
    assert record["status"] == "failed"
    assert record["code"] == "presentation"
    assert "observations" not in record


def test_implementation_references_cover_builder_contract_and_schema(tmp_path):
    record = build(build_series_bundle(tmp_path))
    implementation = record["implementation"]
    assert set(implementation) == {"analysis", "presentation", "contracts",
                                   "binding", "schema"}
    for role in ("contracts", "binding", "schema"):
        reference = implementation[role]
        assert reference["sha256"] == sha256(ROOT / reference["file"])


def test_tampered_implementation_reference_is_rejected(tmp_path):
    bundle = build_series_bundle(tmp_path)
    document = document_from(build(bundle), bundle)
    document["implementation"]["schema"]["sha256"] = "f" * 64
    with pytest.raises(cc.ContractError) as excinfo:
        check_document(document, bundle)
    assert "digest_disagreement" in str(excinfo.value)


def test_implementation_references_do_not_enter_identities(tmp_path):
    bundle = build_series_bundle(tmp_path)
    record = build(bundle)
    document = document_from(record, bundle)
    trimmed = copy.deepcopy(document)
    for role in ("contracts", "binding", "schema"):
        trimmed["implementation"].pop(role)
    assert check_document(trimmed, bundle).identities == record["identities"]


def test_document_with_unsupported_style_fails_schema_validation(tmp_path):
    bundle = build_series_bundle(tmp_path)
    document = document_from(build(bundle), bundle)
    document["presentation"]["style"] = "fancy"
    with pytest.raises(cc.ContractError, match="style"):
        cc.validate_series(document)


def test_published_provenance_carries_implementation_references(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path)
    sidecar = _render(tmp_path, monkeypatch, bundle, [
        {"block": "series-trend", "instance_id": "series-0001", "topic": "virus",
         "measure": "cases", "presentation": {"style": "compact"}}])
    series = next(block for block in sidecar["blocks"]
                  if block["component"]["type"] == "series-trend")
    assert series["presentation"] == {"unit": "cases", "style": "compact"}
    assert set(series["implementation"]) == {"analysis", "presentation", "contracts",
                                             "binding", "schema"}
    assert series["implementation"]["binding"]["file"] == "scripts/health_pipeline/publish.py"
    entry = next(item for item in sidecar["composition"]["instances"]
                 if item["block"] == "series-trend")
    assert entry["presentation"] == {"style": "compact"}
