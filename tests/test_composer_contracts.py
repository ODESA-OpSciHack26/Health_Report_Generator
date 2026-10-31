"""G1 contract tests: structure, resolution and read-only consistency.

These tests never calculate the comparison. Hand-specified expected values come from the
existing analysis contract (10 -> 16 is +60%, 0 baseline is unavailable, 0 latest is
-100%). Two fixture kinds are kept apart on purpose:

* ``tests/fixtures/composer/valid`` and ``.../invalid`` are *structural* documents. Their
  content-addressed fields (snapshot id, plotted digest, code digests) are placeholders,
  so they are never examples of a verified bundle.
* Reference-resolution cases build a small real bundle in ``tmp_path`` and fill the real
  digests before resolution, so those cases do exercise filesystem consistency.
"""
import copy
import csv
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

import composer_contracts as cc
import tabular_run

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "composer"
PLACEHOLDER = "0" * 64
SNAPSHOT_ID = "a" * 64
ANALYSIS_SOURCE = ROOT / "scripts" / "health_pipeline" / "analyse.py"
PRESENTATION_SOURCE = ROOT / "scripts" / "health_pipeline" / "templates" / "report_helpers.R"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def _write_csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_bundle(tmp_path, *, reference="10", latest="16", result="60.0",
                 selection_status="included", metric_overrides=None,
                 lineage_overrides=None, archive=False, stakeholder_overrides=None,
                 reference_year=2019, selection_rows=None):
    """Build a small saved bundle. Values are strings exactly as the CSV stores them."""
    results = tmp_path / "results"
    bundle = results / "reports" / "researcher" / "data"
    bundle.mkdir(parents=True)
    scope = read_fixture("valid/instance.json")["analysis"]["scope"]
    stakeholder = {"id": "test", "title": "Test report", "question": "Q?",
                   "outputs": ["change_table"],
                   "presentation": {"display_name": "Test", "layout": "technical",
                                    "detail_level": "full", "version": "1.0"}}
    stakeholder.update(scope)
    stakeholder.update(stakeholder_overrides or {})
    ry = reference_year

    metrics = [
        {"metric_id": f"virus:{ry}:count", "metric_type": "count", "subject": "virus",
         "year": ry, "unit": "cases", "value": reference, "formula": "raw_sum",
         "inputs_json": "[]"},
        {"metric_id": "virus:2025:count", "metric_type": "count", "subject": "virus",
         "year": 2025, "unit": "cases", "value": latest, "formula": "raw_sum",
         "inputs_json": "[]"},
        {"metric_id": "virus:reference_change", "metric_type": "reference_change",
         "subject": "virus", "year": 2025, "unit": "percent", "value": result,
         "formula": "percent_change",
         "inputs_json": json.dumps([f"virus:{ry}:count", "virus:2025:count"])},
    ]
    for metric_id, changes in (metric_overrides or {}).items():
        for row in metrics:
            if row["metric_id"] == metric_id:
                row.update(changes)

    series = [
        {"topic": "virus", "label": "Virus", "pathogen_class": "viral",
         "dataset_id": "ds1", "source_system": "mandatory_reporting_system",
         "measure": "cases", "geography": "CHFL", "year": ry, "value": reference,
         "population": 100000, "incidence": 10.0, "count_metric_id": f"virus:{ry}:count",
         "incidence_metric_id": f"virus:{ry}:incidence", "coverage": "complete",
         "aggregation": "reported annual"},
        {"topic": "virus", "label": "Virus", "pathogen_class": "viral",
         "dataset_id": "ds1", "source_system": "mandatory_reporting_system",
         "measure": "cases", "geography": "CHFL", "year": 2025, "value": latest,
         "population": 100000, "incidence": 16.0, "count_metric_id": "virus:2025:count",
         "incidence_metric_id": "virus:2025:incidence", "coverage": "complete",
         "aggregation": "reported annual"},
    ]

    selection = [{"dataset_id": "ds1", "topic": "virus",
                  "source_system": "mandatory_reporting_system",
                  "status": selection_status,
                  "reason": "Complete compatible series; explicit source priority",
                  "group_eligible": "True"}]
    if selection_rows is not None:
        selection = selection_rows

    lineage = [
        {"metric_id": f"virus:{ry}:count", "input_kind": "raw", "input_id": "",
         "source_file": "data/virus/data.csv", "source_row": "2",
         "source_column": "value", "sha256": "b" * 64, "metadata_sha256": "c" * 64},
        {"metric_id": "virus:2025:count", "input_kind": "raw", "input_id": "",
         "source_file": "data/virus/data.csv", "source_row": "3",
         "source_column": "value", "sha256": "b" * 64, "metadata_sha256": "c" * 64},
        {"metric_id": "virus:reference_change", "input_kind": "metric",
         "input_id": f"virus:{ry}:count", "source_file": "", "source_row": "",
         "source_column": "", "sha256": "", "metadata_sha256": ""},
        {"metric_id": "virus:reference_change", "input_kind": "metric",
         "input_id": "virus:2025:count", "source_file": "", "source_row": "",
         "source_column": "", "sha256": "", "metadata_sha256": ""},
    ]
    for metric_id, changes in (lineage_overrides or {}).items():
        for row in lineage:
            if row["metric_id"] == metric_id:
                row.update(changes)

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


def block_documents(bundle, *, instance="valid/instance.json",
                    evidence="valid/evidence.json",
                    patch_instance=None, patch_evidence=None):
    """Structural fixtures plus the real content identities of the generated bundle."""
    instance_doc = read_fixture(instance)
    evidence_doc = read_fixture(evidence)
    instance_doc["analysis"]["snapshot_id"] = SNAPSHOT_ID
    instance_doc["plotted"]["digest"] = sha256(bundle["bundle"] / "series.csv")
    evidence_doc["reproduction"]["snapshot_id"] = SNAPSHOT_ID
    evidence_doc["implementation"]["analysis"]["sha256"] = sha256(ANALYSIS_SOURCE)
    evidence_doc["implementation"]["presentation"]["sha256"] = sha256(PRESENTATION_SOURCE)
    if patch_instance:
        patch_instance(instance_doc)
    if patch_evidence:
        patch_evidence(evidence_doc)
    return instance_doc, evidence_doc


def check(bundle, **kwargs):
    instance_doc, evidence_doc = block_documents(bundle, **kwargs)
    loaded = cc.load_bundle(bundle["bundle"])
    return cc.check_block(instance_doc, evidence_doc, loaded, project_root=ROOT)


def findings(bundle, **kwargs):
    instance_doc, evidence_doc = block_documents(bundle, **kwargs)
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    loaded = cc.load_bundle(bundle["bundle"])
    return cc.verify_references(resolved, loaded, project_root=ROOT)


def codes(items):
    return {item.code for item in items}


def _reversed_keys(value):
    if isinstance(value, dict):
        return {key: _reversed_keys(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reversed_keys(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# Positive resolution against a real, digest-populated bundle
# ---------------------------------------------------------------------------

def test_saved_sixty_percent_resolves(tmp_path):
    bundle = build_bundle(tmp_path)
    record = check(bundle)
    assert record.available is True
    assert record.instance_id == "cmp-0001"
    assert record.effective["presentation"] == {"unit": "percent", "digits": 0}
    assert record.effective["disclosure"] == {"distribution": "public", "initial": "collapsed"}
    trace = {item["field"]: item["source"] for item in record.trace}
    assert trace["presentation.digits"] == "component"
    assert trace["disclosure.initial"] == "component"
    assert trace["presentation.unit"] == "author"
    assert set(record.identities) == {"analytical", "result", "instance"}
    assert all(len(value) == 64 for value in record.identities.values())


def test_zero_reference_stays_unavailable(tmp_path):
    bundle = build_bundle(tmp_path, reference="0", result="")
    record = check(bundle, evidence="valid/evidence-unavailable.json")
    assert record.available is False
    assert findings(bundle, evidence="valid/evidence-unavailable.json") == ()


def test_zero_reference_cannot_be_reported_as_zero_percent(tmp_path):
    bundle = build_bundle(tmp_path, reference="0", result="")

    def claim_available(evidence):
        evidence["results"].update(value=0.0, availability="available",
                                   unavailable_reason=None)

    with pytest.raises(cc.ContractError) as error:
        check(bundle, evidence="valid/evidence-unavailable.json",
              patch_evidence=claim_available)
    assert error.value.code == "inconsistent"
    assert "availability_disagreement" in codes(error.value.findings)


def test_zero_latest_is_minus_one_hundred(tmp_path):
    bundle = build_bundle(tmp_path, latest="0", result="-100.0")
    record_kwargs = {"patch_evidence": lambda evidence: evidence["results"].update(value=-100.0)}
    record = check(bundle, **record_kwargs)
    assert record.available is True
    assert findings(bundle, **record_kwargs) == ()


def test_profile_defaults_are_traced_and_only_cosmetic(tmp_path):
    bundle = build_bundle(tmp_path)
    instance_doc, evidence_doc = block_documents(bundle)
    resolved = cc.resolve_instance(instance_doc, evidence_doc, profile={"presentation": {"digits": 1}})
    trace = {item["field"]: item["source"] for item in resolved.trace}
    assert resolved.effective["presentation"]["digits"] == 1
    assert trace["presentation.digits"] == "profile"
    plain = cc.resolve_instance(instance_doc, evidence_doc)
    assert resolved.identities["instance"] != plain.identities["instance"]
    assert resolved.identities["analytical"] == plain.identities["analytical"]
    assert resolved.identities["result"] == plain.identities["result"]


def test_inputs_are_not_mutated(tmp_path):
    bundle = build_bundle(tmp_path)
    instance_doc, evidence_doc = block_documents(bundle)
    before = copy.deepcopy((instance_doc, evidence_doc))
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    assert (instance_doc, evidence_doc) == before
    assert resolved.original_instance == before[0]
    assert resolved.original_instance is not instance_doc
    cc.check_block(instance_doc, evidence_doc, cc.load_bundle(bundle["bundle"]), project_root=ROOT)
    assert (instance_doc, evidence_doc) == before


def test_identities_are_deterministic_and_key_order_independent(tmp_path):
    bundle = build_bundle(tmp_path)
    instance_doc, evidence_doc = block_documents(bundle)
    first = cc.resolve_instance(instance_doc, evidence_doc)
    second = cc.resolve_instance(copy.deepcopy(instance_doc), copy.deepcopy(evidence_doc))
    assert first.identities == second.identities
    reordered = cc.resolve_instance(_reversed_keys(instance_doc), _reversed_keys(evidence_doc))
    assert reordered.identities == first.identities
    assert reordered.trace == first.trace


def test_duplication_changes_display_not_numbers(tmp_path):
    bundle = build_bundle(tmp_path)
    instance_doc, evidence_doc = block_documents(bundle)
    first = cc.resolve_instance(instance_doc, evidence_doc)
    clone_instance = copy.deepcopy(instance_doc)
    clone_evidence = copy.deepcopy(evidence_doc)
    clone_instance["instance_id"] = "cmp-0002"
    clone_evidence["instance_id"] = "cmp-0002"
    second = cc.resolve_instance(clone_instance, clone_evidence)
    assert second.identities["analytical"] == first.identities["analytical"]
    assert second.identities["result"] == first.identities["result"]
    assert second.identities["instance"] != first.identities["instance"]


def test_reordering_changes_composition_identity_only(tmp_path):
    bundle = build_bundle(tmp_path)
    instance_doc, evidence_doc = block_documents(bundle)
    first = cc.resolve_instance(instance_doc, evidence_doc)
    clone_instance = copy.deepcopy(instance_doc)
    clone_evidence = copy.deepcopy(evidence_doc)
    clone_instance["instance_id"] = "cmp-0002"
    clone_evidence["instance_id"] = "cmp-0002"
    second = cc.resolve_instance(clone_instance, clone_evidence)
    forward = {"contract": cc.COMPOSITION_CONTRACT, "composition_id": "comp-0001",
               "instances": ["cmp-0001", "cmp-0002"]}
    backward = {**forward, "instances": ["cmp-0002", "cmp-0001"]}
    one = cc.resolve_composition(forward, [first, second])
    two = cc.resolve_composition(backward, [first, second])
    assert one.identities["composition"] != two.identities["composition"]
    assert one.identities["per_instance"] == two.identities["per_instance"]


def test_composition_rejects_dangling_and_duplicate_ids(tmp_path):
    bundle = build_bundle(tmp_path)
    instance_doc, evidence_doc = block_documents(bundle)
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    dangling = {"contract": cc.COMPOSITION_CONTRACT, "composition_id": "comp-0001",
                "instances": ["cmp-0001", "cmp-9999"]}
    with pytest.raises(cc.ContractError) as error:
        cc.resolve_composition(dangling, [resolved])
    assert error.value.code == "dangling_reference"
    with pytest.raises(cc.ContractError) as error:
        cc.resolve_composition({**dangling, "instances": ["cmp-0001"]}, [resolved, resolved])
    assert error.value.code == "duplicate_instance"
    duplicated = {"contract": cc.COMPOSITION_CONTRACT, "composition_id": "comp-0001",
                  "instances": ["cmp-0001", "cmp-0001"]}
    with pytest.raises(cc.ContractError) as error:
        cc.validate_composition(duplicated)
    assert error.value.code == "duplicate_instance"


# ---------------------------------------------------------------------------
# Structural rejection
# ---------------------------------------------------------------------------

def test_unknown_field_is_rejected():
    with pytest.raises(cc.ContractError) as error:
        cc.validate_instance(read_fixture("invalid/unknown-field.json"))
    assert error.value.code == "schema"


@pytest.mark.parametrize("fixture", ["invalid/unsupported-contract.json",
                                     "invalid/unsupported-component.json"])
def test_unsupported_versions_are_rejected(fixture):
    with pytest.raises(cc.ContractError) as error:
        cc.validate_instance(read_fixture(fixture))
    assert error.value.code == "schema"


@pytest.mark.parametrize("path", ["../etc/passwd", "/etc/passwd", "a/../b", "C:/x",
                                  "a\\b", "x/", "a//b", "./x"])
def test_unsafe_references_are_rejected(tmp_path, path):
    instance_doc, _ = block_documents(build_bundle(tmp_path))
    instance_doc["plotted"]["file"] = path
    with pytest.raises(cc.ContractError) as error:
        cc.validate_instance(instance_doc)
    assert error.value.code == "unsafe_reference"


def test_empty_reference_fails_schema(tmp_path):
    instance_doc, _ = block_documents(build_bundle(tmp_path))
    instance_doc["plotted"]["file"] = ""
    with pytest.raises(cc.ContractError) as error:
        cc.validate_instance(instance_doc)
    assert error.value.code == "schema"


@pytest.mark.parametrize("text,code", [
    ('{"contract": NaN}', "nonfinite"),
    ('{"contract": Infinity}', "nonfinite"),
    ('{"contract": ', "invalid_json"),
    ('{"contract": "a", "contract": "b"}', "duplicate_key"),
])
def test_invalid_json_is_rejected(tmp_path, text, code):
    path = tmp_path / "document.json"
    path.write_text(text)
    with pytest.raises(cc.ContractError) as error:
        cc.load_document(path, "instance")
    assert error.value.code == code


def test_availability_shape_is_enforced():
    evidence = read_fixture("valid/evidence.json")
    evidence["results"].update(value=None)
    with pytest.raises(cc.ContractError) as error:
        cc.validate_evidence(evidence)
    assert error.value.code == "availability"
    evidence = read_fixture("valid/evidence-unavailable.json")
    del evidence["results"]["unavailable_reason"]
    with pytest.raises(cc.ContractError) as error:
        cc.validate_evidence(evidence)
    assert error.value.code == "availability"


# ---------------------------------------------------------------------------
# Scope, metric, selection, lineage and digest consistency
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("geography", "CH"),
    ("years", [2020, 2025]),
    ("dimension_filters", {}),
    ("source_priority", ["mandatory_reporting_system"]),
])
def test_scope_disagreement_is_reported(tmp_path, field, value):
    bundle = build_bundle(tmp_path)

    def mutate(instance_doc):
        instance_doc["analysis"]["scope"][field] = value

    assert "scope_disagreement" in codes(findings(bundle, patch_instance=mutate))


@pytest.mark.parametrize("metric_id,changes,code", [
    ("virus:2025:count", {"metric_type": "group_total"}, "metric_type"),
    ("virus:reference_change", {"formula": "sum"}, "formula_disagreement"),
    ("virus:reference_change", {"inputs_json": '["virus:2025:count","virus:2019:count"]'}, "inputs_disagreement"),
    ("virus:reference_change", {"subject": "bacterium"}, "metric_subject"),
    ("virus:2025:count", {"year": 2024}, "parameter_disagreement"),
])
def test_metric_semantics_are_checked(tmp_path, metric_id, changes, code):
    bundle = build_bundle(tmp_path, metric_overrides={metric_id: changes})
    assert code in codes(findings(bundle))


def test_missing_metric_is_reported(tmp_path):
    bundle = build_bundle(tmp_path)

    def rebind(instance_doc):
        instance_doc["bindings"]["latest_count"] = "virus:2024:count"

    assert "metric_missing" in codes(findings(bundle, patch_instance=rebind))


def test_excluded_selection_is_not_a_success(tmp_path):
    bundle = build_bundle(tmp_path, selection_status="excluded")
    reported = codes(findings(bundle))
    assert "selection_excluded" in reported
    with pytest.raises(cc.ContractError) as error:
        check(bundle)
    assert error.value.code == "inconsistent"


def test_measure_disagreement_is_reported(tmp_path):
    bundle = build_bundle(tmp_path)

    def mutate(evidence_doc):
        evidence_doc["calculation"]["parameters"]["measure"] = "consultations"

    assert "measure_disagreement" in codes(findings(bundle, patch_evidence=mutate))


def test_plotted_digest_disagreement_is_reported(tmp_path):
    bundle = build_bundle(tmp_path)

    def mutate(instance_doc):
        instance_doc["plotted"]["digest"] = "f" * 64

    assert "digest_disagreement" in codes(findings(bundle, patch_instance=mutate))


def test_plotted_row_must_match_saved_series(tmp_path):
    bundle = build_bundle(tmp_path)

    def mutate(instance_doc):
        instance_doc["plotted"]["rows"] = [{"topic": "virus", "year": 2020}]

    assert "plotted_row" in codes(findings(bundle, patch_instance=mutate))


def test_implementation_digest_disagreement_is_reported(tmp_path):
    bundle = build_bundle(tmp_path)

    def mutate(evidence_doc):
        evidence_doc["implementation"]["analysis"]["sha256"] = "f" * 64

    assert "digest_disagreement" in codes(findings(bundle, patch_evidence=mutate))


def test_symlinked_implementation_is_rejected(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    shutil.copy2(PRESENTATION_SOURCE, project / "report_helpers.R")
    os.symlink(ANALYSIS_SOURCE, project / "analyse.py")
    instance_doc, evidence_doc = block_documents(bundle, patch_evidence=lambda evidence: (
        evidence["implementation"]["analysis"].update(file="analyse.py"),
        evidence["implementation"]["presentation"].update(file="report_helpers.R", sha256=sha256(PRESENTATION_SOURCE)),
    ))
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    reported = cc.verify_references(resolved, cc.load_bundle(bundle["bundle"]), project_root=project)
    assert "implementation_missing" in codes(reported)


def test_lineage_checks(tmp_path):
    bundle = build_bundle(tmp_path, lineage_overrides={"virus:2019:count": {"input_id": "missing:2019:count", "input_kind": "metric"}})
    assert "lineage_dangling" in codes(findings(bundle))
    bundle = build_bundle(tmp_path / "b", lineage_overrides={"virus:2019:count": {"sha256": ""}})
    assert "lineage_digest" in codes(findings(bundle))
    bundle = build_bundle(tmp_path / "c", lineage_overrides={"virus:2019:count": {"source_file": "../escape.csv"}})
    assert "unsafe_reference" in codes(findings(bundle))


def test_missing_lineage_row_is_reported(tmp_path):
    bundle = build_bundle(tmp_path)

    def drop(instance_doc):
        pass

    loaded = cc.load_bundle(bundle["bundle"])
    loaded = cc.BundleEvidence(root=loaded.root, stakeholder=loaded.stakeholder,
                               manifest=loaded.manifest, snapshot=loaded.snapshot,
                               metrics=loaded.metrics, series=loaded.series,
                               selection=loaded.selection,
                               lineage=tuple(row for row in loaded.lineage
                                             if row["metric_id"] != "virus:2019:count"))
    instance_doc, evidence_doc = block_documents(bundle)
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    assert "lineage_missing" in codes(cc.verify_references(resolved, loaded, project_root=ROOT))


def test_archived_source_files_are_optional_and_bounded(tmp_path):
    bundle = build_bundle(tmp_path, archive=False)
    instance_doc, evidence_doc = block_documents(bundle)
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    loaded = cc.load_bundle(bundle["bundle"])
    assert "lineage_source_missing" in codes(cc.verify_references(
        resolved, loaded, project_root=ROOT, results_root=bundle["results"]))
    archived = build_bundle(tmp_path / "archived", archive=True)
    instance_doc, evidence_doc = block_documents(archived)
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    loaded = cc.load_bundle(archived["bundle"])
    assert cc.verify_references(resolved, loaded, project_root=ROOT,
                                results_root=archived["results"]) == ()


def test_bundle_loader_requires_its_artifacts(tmp_path):
    bundle = build_bundle(tmp_path)
    (bundle["bundle"] / "lineage.csv").unlink()
    with pytest.raises(cc.ContractError) as error:
        cc.load_bundle(bundle["bundle"])
    assert error.value.code == "bundle"


# ---------------------------------------------------------------------------
# Compatibility with the unchanged tabular request v1/v2 contract
# ---------------------------------------------------------------------------

def test_request_v1_and_v2_remain_accepted(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("category,value,date\nAlpha,10,2023-01-01\n")
    base = {"schema": tabular_run.REQUEST_SCHEMA,
            "source_sha256": sha256(source),
            "mapping": {"category": "category", "measure": "value", "time": "date"},
            "mode": "timeseries", "period": "year"}
    v1 = tmp_path / "v1.json"
    v1.write_text(json.dumps(base))
    assert tabular_run.load_request(v1)["schema"] == "health-report/tabular-request/1"
    v2 = tmp_path / "v2.json"
    v2.write_text(json.dumps({**base, "schema": "health-report/tabular-request/2",
                              "report": {}}))
    assert tabular_run.load_request(v2)["schema"] == "health-report/tabular-request/2"
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({**base, "contract": "health-report/composer-component/1"}))
    with pytest.raises(ValueError):
        tabular_run.load_request(extra)


# ---------------------------------------------------------------------------
# Regression tests for source-review findings R1-R7
# ---------------------------------------------------------------------------

def _refresh_manifest(bundle, extra=None):
    names = ("metrics.csv", "series.csv", "selection.csv", "lineage.csv",
             "snapshot.json", "stakeholder.json")
    files = {name: sha256(bundle / name) for name in names}
    files.update(extra or {})
    (bundle / "bundle.json").write_text(json.dumps({"schema_version": "2.0", "files": files}))
    return files


def test_r1_consumed_artifact_digest_must_match_manifest(tmp_path):
    bundle = build_bundle(tmp_path)
    metrics = bundle["bundle"] / "metrics.csv"
    metrics.write_text(metrics.read_text().replace("60.0", "61.0"))
    assert "digest_disagreement" in codes(findings(bundle))


def test_r1_consumed_artifact_symlink_is_rejected(tmp_path):
    bundle = build_bundle(tmp_path)
    target = bundle["bundle"] / "lineage.csv"
    outside = tmp_path / "outside-lineage.csv"
    shutil.copy2(target, outside)
    target.unlink()
    os.symlink(outside, target)
    reported = codes(findings(bundle))
    assert "artifact_unsafe" in reported


def test_r2_plotted_path_with_symlinked_parent_is_rejected(tmp_path):
    bundle = build_bundle(tmp_path)
    alias = bundle["bundle"] / "alias"
    alias.symlink_to(bundle["bundle"], target_is_directory=True)

    def mutate(instance_doc):
        instance_doc["plotted"]["file"] = "alias/series.csv"

    _refresh_manifest(bundle["bundle"], {"alias/series.csv": sha256(bundle["bundle"] / "series.csv")})
    assert "artifact_unsafe" in codes(findings(bundle, patch_instance=mutate))


def test_r2_snapshot_path_cannot_escape_results_root(tmp_path):
    bundle = build_bundle(tmp_path)
    outside = tmp_path / "outside" / "data" / "virus"
    outside.mkdir(parents=True)
    (outside / "data.csv").write_text("value\n10\n16\n")
    (bundle["bundle"] / "snapshot.json").write_text(json.dumps(
        {"snapshot_id": SNAPSHOT_ID, "snapshot_path": "../outside"}))
    _refresh_manifest(bundle["bundle"])
    instance_doc, evidence_doc = block_documents(bundle)
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    reported = codes(cc.verify_references(resolved, cc.load_bundle(bundle["bundle"]),
                                          project_root=ROOT, results_root=bundle["results"]))
    assert "snapshot_path" in reported


def test_r3_plotted_rows_must_be_exactly_the_bound_pair(tmp_path):
    bundle = build_bundle(tmp_path)

    def mutate(instance_doc):
        instance_doc["plotted"]["rows"] = [
            {"topic": "virus", "year": 2019},
            {"topic": "virus", "year": 2025},
            {"topic": "virus", "year": 2025},
        ]

    assert "plotted_row" in codes(findings(bundle, patch_instance=mutate))


def test_r3_plotted_artifact_must_be_the_series_file(tmp_path):
    bundle = build_bundle(tmp_path)

    def mutate(instance_doc):
        instance_doc["plotted"]["file"] = "metrics.csv"
        instance_doc["plotted"]["digest"] = sha256(bundle["bundle"] / "metrics.csv")

    assert "plotted_artifact" in codes(findings(bundle, patch_instance=mutate))


def test_r4_parameters_must_match_saved_scope(tmp_path):
    bundle = build_bundle(tmp_path, reference_year=2018, reference="12", result="33.3")

    def mutate_instance(instance_doc):
        instance_doc["bindings"]["reference_count"] = "virus:2018:count"
        instance_doc["plotted"]["rows"] = [
            {"topic": "virus", "year": 2018},
            {"topic": "virus", "year": 2025},
        ]

    def mutate_evidence(evidence_doc):
        evidence_doc["inputs"]["metric_ids"] = ["virus:2018:count", "virus:2025:count"]
        evidence_doc["calculation"]["parameters"]["reference_year"] = 2018
        evidence_doc["results"]["value"] = 33.3

    reported = codes(findings(bundle, patch_instance=mutate_instance,
                              patch_evidence=mutate_evidence))
    assert "parameter_disagreement" in reported


def test_r5_unavailable_result_must_not_carry_a_value():
    evidence = read_fixture("valid/evidence-unavailable.json")
    evidence["results"]["value"] = 60.0
    with pytest.raises(cc.ContractError) as error:
        cc.validate_evidence(evidence)
    assert error.value.code == "availability"


def test_r5_zero_reference_with_available_result_is_inconsistent(tmp_path):
    bundle = build_bundle(tmp_path, reference="0", result="60.0")

    def claim_available(evidence):
        evidence["results"].update(value=60.0, availability="available",
                                   unavailable_reason=None)

    assert "availability_disagreement" in codes(
        findings(bundle, patch_evidence=claim_available))


def test_r5_bound_count_values_must_be_saved_numbers(tmp_path):
    bundle = build_bundle(tmp_path, metric_overrides={"virus:2019:count": {"value": ""}})
    assert "count_value" in codes(findings(bundle))


@pytest.mark.parametrize("defaults", [
    {"presentation": {"colour": "teal"}},
    {"presentation": {"digits": "two"}},
    {"disclosure": {"initial": "sometimes"}},
])
def test_r6_component_defaults_are_validated(tmp_path, defaults):
    bundle = build_bundle(tmp_path)
    instance_doc, evidence_doc = block_documents(bundle)
    with pytest.raises(cc.ContractError) as error:
        cc.resolve_instance(instance_doc, evidence_doc, component_defaults=defaults)
    assert error.value.code == "defaults"


def test_r7_selection_matches_the_bound_source_not_any_row(tmp_path):
    bundle = build_bundle(tmp_path, selection_rows=[
        {"dataset_id": "ds1", "topic": "virus",
         "source_system": "mandatory_reporting_system", "status": "included",
         "reason": "Complete compatible series; explicit source priority",
         "group_eligible": "True"},
        {"dataset_id": "ds2", "topic": "virus",
         "source_system": "sentinella_reporting_system", "status": "excluded",
         "reason": "Lower-priority source", "group_eligible": "False"},
    ])
    assert findings(bundle) == ()


def test_r7_unsupported_lineage_kind_is_rejected(tmp_path):
    bundle = build_bundle(tmp_path, lineage_overrides={
        "virus:2019:count": {"input_kind": "parquet", "input_id": "external"}})
    assert "lineage_kind" in codes(findings(bundle))


def test_r1_unlisted_consumed_artifact_is_still_checked_for_safety(tmp_path):
    bundle = build_bundle(tmp_path)
    target = bundle["bundle"] / "lineage.csv"
    outside = tmp_path / "outside-lineage.csv"
    shutil.copy2(target, outside)
    target.unlink()
    os.symlink(outside, target)
    manifest_path = bundle["bundle"] / "bundle.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"].pop("lineage.csv")
    manifest_path.write_text(json.dumps(manifest))
    reported = codes(findings(bundle))
    assert "artifact_unsafe" in reported
    assert "artifact_unlisted" in reported


def test_r1_symlinked_bundle_json_is_rejected_before_reading(tmp_path):
    bundle = build_bundle(tmp_path)
    manifest_path = bundle["bundle"] / "bundle.json"
    outside = tmp_path / "bundle-copy.json"
    shutil.copy2(manifest_path, outside)
    manifest_path.unlink()
    os.symlink(outside, manifest_path)
    with pytest.raises(cc.ContractError) as error:
        cc.load_bundle(bundle["bundle"])
    assert error.value.code == "artifact_unsafe"


def test_r1_extra_manifest_entry_with_stale_digest_is_reported(tmp_path):
    bundle = build_bundle(tmp_path)
    (bundle["bundle"] / "notes.txt").write_text("declared but stale\n")
    manifest_path = bundle["bundle"] / "bundle.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["notes.txt"] = "f" * 64
    manifest_path.write_text(json.dumps(manifest))
    assert "digest_disagreement" in codes(findings(bundle))


def test_r1_unsafe_extra_manifest_entry_is_not_read(tmp_path):
    bundle = build_bundle(tmp_path)
    manifest_path = bundle["bundle"] / "bundle.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["../outside.txt"] = "f" * 64
    manifest_path.write_text(json.dumps(manifest))
    assert "artifact_unsafe" in codes(findings(bundle))


def test_r2_symlinked_snapshot_ancestor_is_rejected(tmp_path):
    bundle = build_bundle(tmp_path, archive=False)
    results = bundle["results"]
    real = results / "snapshots-real" / SNAPSHOT_ID / "data" / "virus"
    real.mkdir(parents=True)
    (real / "data.csv").write_text("value\n10\n16\n")
    (results / "snapshots").symlink_to(results / "snapshots-real", target_is_directory=True)
    instance_doc, evidence_doc = block_documents(bundle)
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    reported = codes(cc.verify_references(resolved, cc.load_bundle(bundle["bundle"]),
                                          project_root=ROOT, results_root=results))
    assert "snapshot_path" in reported


def test_r3_series_value_must_match_the_bound_count(tmp_path):
    bundle = build_bundle(tmp_path)
    series = bundle["bundle"] / "series.csv"
    rows = list(csv.DictReader(series.open(newline="", encoding="utf-8")))
    rows[0]["value"] = "999"
    _write_csv(series, list(rows[0]), rows)
    _refresh_manifest(bundle["bundle"])
    assert "series_value_disagreement" in codes(findings(bundle))


def test_r3_series_measure_and_geography_must_match_the_scope(tmp_path):
    bundle = build_bundle(tmp_path)
    series = bundle["bundle"] / "series.csv"
    rows = list(csv.DictReader(series.open(newline="", encoding="utf-8")))
    rows[0]["measure"] = "consultations"
    rows[0]["geography"] = "CH"
    _write_csv(series, list(rows[0]), rows)
    _refresh_manifest(bundle["bundle"])
    reported = codes(findings(bundle))
    assert "series_scope_disagreement" in reported


def test_r6_unknown_profile_section_is_rejected(tmp_path):
    bundle = build_bundle(tmp_path)
    instance_doc, evidence_doc = block_documents(bundle)
    with pytest.raises(cc.ContractError) as error:
        cc.resolve_instance(instance_doc, evidence_doc,
                            profile={"presentations": {"digits": 1}})
    assert error.value.code == "profile"


def test_r7_self_referencing_count_lineage_is_rejected(tmp_path):
    bundle = build_bundle(tmp_path, lineage_overrides={
        "virus:2019:count": {"input_kind": "metric", "input_id": "virus:2019:count"}})
    assert "lineage_unsupported" in codes(findings(bundle))


def test_r7_mutually_referencing_counts_without_raw_provenance_are_rejected(tmp_path):
    bundle = build_bundle(tmp_path, lineage_overrides={
        "virus:2019:count": {"input_kind": "metric", "input_id": "virus:2025:count"},
        "virus:2025:count": {"input_kind": "metric", "input_id": "virus:2019:count"}})
    assert "lineage_unsupported" in codes(findings(bundle))


def test_r7_monthly_raw_rows_for_one_annual_count_remain_valid(tmp_path):
    bundle = build_bundle(tmp_path, lineage_overrides={
        "virus:2019:count": {"source_row": "2"}})
    assert findings(bundle) == ()


# ---------------------------------------------------------------------------
# source_row reader compatibility (R7 follow-up): exact data-record numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source_row", ["521", "521.0", "521.00", "699.0", "2", "2.0"])
def test_source_row_accepts_integer_and_zero_fraction_forms(tmp_path, source_row):
    bundle = build_bundle(tmp_path, lineage_overrides={
        "virus:2019:count": {"source_row": source_row}})
    assert findings(bundle) == ()


@pytest.mark.parametrize("source_row", [
    "0", "1", "1.0", "521.5", "-521", "-521.0", "", "nan", "NaN",
    "Infinity", "5.21e2", "True", "521.",
])
def test_source_row_rejects_invalid_record_numbers(tmp_path, source_row):
    bundle = build_bundle(tmp_path, lineage_overrides={
        "virus:2019:count": {"source_row": source_row}})
    assert "lineage_row" in codes(findings(bundle))


def test_source_row_string_is_preserved_by_the_loader(tmp_path):
    bundle = build_bundle(tmp_path, lineage_overrides={
        "virus:2019:count": {"source_row": "521.00"}})
    loaded = cc.load_bundle(bundle["bundle"])
    rows = [row for row in loaded.lineage if row["metric_id"] == "virus:2019:count"]
    assert len(rows) == 1
    assert rows[0]["source_row"] == "521.00"
    on_disk = [row for row in csv.DictReader((bundle["bundle"] / "lineage.csv").open(newline="", encoding="utf-8"))
               if row["metric_id"] == "virus:2019:count"]
    assert on_disk[0]["source_row"] == "521.00"


def test_multiple_monthly_raw_rows_with_zero_fraction_rows_stay_valid(tmp_path):
    bundle = build_bundle(tmp_path)
    lineage = bundle["bundle"] / "lineage.csv"
    rows = list(csv.DictReader(lineage.open(newline="", encoding="utf-8")))
    header = list(rows[0])
    extra = dict(rows[0])
    extra.update({"input_kind": "raw", "source_row": "12.0", "sha256": "d" * 64})
    rows.append(extra)
    rows[0]["source_row"] = "2.0"
    _write_csv(lineage, header, rows)
    _refresh_manifest(bundle["bundle"])
    assert findings(bundle) == ()


# ---------------------------------------------------------------------------
# Optional report-level topic scope
# ---------------------------------------------------------------------------

def test_optional_topic_scope_present_changes_analytical_identity(tmp_path):
    base = check(build_bundle(tmp_path / "base")).identities["analytical"]
    bundle = build_bundle(tmp_path / "scoped", stakeholder_overrides={"include_topics": ["virus"]})
    instance_doc, evidence_doc = block_documents(
        bundle, patch_instance=lambda d: d["analysis"]["scope"].update(include_topics=["virus"]))
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    assert resolved.identities["analytical"] != base


def test_omitted_topic_scope_is_not_an_empty_inclusion_list(tmp_path):
    base = check(build_bundle(tmp_path / "base")).identities["analytical"]
    bundle = build_bundle(tmp_path / "empty", stakeholder_overrides={"include_topics": []})
    instance_doc, evidence_doc = block_documents(
        bundle, patch_instance=lambda d: d["analysis"]["scope"].update(include_topics=[]))
    resolved = cc.resolve_instance(instance_doc, evidence_doc)
    loaded = cc.load_bundle(bundle["bundle"])
    assert cc.verify_references(resolved, loaded, project_root=ROOT) == ()
    assert resolved.identities["analytical"] != base


def test_topic_scope_order_does_not_change_identity(tmp_path):
    first = build_bundle(tmp_path / "first", stakeholder_overrides={"include_topics": ["virus", "bacterium"]})
    second = build_bundle(tmp_path / "second", stakeholder_overrides={"include_topics": ["bacterium", "virus"]})
    doc_a, ev_a = block_documents(
        first, patch_instance=lambda d: d["analysis"]["scope"].update(include_topics=["bacterium", "virus"]))
    doc_b, ev_b = block_documents(
        second, patch_instance=lambda d: d["analysis"]["scope"].update(include_topics=["virus", "bacterium"]))
    res_a = cc.resolve_instance(doc_a, ev_a)
    res_b = cc.resolve_instance(doc_b, ev_b)
    assert res_a.identities["analytical"] == res_b.identities["analytical"]
    assert cc.verify_references(res_a, cc.load_bundle(first["bundle"]), project_root=ROOT) == ()


def test_optional_scope_omission_mismatch_both_directions(tmp_path):
    # Saved settings restrict scope, instance omits it.
    restricted = build_bundle(tmp_path / "restricted", stakeholder_overrides={"include_topics": ["virus"]})
    assert "scope_disagreement" in codes(findings(restricted))
    # Instance restricts scope, saved settings omit it.
    plain = build_bundle(tmp_path / "plain")

    def add_scope(instance_doc):
        instance_doc["analysis"]["scope"]["include_topics"] = ["virus"]

    assert "scope_disagreement" in codes(findings(plain, patch_instance=add_scope))
