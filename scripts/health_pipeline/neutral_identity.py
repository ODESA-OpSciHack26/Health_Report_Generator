"""Neutral effective-request identity for verified reuse.

One canonical, versioned record of everything that can change a neutral package. Job identity,
submission time and output paths are deliberately excluded: they describe a run, not a request.

Source, analysis and render identities stay separate so a caller can explain a miss:
- source      the captured bytes and the confirmed roles;
- analysis    the analysis digest and calculation version;
- composition the ordered sections, instance ids, titles and resolved display settings;
- disclosure  the policy and its two permissions;
- environment the templates, helpers and software that produced the package.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import neutral_display

IDENTITY_SCHEMA = "health-report/neutral-request-identity/1"
IDENTITY_VERSION = 1

# Every retained file that can change a neutral package. Kept explicit so a new template must be
# added deliberately rather than silently escaping reuse identity.
REUSABLE_FILES = (
    "scripts/health_pipeline/publish.py",
    "scripts/health_pipeline/neutral_describe.py",
    "scripts/health_pipeline/neutral_publish.py",
    "scripts/health_pipeline/neutral_library.py",
    "scripts/health_pipeline/neutral_display.py",
    "scripts/health_pipeline/report_shared.qmd",
    "scripts/health_pipeline/templates/report_helpers.R",
    "scripts/health_pipeline/templates/methods.qmd",
    "scripts/health_pipeline/templates/dashboard.css",
    "scripts/health_pipeline/config/composer/block-labels.json",
)


def canonical_digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str | None:
    path = Path(path)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment(project_root: Path, *, software: dict | None = None,
                workflow_config_sha256: str | None = None) -> dict:
    """Renderer/template/software identity, computed from content every time."""
    root = Path(project_root)
    return {
        "version": IDENTITY_VERSION,
        "files": {relative: file_digest(root / relative) for relative in REUSABLE_FILES},
        "software": dict(software or {}),
        "workflow_config_sha256": workflow_config_sha256,
    }


def normalised_recipe(recipe: dict) -> dict:
    """Canonical composition: resolved display settings, titles only for present sections.

    Resolution matters: an omitted display field must mean the same thing on both sides of a
    comparison, and a later default change must not reinterpret a saved request.
    """
    blocks = []
    for entry in recipe.get("blocks") or []:
        item = {"block": entry["block"], "instance_id": entry["instance_id"]}
        if "time_period" in entry:
            item["time_period"] = entry["time_period"]
        if entry["block"] in neutral_display.CAPABILITIES:
            item["display"] = neutral_display.resolve(entry["block"], entry.get("display"))
        blocks.append(item)
    titles = recipe.get("titles") or {}
    present = {entry["instance_id"] for entry in blocks}
    return {"contract": recipe.get("contract"), "audience": recipe.get("audience"),
            "blocks": blocks,
            "titles": {key: titles[key] for key in sorted(titles) if key in present}}


def analysis_identity(analysis: dict) -> dict:
    return {"digest": canonical_digest(analysis),
            "calc_version": (analysis.get("method") or {}).get("calc_version"),
            "schema": analysis.get("schema")}


def request_identity(*, recipe: dict, analysis: dict, interpretation: dict,
                     dataset: dict, environment_record: dict) -> dict:
    """The canonical record; its digest is the reuse key."""
    composition = normalised_recipe(recipe)
    return {
        "schema": IDENTITY_SCHEMA,
        "version": IDENTITY_VERSION,
        "mode": "csv",
        "format": "html",
        "source": {
            "digest": dataset.get("input_sha256"),
            "filename": dataset.get("source_filename"),
            "interpretation": {
                "category": (interpretation or {}).get("category"),
                "measure": (interpretation or {}).get("measure"),
                "time": (interpretation or {}).get("time"),
                "missing_tokens": sorted((interpretation or {}).get("missing_tokens") or []),
            },
        },
        "analysis": analysis_identity(analysis),
        "composition": composition,
        "disclosure": {
            "policy": (recipe.get("disclosure") or {}).get("policy"),
            "permit_values": bool((recipe.get("disclosure") or {}).get("permit_values")),
            "permit_records": bool((recipe.get("disclosure") or {}).get("permit_records")),
        },
        "environment": environment_record,
    }


def reuse_key(identity: dict) -> str:
    return canonical_digest(identity)


def difference(left: dict, right: dict) -> list[str]:
    """Which identity areas differ, for a reader-facing miss reason."""
    areas = ("source", "analysis", "composition", "disclosure", "environment")
    return [area for area in areas if left.get(area) != right.get(area)]
