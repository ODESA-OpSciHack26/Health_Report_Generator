"""Saved-record composite blocks: coverage, monitoring and sensitivity bindings.

Fixtures here are synthetic and labelled as such; they are not findings in the retained
data. Group totals are written as saved values so the builders never recalculate a count.
"""
import copy
import csv
import json
from pathlib import Path

import pytest

import composer_contracts as cc
import publish
from test_composer_contracts import sha256
from test_composer_series import (ROOT, _render, build_series_bundle, write_recipe)


def _rewrite(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _refresh_manifest(bundle, *names):
    bundle_dir = bundle["bundle"]
    manifest = json.loads((bundle_dir / "bundle.json").read_text())
    for name in names:
        manifest["files"][name] = sha256(bundle_dir / name)
    (bundle_dir / "bundle.json").write_text(json.dumps(manifest))


def add_group_specs(bundle):
    """Append saved main/sensitivity group totals and reference changes."""
    path = bundle["bundle"] / "metrics.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    years = [2019, 2021, 2022, 2023, 2024, 2025]
    virus_members = [f"virus:{year}:count" for year in years]
    main_members = virus_members + ["bacterium:2025:count"]

    def total(subject, value, members):
        for year, amount in ((2019, "7253.0" if "main" in subject else "7253.0"),
                             (2025, value)):
            rows.append({"metric_id": f"{subject}:{year}:total", "metric_type": "group_total",
                         "subject": subject, "year": year, "unit": "cases",
                         "value": amount, "formula": "sum", "inputs_json": json.dumps(members)})

    total("viral:main", "8716.0", main_members)
    total("viral:sensitivity", "8600.0", virus_members)
    for subject, value in (("viral:main", "20.2"), ("viral:sensitivity", "18.6")):
        rows.append({"metric_id": f"{subject}:reference_change",
                     "metric_type": "reference_change", "subject": subject, "year": 2025,
                     "unit": "percent", "value": value, "formula": "percent_change",
                     "inputs_json": json.dumps([f"{subject}:2019:total",
                                                f"{subject}:2025:total"])})
    _rewrite(path, rows)
    _refresh_manifest(bundle, "metrics.csv")
    return bundle


def add_sources(bundle, used="true"):
    path = bundle["bundle"] / "sources.csv"
    rows = [{"dataset_id": "ds1", "topic": "virus",
             "source_system": "mandatory_reporting_system", "used": used,
             "source_file": "data/virus/data.csv", "sha256": "b" * 64,
             "metadata_sha256": "c" * 64}]
    _rewrite(path, rows)
    _refresh_manifest(bundle, "sources.csv")
    return bundle


def add_excluded_topic(bundle, topic="measles", reason="No explicit CHFL total"):
    path = bundle["bundle"] / "selection.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rows.append({"dataset_id": f"ds-{topic}", "topic": topic,
                 "source_system": "mandatory_reporting_system", "status": "excluded",
                 "reason": reason, "group_eligible": "False"})
    _rewrite(path, rows)
    _refresh_manifest(bundle, "selection.csv")
    return bundle


def add_ghost_topic(bundle, topic="ghost"):
    """An included topic with no saved annual series rows."""
    path = bundle["bundle"] / "selection.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rows.append({"dataset_id": f"ds-{topic}", "topic": topic,
                 "source_system": "mandatory_reporting_system", "status": "included",
                 "reason": "Included dataset without annual series rows",
                 "group_eligible": "False"})
    _rewrite(path, rows)
    _refresh_manifest(bundle, "selection.csv")
    return bundle


# ---------------------------------------------------------------------------
# Recipe interface
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("block", publish.COMPOSITE_BLOCKS)
def test_composite_blocks_are_accepted_in_v2_only(tmp_path, block):
    recipe = publish.load_composition(write_recipe(
        tmp_path, [{"block": block, "instance_id": f"{block}-0001"}]))
    assert recipe["contract"] == publish.COMPOSITION_CONTRACT_V2
    with pytest.raises(ValueError, match="requires composition contract"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": block, "instance_id": f"{block}-0001"}],
            contract=publish.COMPOSITION_CONTRACT))


@pytest.mark.parametrize("block", publish.COMPOSITE_BLOCKS)
def test_composite_blocks_take_no_extra_fields(tmp_path, block):
    with pytest.raises(ValueError, match="Invalid fields"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": block, "instance_id": f"{block}-0001",
                        "topic": "virus"}]))


# ---------------------------------------------------------------------------
# Coverage / selection
# ---------------------------------------------------------------------------

def test_coverage_counts_datasets_topics_and_observations_separately(tmp_path):
    bundle = add_sources(add_excluded_topic(build_series_bundle(
        tmp_path, extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),))))
    record = publish.build_coverage_block(bundle["bundle"], ROOT, "cov-0001", ["virus"])
    assert record["status"] == "verified"
    counts = record["counts"]
    assert counts["datasets_total"] == 3
    assert counts["datasets_included"] == 2
    assert counts["datasets_excluded"] == 1
    assert counts["topics_included"] == 2
    assert counts["topics_excluded"] == 1
    assert counts["observations_total"] == 8
    assert counts["observations_in_window"] == 7
    assert counts["source_registry_rows"] == 1
    assert counts["topics_group_sum"] == 2
    assert record["displayed_topics"] == ["virus"]
    assert record["excluded"] == [{"topic": "measles",
                                   "reasons": ["No explicit CHFL total"]}]
    assert any("per-year coverage" in text for text in record["unsupported"])


def test_coverage_displayed_topics_come_from_bindings_not_series(tmp_path):
    bundle = add_sources(build_series_bundle(
        tmp_path, extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),)))
    record = publish.build_coverage_block(bundle["bundle"], ROOT, "cov-0001", ["bacterium"])
    assert record["displayed_topics"] == ["bacterium"]
    assert record["counts"]["topics_included"] == 2


def test_coverage_rejects_a_displayed_topic_outside_the_selection(tmp_path):
    bundle = add_sources(build_series_bundle(tmp_path))
    record = publish.build_coverage_block(bundle["bundle"], ROOT, "cov-0001", ["measles"])
    assert record["status"] == "failed"
    assert record["code"] == "selection"
    assert "measles" in record["detail"]


def test_coverage_fails_when_the_selection_record_is_empty(tmp_path):
    bundle = add_sources(build_series_bundle(tmp_path))
    path = bundle["bundle"] / "selection.csv"
    path.write_text("dataset_id,topic,source_system,status,reason,group_eligible\n")
    _refresh_manifest(bundle, "selection.csv")
    record = publish.build_coverage_block(bundle["bundle"], ROOT, "cov-0001")
    assert record["status"] == "failed"
    assert record["code"] == "selection"


# ---------------------------------------------------------------------------
# Monitoring overview
# ---------------------------------------------------------------------------

def test_monitoring_rows_bind_latest_saved_values_and_comparisons(tmp_path):
    bundle = build_series_bundle(tmp_path,
                                 extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),))
    record = publish.build_monitoring_block(bundle["bundle"], ROOT, "mon-0001")
    assert record["status"] == "verified"
    rows = {row["topic"]: row for row in record["rows"]}
    assert rows["virus"]["latest_year"] == 2025
    assert rows["virus"]["latest_value"] == "8716.0"
    assert rows["virus"]["latest_metric_id"] == "virus:2025:count"
    kinds = {item["type"]: item for item in rows["virus"]["comparisons"]}
    assert set(kinds) == {"reference_change"}
    assert kinds["reference_change"]["from_year"] == "2019"
    assert kinds["reference_change"]["to_year"] == "2025"
    assert kinds["reference_change"]["value"] == "20.170963739142426"
    assert rows["bacterium"]["latest_value"] == "9"
    assert record["units"] == ["cases"]


def test_monitoring_marks_an_included_topic_without_observations(tmp_path):
    bundle = add_ghost_topic(build_series_bundle(tmp_path))
    record = publish.build_monitoring_block(bundle["bundle"], ROOT, "mon-0001")
    assert record["status"] == "verified"
    row = next(item for item in record["rows"] if item["topic"] == "ghost")
    assert row["availability"] == "no saved annual observation"
    assert row["latest_value"] is None
    assert row["comparisons"] == []


# ---------------------------------------------------------------------------
# Sensitivity comparison
# ---------------------------------------------------------------------------

def test_sensitivity_pairs_saved_specifications_and_members(tmp_path):
    bundle = add_group_specs(build_series_bundle(
        tmp_path, extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),)))
    record = publish.build_sensitivity_block(bundle["bundle"], ROOT, "sens-0001")
    assert record["status"] == "verified"
    assert [pair["class"] for pair in record["pairs"]] == ["viral"]
    pair = record["pairs"][0]
    main, sensitivity = pair["specifications"]
    assert main["role"] == "main" and sensitivity["role"] == "sensitivity"
    assert main["reference_change"]["value"] == "20.2"
    assert sensitivity["reference_change"]["value"] == "18.6"
    assert main["reference"]["value"] == "7253.0"
    assert main["latest"]["value"] == "8716.0"
    assert "bacterium" in main["members"]
    assert "bacterium" not in sensitivity["members"]
    assert pair["excluded_members"] == ["bacterium"]
    assert pair["added_members"] == []
    assert pair["identical_members"] is False
    assert main["member_metric_ids"] and "bacterium:2025:count" in main["member_metric_ids"]
    assert main["artifact"]["file"] == "metrics.csv"
    assert len(main["artifact"]["digest"]) == 64
    assert "virus:2019:count" in main["reference_member_metric_ids"]
    assert "bacterium:2025:count" in main["latest_member_metric_ids"]


def test_sensitivity_fails_without_both_specifications(tmp_path):
    bundle = add_group_specs(build_series_bundle(tmp_path))
    path = bundle["bundle"] / "metrics.csv"
    rows = [row for row in csv.DictReader(path.open(encoding="utf-8"))
            if row["subject"] != "viral:sensitivity"]
    _rewrite(path, rows)
    _refresh_manifest(bundle, "metrics.csv")
    record = publish.build_sensitivity_block(bundle["bundle"], ROOT, "sens-0001")
    assert record["status"] == "failed"
    assert record["code"] == "selection"


def test_coverage_reports_group_summaries_separately_from_individual_topics(tmp_path):
    bundle = add_sources(add_group_specs(build_series_bundle(
        tmp_path, extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),))))
    record = publish.build_coverage_block(bundle["bundle"], ROOT, "cov-0001", ["virus"], True)
    assert record["status"] == "verified"
    assert record["displayed_topics"] == ["virus"]
    assert {item["subject"] for item in record["displayed_groups"]} == {
        "viral:main", "viral:sensitivity"}
    main = next(item for item in record["displayed_groups"]
                if item["specification"] == "main")
    assert "bacterium" in main["members"]


def test_coverage_without_group_scope_names_no_group_summary(tmp_path):
    bundle = add_sources(build_series_bundle(tmp_path))
    record = publish.build_coverage_block(bundle["bundle"], ROOT, "cov-0001", ["virus"])
    assert record["displayed_groups"] == []


def test_sensitivity_identical_specifications_are_reported_as_identical(tmp_path):
    bundle = add_group_specs(build_series_bundle(
        tmp_path, extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),)))
    path = bundle["bundle"] / "metrics.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for row in rows:
        if row["subject"] == "viral:main" and row["metric_type"] == "group_total":
            row["inputs_json"] = json.dumps([f"virus:{y}:count" for y in (2019, 2021, 2022, 2023, 2024, 2025)])
            if row["year"] == "2025":
                row["value"] = "8600.0"
        if row["subject"] == "viral:main" and row["metric_type"] == "reference_change":
            row["value"] = "18.6"
    _rewrite(path, rows)
    _refresh_manifest(bundle, "metrics.csv")
    record = publish.build_sensitivity_block(bundle["bundle"], ROOT, "sens-0001")
    assert record["status"] == "verified"
    pair = record["pairs"][0]
    assert pair["identical_members"] is True
    assert pair["identical_results"] is True
    assert pair["excluded_members"] == []


# ---------------------------------------------------------------------------
# Composition wiring and failure propagation
# ---------------------------------------------------------------------------

def test_failed_composite_binding_fails_the_render(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path, selection_status="excluded")
    with pytest.raises(ValueError, match="failed saved-record binding"):
        _render(tmp_path, monkeypatch, bundle, [
            {"block": "monitoring-overview", "instance_id": "mon-0001"}])
    sidecar = json.loads((tmp_path / "render" / "provenance.json").read_text())
    failed = next(block for block in sidecar["blocks"]
                  if block["component"]["type"] == "monitoring-overview")
    assert failed["status"] == "failed"


def test_composites_are_recorded_in_provenance_with_typed_entries(tmp_path, monkeypatch):
    bundle = add_sources(add_group_specs(build_series_bundle(
        tmp_path, extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),))))
    sidecar = _render(tmp_path, monkeypatch, bundle, [
        {"block": "series-trend", "instance_id": "series-0001",
         "topic": "virus", "measure": "cases"},
        {"block": "coverage-selection", "instance_id": "cov-0001"},
        {"block": "monitoring-overview", "instance_id": "mon-0001"},
        {"block": "sensitivity-comparison", "instance_id": "sens-0001"}])
    types = {block["component"]["type"] for block in sidecar["blocks"]}
    assert {"series-trend", "coverage-selection", "monitoring-overview",
            "sensitivity-comparison"} <= types
    coverage = next(block for block in sidecar["blocks"]
                    if block["component"]["type"] == "coverage-selection")
    assert coverage["displayed_topics"] == ["virus"]
    for block in sidecar["blocks"]:
        assert set(block["implementation"]) >= {"contracts", "binding", "presentation"}


# ---------------------------------------------------------------------------
# Reference-comparison provenance (cross-cutting)
# ---------------------------------------------------------------------------

def test_reference_evidence_records_implementation_references(tmp_path):
    bundle = build_series_bundle(tmp_path)
    record = publish.build_block(bundle["bundle"], bundle["results"], ROOT,
                                 "ref-0001", "virus")
    assert record["status"] == "verified"
    assert set(record["implementation"]) == {"analysis", "presentation", "contracts",
                                             "binding", "schema"}
    for role in ("contracts", "binding", "schema"):
        reference = record["implementation"][role]
        assert reference["sha256"] == sha256(ROOT / reference["file"])


def test_reference_implementation_digests_do_not_change_identities(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path)
    first = publish.build_block(bundle["bundle"], bundle["results"], ROOT, "ref-0001", "virus")
    monkeypatch.setattr(publish, "_code_reference",
                        lambda relative: {"file": relative, "sha256": "f" * 64})
    second = publish.build_block(bundle["bundle"], bundle["results"], ROOT, "ref-0001", "virus")
    assert second["status"] == "verified"
    assert first["identities"] == second["identities"]


def test_monitoring_comparison_endpoints_bind_saved_count_metrics(tmp_path):
    bundle = build_series_bundle(tmp_path)
    record = publish.build_monitoring_block(bundle["bundle"], ROOT, "mon-0001")
    comparison = record["rows"][0]["comparisons"][0]
    metrics = {row["metric_id"]: row
               for row in csv.DictReader((bundle["bundle"] / "metrics.csv").open(encoding="utf-8"))}
    assert comparison["reference"]["metric_id"] == "virus:2019:count"
    assert comparison["reference"]["value"] == metrics["virus:2019:count"]["value"]
    assert int(comparison["reference"]["year"]) == 2019
    assert comparison["latest"]["value"] == metrics["virus:2025:count"]["value"]
    assert int(comparison["latest"]["year"]) == 2025
    assert comparison["value"] == metrics["virus:reference_change"]["value"]


def test_monitoring_instance_identity_tracks_comparison_bindings(tmp_path):
    bundle = build_series_bundle(tmp_path)
    record = publish.build_monitoring_block(bundle["bundle"], ROOT, "mon-0001")
    analytical = record["identities"]["analytical"]
    base = publish._monitoring_instance_identity(analytical, "mon-0001", record["rows"])
    assert base == record["identities"]["instance"]
    changed = copy.deepcopy(record["rows"])
    changed[0]["comparisons"][0]["value"] = "999"
    assert publish._monitoring_instance_identity(analytical, "mon-0001", changed) != base
    rebound = copy.deepcopy(record["rows"])
    rebound[0]["comparisons"][0]["metric_id"] = "virus:period_change"
    assert publish._monitoring_instance_identity(analytical, "mon-0001", rebound) != base
    dropped = copy.deepcopy(record["rows"])
    dropped[0]["comparisons"] = []
    assert publish._monitoring_instance_identity(analytical, "mon-0001", dropped) != base


def test_resolved_scope_merges_standalone_and_monitoring_topics(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path,
                                 extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),))
    sidecar = _render(tmp_path, monkeypatch, bundle, [
        {"block": "monitoring-overview", "instance_id": "mon-0001"},
        {"block": "series-trend", "instance_id": "series-0001",
         "topic": "virus", "measure": "cases"}])
    scope = sidecar["composition"]["display_scope"]
    assert scope["standalone_topics"] == ["virus"]
    assert scope["monitoring_topics"] == ["bacterium", "virus"]
    assert scope["displayed_topics"] == ["bacterium", "virus"]
    assert sidecar["composition"]["effective_title"] == "Notifiable disease monitoring overview"
    assert sidecar["composition"]["effective_subtitle"] == "Switzerland and Liechtenstein · Virus focus"


def test_institutional_scope_derives_monitoring_title_and_subtitle(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path,
                                 extra_topics=(("bacterium", [(2021, "5"), (2025, "9")]),))
    sidecar = _render(tmp_path, monkeypatch, bundle, [
        {"block": "monitoring-overview", "instance_id": "mon-0001"},
        {"block": "series-trend", "instance_id": "series-0001",
         "topic": "virus", "measure": "cases"}])
    composition = sidecar["composition"]
    assert composition["effective_title"] == "Notifiable disease monitoring overview"
    assert composition["effective_subtitle"].endswith("Virus focus")
    assert "Switzerland and Liechtenstein" in composition["effective_subtitle"]


def test_published_package_carries_effective_recipe_and_reproduction_record(tmp_path, monkeypatch):
    bundle = build_series_bundle(tmp_path)
    sidecar = _render(tmp_path, monkeypatch, bundle, [
        {"block": "reference-comparison", "instance_id": "ref-0001", "topic": "virus"}])
    work = tmp_path / "render"
    recipe = work / "reproduction" / "composition.json"
    record = work / "reproduction" / "reproduction.json"
    assert recipe.is_file() and record.is_file()
    published = json.loads(record.read_text())
    assert published["recipe_sha256"] == sidecar["composition"]["recipe_sha256"]
    assert published["recipe_file"] == "reproduction/composition.json"
    assert published["analysis_bundle_files"] == 6
    assert "uncommitted" in published["source_state"]
    for field in ("rendering_command", "placeholder_note", "required_inputs",
                  "original_analysis", "integrity_example"):
        assert field in published
    assert "--composition" in published["rendering_command"]
    assert "<original-snapshot-root>" in published["rendering_command"]
