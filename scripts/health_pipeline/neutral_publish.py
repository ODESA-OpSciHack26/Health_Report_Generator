"""Neutral provenance record builder for composed neutral reports.

Separate from the health block builders on purpose: neutral blocks read the saved
neutral analysis (neutral-analysis.json inside the dataset directory) and produce their
own checked records. Records carry analytical and instance identities derived from the
saved analysis digest, never from recipe position.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import neutral_describe as nd

NEUTRAL_PROFILE = "neutral-overview"


def _digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_neutral_bundle(bundle: Path):
    """(dataset, interpretation, prepared, analysis) from a neutral dataset directory."""
    analysis = json.loads((bundle / "neutral-analysis.json").read_text(encoding="utf-8"))
    prepared = json.loads((bundle / "prepared.json").read_text(encoding="utf-8"))
    dataset = json.loads((bundle / "dataset.json").read_text(encoding="utf-8"))
    interpretation = json.loads((bundle / "interpretation.json").read_text(encoding="utf-8"))
    return dataset, interpretation, prepared, analysis


def _instance_identity(tag, values) -> str:
    digest = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"{tag}:{digest[:16]}"


def _analysis_digest(analysis: dict) -> str:
    return _digest_bytes(
        json.dumps(analysis, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _code_reference(project_root: Path, relative: str) -> dict:
    path = project_root / relative
    if not path.is_file():
        return {"file": relative, "sha256": None}
    return {"file": relative, "sha256": _digest_bytes(path.read_bytes())}


def build_data_overview_record(bundle: Path, project_root: Path, instance_id: str,
                               analysis: dict, prepared: dict, dataset: dict) -> dict:
    """One checked data-overview record over the saved neutral analysis."""
    digest = _analysis_digest(analysis)
    selection_rows = list(prepared["rows"])
    values = [row["value"] for row in selection_rows]
    bounds = {"rows": len(selection_rows), "selected": analysis["row_count"],
              "missing": analysis["missing"]}
    record = {
        "schema": "health-report/neutral-block/1",
        "component": {"type": "data-overview", "version": 1},
        "instance_id": instance_id,
        "status": "verified",
        "subject": dataset.get("source_filename"),
        "analysis_digest": digest,
        "interpretation": {
            "category": analysis["interpretation"].get("category"),
            "measure": analysis["interpretation"].get("measure"),
            "time": analysis["interpretation"].get("time"),
            "measure_label": analysis["measure"]["label"],
            "unit": analysis["measure"]["unit"],
            "meaning": analysis["measure"]["meaning"],
        },
        "result": {
            "availability": "available",
            "rows": bounds["selected"],
            "groups": analysis["group_count"],
            "coverage": {
                "columns": len(analysis["source"].get("columns", []))
                if isinstance(analysis.get("source"), dict) else None,
                "rows": bounds["selected"],
                "groups": analysis["group_count"],
                "period_count": analysis["time"]["period_count"]
                if analysis["time"] else None,
            },
        },
        "selected": {"rows": [row["ordinal"] for row in selection_rows]},
        "identities": {
            "analytical": _instance_identity("neutral-analytical/1", {
                "measure": analysis["interpretation"].get("measure"),
                "missing_tokens": analysis["interpretation"].get("missing_tokens", []),
                "analysis_digest": digest}),
            "instance": _instance_identity("neutral-data-overview-instance/1", {
                "component": "data-overview", "instance_id": instance_id}),
        },
        "reproduction": {
            "entry_point": "python scripts/health_pipeline/publish.py html --bundle <captured-dataset> --composition <recipe>",
            "notes": "Renders the saved neutral analysis; the captured file and pinned environment are required."},
        "implementation": {"analysis": _code_reference(project_root, "scripts/health_pipeline/neutral_describe.py"),
                           "presentation": _code_reference(project_root, "scripts/health_pipeline/templates/report_helpers.R")},
    }
    return record


def build_values_record(bundle: Path, project_root: Path, instance_id: str, block: str,
                        analysis: dict, disclosure: dict | None = None) -> dict:
    """One checked values-by-group / values-over-time record.

    The record never restates the observed values; it states that the block resolved against
    the saved analysis and whether the recorded policy publishes numbers.
    """
    digest = _analysis_digest(analysis)
    groups = analysis["groups"]
    record = {
        "schema": "health-report/neutral-block/1",
        "component": {"type": block, "version": 1},
        "instance_id": instance_id,
        "status": "verified",
        "subject": analysis["measure"]["label"],
        "analysis_digest": digest,
        "result": {
            "availability": "available",
            "values_published": bool((disclosure or {}).get("permit_values")),
            "groups": len(groups),
            "period_count": analysis["time"]["period_count"] if block == "values-over-time"
            else None,
            "repeated_group_period_keys": analysis["quality"]["repeated_group_period_keys"],
        },
        "identities": {
            "analytical": _instance_identity(f"neutral-{block}/1",
                                             {"analysis_digest": digest}),
            "instance": _instance_identity(f"neutral-{block}-instance/1",
                                           {"component": block, "instance_id": instance_id}),
        },
        "implementation": {"analysis": _code_reference(project_root, "scripts/health_pipeline/neutral_describe.py"),
                           "presentation": _code_reference(project_root, "scripts/health_pipeline/templates/report_helpers.R")},
    }
    return record


def restricted_analysis(analysis: dict) -> dict:
    """The published analysis record for a restricted shareable export.

    Counts, keys, labels and availability survive; observed values, per-group descriptive
    statistics and per-period values do not. Written under its own schema tag so a consumer
    cannot mistake it for the full saved analysis.
    """
    groups = []
    for group in analysis.get("groups") or []:
        groups.append({
            "group": group.get("group"),
            "n": group.get("n"),
            "observation_periods": [{"period": item.get("period"),
                                     "repeated": item.get("repeated")}
                                    for item in group.get("periods") or []],
            "summary": {"n": (group.get("summary") or {}).get("n")},
        })
    return {
        "schema": "health-report/neutral-restricted-analysis/1",
        "notice": ("Restricted shareable summary: observed values, descriptive statistics and "
                   "contributing records are excluded by the recorded disclosure policy."),
        "interpretation": analysis.get("interpretation"),
        "source": analysis.get("source"),
        "row_count": analysis.get("row_count"),
        "measure": analysis.get("measure"),
        "time": analysis.get("time"),
        "groups": groups,
        "group_count": analysis.get("group_count"),
        "missing": analysis.get("missing"),
        "quality": analysis.get("quality"),
    }


def disclosure_record(disclosure: dict, analysis: dict, prepared: dict,
                      recipe: dict | None = None) -> dict:
    """What the policy puts into this package, stated as evidence semantics.

    Distinguishes the original source, prepared records, selected records, plotted data and
    the permitted export, so a reader can tell what they are looking at without re-deriving
    it from the renderer.
    """
    import neutral_library as nl

    spec = nl.DISCLOSURE_POLICIES[disclosure["policy"]]
    rows = len(prepared.get("rows") or [])
    value_blocks = [entry["block"] for entry in (recipe or {}).get("blocks") or []
                    if entry.get("block") in nl.VALUE_BLOCKS]
    return {
        "schema": nl.DISCLOSURE_SCHEMA,
        "policy": disclosure["policy"],
        "label": spec["label"],
        "permit_values": bool(disclosure["permit_values"]),
        "permit_records": bool(disclosure["permit_records"]),
        "summary": spec["summary"],
        "consequence": spec["detail"],
        "evidence": {
            "original_source": {
                "published": False,
                "location": "private capture store",
                "input_sha256": (analysis.get("source") or {}).get("input_sha256"),
            },
            "prepared_records": {"count": rows, "values_published":
                                 bool(disclosure["permit_values"])},
            "selected_records": {"count": rows,
                                 "published": bool(disclosure["permit_records"]),
                                 "file": "data/selected-records.csv"
                                 if disclosure["permit_records"] else None},
            "plotted_data": {"published": bool(disclosure["permit_values"])},
            "export": {"published": bool(disclosure["permit_records"]),
                       "file": "data/selected-records.csv"
                       if disclosure["permit_records"] else None},
            "analysis_record": ("data/neutral-analysis.json"
                                if disclosure["permit_values"]
                                else "data/neutral-summary.json"),
        },
        "value_blocks": value_blocks,
    }


def composition_provenance(recipe: dict, recipe_path, analysis: dict) -> dict:
    digest = _digest_bytes(json.dumps(
        recipe, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {
        "contract": recipe.get("contract"),
        "audience": recipe.get("audience"),
        "recipe_path": "not disclosed in the shareable record",
        "recipe_sha256": digest,
        "effective_recipe": recipe.get("blocks"),
        "section_titles": dict(recipe.get("titles") or {}),
        "instances": [{"block": entry["block"], "instance_id": entry["instance_id"]}
                      for entry in recipe.get("blocks") or []],
        "mode": "composed",
        "dataset_digest": (analysis.get("source") or {}).get("input_sha256"),
        "analysis_schema": analysis.get("schema"),
        "disclosure": (recipe.get("disclosure") or None),
    }


def build_neutral_provenance(bundle: Path, recipe: dict, recipe_path,
                             project_root: Path, *, input_kind: str = "neutral") -> dict:
    """Provenance for a neutral composed render: blocks + composition + dataset passport.

    Only the blocks present in the recipe get records, mirroring the health path: intro,
    limitations and reproduction are shell sections without their own records; data blocks
    resolve from the saved analysis.
    """
    bundle = Path(bundle)
    dataset, interpretation, prepared, analysis = load_neutral_bundle(bundle)
    records = []
    for entry in recipe.get("blocks") or []:
        block = entry["block"]
        if block == "data-overview":
            records.append(build_data_overview_record(
                bundle, project_root, entry["instance_id"], analysis, prepared, dataset))
        elif block in ("values-by-group", "values-over-time"):
            records.append(build_values_record(
                bundle, project_root, entry["instance_id"], block, analysis,
                recipe.get("disclosure")))
    return {
        "dataset": {
            "kind": "neutral",
            "source_filename": dataset.get("source_filename"),
            "input_sha256": dataset.get("input_sha256"),
            "captured_at_utc": dataset.get("captured_at_utc"),
            "row_meaning": interpretation.get("meaning"),
            "unit": interpretation.get("unit"),
            "measure_label": interpretation.get("measure_label"),
        },
        "interpretation": dict(interpretation),
        "blocks": records,
        "composition": composition_provenance(recipe, recipe_path, analysis),
        "input_kind": input_kind,
        "neutral": True,
    }
