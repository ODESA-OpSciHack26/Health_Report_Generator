"""Pilot renderer integration tests (require the frozen pilot environment).

Skipped in the baseline R runtime because matplotlib is intentionally absent there; the
candidate image runs them. This is a pilot-only skip, not a skip of existing behaviour.
"""
import json
import sys
from pathlib import Path

import pytest

matplotlib = pytest.importorskip(
    "matplotlib", reason="pilot renderer requires the frozen pilot environment")

import tabular_describe
import tabular_python
import tabular_render
import tabular_run

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "tabular"


def _context(name):
    request = tabular_run.load_request(FIXTURES / f"{name}.request.json")
    source = next(path for path in (FIXTURES / f"{name}.csv", FIXTURES / f"{name}.tsv")
                  if path.exists())
    prepared = tabular_run.prepare_payload(
        source.read_bytes(), source_filename=source.name, mapping=request["mapping"],
        mode=request["mode"], period=request["period"])
    analysis = tabular_describe.describe(prepared, request.get("report"))
    profile = {"researcher": {"layout": "technical", "display_name": "Researcher"},
               "health_institution": {"layout": "dashboard", "display_name": "Public health"},
               "public": {"layout": "editorial", "display_name": "General public"}}
    return request, prepared, analysis, profile


@pytest.mark.parametrize("fixture", ["f1_ordinary", "f2_snapshot", "f3_missing",
                                     "f5_labels", "f7_zero_negative", "f8_duplicate"])
def test_document_renders_all_audiences_with_saved_analysis(fixture):
    request, prepared, analysis, profiles = _context(fixture)
    for audience, profile in profiles.items():
        context = {"analysis": analysis, "profile": profile,
                   "rows_html": "<div>rows</div>", "parameters": {"period": request["period"]},
                   "audience": audience}
        html = tabular_python.document_html(context, "report")
        assert f'data-tabular-audience="{audience}"' in html
        assert 'id="limitations"' in html and 'id="provenance"' in html
        methods = tabular_python.document_html(context, "methods")
        assert 'id="statistics"' in methods and 'id="comparison-detail"' in methods
        assert "<script>alert(1)</script>" not in html


def test_unicode_and_html_sensitive_labels_are_escaped():
    request, _prepared, analysis, profiles = _context("f5_labels")
    html = tabular_python.document_html(
        {"analysis": analysis, "profile": profiles["researcher"], "rows_html": "<div>rows</div>",
         "parameters": {"period": request["period"]}, "audience": "researcher"}, "report")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "中文类别" in html
    assert "&amp;" in html


def test_python_generation_through_documented_cli(tmp_path):
    output = tmp_path / "candidate"
    tabular_run.main([
        "build", "--input", str(FIXTURES / "f1_ordinary.csv"),
        "--request", str(FIXTURES / "f1_ordinary.request.json"),
        "--output", str(output), "--renderer", "python"])
    manifest = tabular_render.verify_tabular_reports(output)
    assert manifest["schema"] == tabular_render.SCHEMA_V2
    record = json.loads((output / "researcher" / "provenance.json").read_text())
    assert record["schema"] == tabular_render.SCHEMA_V2
    assert record["software"]["R"] == "not used"
    assert record["software"]["matplotlib"] == tabular_render._matplotlib_version()
    assert record["code"]["renderer"]["implementation"] == "python"
    assert record["code"]["source_identity"]["content"]["digest"]
    report = (output / "researcher" / "report.html").read_text()
    assert 'id="research-statistics"' in report
    assert "data:image/png;base64," in report
    assert "table-filter" in report


def test_v2_integrity_rejects_tampered_artifact_without_source_check(tmp_path):
    output = tmp_path / "candidate"
    tabular_run.main([
        "build", "--input", str(FIXTURES / "f2_snapshot.csv"),
        "--request", str(FIXTURES / "f2_snapshot.request.json"),
        "--output", str(output), "--renderer", "python"])
    target = output / "researcher" / "report.html"
    target.write_text(target.read_text() + "<!--tampered-->")
    with pytest.raises(ValueError, match="artifact hash or size mismatch"):
        tabular_render.verify_tabular_reports(output)


def test_invalid_identity_fails_before_rendering(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise ValueError("the supplied source identity does not describe the files")

    monkeypatch.setattr(tabular_render.source_identity, "resolve", refuse)
    output = tmp_path / "candidate"
    with pytest.raises(ValueError, match="does not describe"):
        tabular_run.run_tabular(FIXTURES / "f2_snapshot.csv",
                                FIXTURES / "f2_snapshot.request.json", output,
                                renderer="python")
    assert not output.exists()
