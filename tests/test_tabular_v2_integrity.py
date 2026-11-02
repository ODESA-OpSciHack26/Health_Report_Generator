"""v2 artifacts from the retired Python pilot renderer stay integrity-verifiable.

The R release keeps read-only integrity checking for those packages without importing the
pilot renderer, matplotlib or the pilot locks. Source verification against this checkout is
not possible and must fail explicitly rather than pretend to succeed.
"""
import hashlib
import json
import platform
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/health_pipeline"))

import tabular_render as renderer  # noqa: E402
import tabular_bundle as bundles  # noqa: E402
from tabular_describe import describe  # noqa: E402
from tabular_prepare import prepare_table  # noqa: E402


def _identity():
    return {"schema": "health-report/source-identity/1", "origin": "host-supplied",
            "verification": "supplied-digest-match", "commit": "0" * 40, "tree": "1" * 40,
            "tracked_dirty": True, "staged_count": 0, "unstaged_count": 1,
            "untracked_inputs": 1, "untracked_outside_inputs": 0,
            "content": {"roots": ["scripts"], "count": 3, "digest": "a" * 64},
            "collected_at_utc": "2026-01-01T00:00:00+00:00",
            "limits": "synthetic fixture: host-reported fields are not verified"}


def _record():
    return {"schema": renderer.SCHEMA_V2,
            "rendered_at_utc": "2026-01-01T00:05:00+00:00",
            "software": {"python": platform.python_version(), "quarto": "1.3.353",
                         "matplotlib": "3.11.2", "R": "not used"},
            "code": {"source_identity": _identity()},
            "stakeholder": {"id": "researcher"}}


def _write_manifest(root):
    names = sorted(path.relative_to(root).as_posix()
                   for path in root.rglob("*")
                   if path.is_file() and path.name != "render_manifest.json")
    manifest = {"schema": renderer.SCHEMA_V2,
                "artifacts": {name: {"bytes": (root / name).stat().st_size,
                                     "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
                              for name in names}}
    (root / "render_manifest.json").write_bytes(bundles._json_bytes(manifest))


def _v2_tree(tmp_path):
    """A minimal well-formed v2 package, built without any pilot renderer code."""
    source = tmp_path / "input.csv"
    source.write_text('group,amount,date\nAlpha,10,2023-01-01\nBeta,5,2024-01-01\n')
    prepared = prepare_table(source, mapping={"category": "group", "measure": "amount",
                                              "time": "date"},
                             mode="timeseries", period="year")
    root = tmp_path / "v2-report"
    root.mkdir()
    bundles.publish_prepared_bundle(prepared, root / "bundle")
    analysis = describe(prepared, None)
    (root / "analysis.json").write_bytes(bundles._json_bytes(analysis))
    record = _record()
    embedded = json.dumps(record).replace("</", "<\\/")
    for audience in renderer.AUDIENCES:
        folder = root / audience
        folder.mkdir()
        (folder / "provenance.json").write_bytes(bundles._json_bytes(record))
        for document in ("report", "methods"):
            (folder / f"{document}.html").write_text(
                f'<div data-tabular-audience="{audience}"><script>var x="table-filter";</script>'
                f'<script type="application/json" id="report-provenance">{embedded}</script>',
                encoding="utf-8")
    _write_manifest(root)
    return root


def test_v2_integrity_verification_succeeds_without_pilot_code(tmp_path):
    manifest = renderer.verify_tabular_reports(_v2_tree(tmp_path))
    assert manifest["schema"] == renderer.SCHEMA_V2


def test_v2_integrity_verification_detects_a_tampered_artifact(tmp_path):
    report = _v2_tree(tmp_path)
    (report / "public" / "report.html").write_text("changed after rendering", encoding="utf-8")
    with pytest.raises(ValueError, match="hash or size mismatch"):
        renderer.verify_tabular_reports(report)


def test_v2_integrity_verification_rejects_a_broken_identity_block(tmp_path):
    report = _v2_tree(tmp_path)
    record = _record()
    record["code"]["source_identity"].pop("content")
    embedded = json.dumps(record).replace("</", "<\\/")
    for audience in renderer.AUDIENCES:
        (report / audience / "provenance.json").write_bytes(bundles._json_bytes(record))
        for document in ("report", "methods"):
            (report / audience / f"{document}.html").write_text(
                f'<div data-tabular-audience="{audience}"><script>var x="table-filter";</script>'
                f'<script type="application/json" id="report-provenance">{embedded}</script>',
                encoding="utf-8")
    _write_manifest(report)
    with pytest.raises(ValueError, match="source-identity"):
        renderer.verify_tabular_reports(report)


def test_v2_source_verification_fails_explicitly(tmp_path):
    with pytest.raises(ValueError, match="retired Python pilot renderer"):
        renderer.verify_tabular_reports(_v2_tree(tmp_path), verify_source=True)


def test_v2_integrity_path_does_not_depend_on_pilot_modules():
    source = Path(renderer.__file__).read_text(encoding="utf-8")
    for name in ("import pilot_document", "import pilot_charts", "import tabular_python",
                 "import matplotlib", "from matplotlib", "requirements.pilot"):
        assert name not in source, name
    assert "SCHEMA_V2" in source
