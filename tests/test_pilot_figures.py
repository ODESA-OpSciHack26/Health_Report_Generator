"""Batch C: figure placeholder-and-restore contract tests.

Pure unit tests exercise pilot_document.figure/restore_figures. The real-Quarto test renders
the actual supplied-table context with multiple figures and inspects intermediate and final HTML.
The caller-failure test injects a restoration exception; it is exception cleanup, not process
interruption coverage.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import pilot_document as doc
import tabular_python

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "tabular"
FIGURE_EVIDENCE = os.environ.get("TABULAR_FIGURE_EVIDENCE")
MARKER = re.compile(r'<div data-pilot-figure="(\d+)">\s*</div>')


def _fig(registry, png, title, note):
    return doc.figure(png, title, note, registry=registry)


def _save(name, text):
    if FIGURE_EVIDENCE:
        directory = Path(FIGURE_EVIDENCE)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(text, encoding="utf-8")


def test_single_figure_restored_once_in_document_order():
    registry = {}
    marker = _fig(registry, b"one", "First title", "First note")
    rendered = f"<p>before</p>{marker}<p>after</p>"
    assert MARKER.findall(rendered) == ["0"]
    final = doc.restore_figures(rendered, registry)
    assert "data-pilot-figure" not in final
    assert final.count('<figure class="report-figure">') == 1
    assert final.index("before") < final.index("First title") < final.index("after")
    assert 'alt="First title"' in final and "First note" in final


def test_multiple_figures_keep_order_and_appear_exactly_once():
    registry = {}
    first = _fig(registry, b"one", "First title", "First note")
    second = _fig(registry, b"two", "Second title", "Second note")
    rendered = f"<section>{first}</section><section>{second}</section>"
    assert MARKER.findall(rendered) == ["0", "1"]
    final = doc.restore_figures(rendered, registry)
    assert final.count('<figure class="report-figure">') == 2
    assert final.count('alt="First title"') == 1
    assert final.count('alt="Second title"') == 1
    assert final.index("First title") < final.index("Second title")
    assert "data-pilot-figure" not in final


def test_captions_alt_text_escaping_and_unicode_survive_round_trip():
    registry = {}
    title = '<script>"quoted" & ünïcode 中文'
    note = 'Note <b>bold</b> & "quotes" — very long ' + "x" * 300
    marker = _fig(registry, b"bytes", title, note)
    final = doc.restore_figures(marker, registry)
    assert "&lt;script&gt;" in final and "<script>" not in final
    assert "&quot;quoted&quot;" in final and "&amp;" in final
    assert "ünïcode 中文" in final
    assert "Note &lt;b&gt;bold&lt;/b&gt;" in final
    assert "Detailed statistics and methods" in final
    assert 'src="data:image/png;base64,Ynl0ZXM="' in final


@pytest.mark.parametrize("spacing", ["", "\n", "\n  ", "\t \n "])
def test_matcher_supports_its_documented_whitespace_variation(spacing):
    registry = {}
    marker = _fig(registry, b"one", "Title", "Note")
    varied = marker.replace("></div>", f">{spacing}</div>")
    final = doc.restore_figures(varied, registry)
    assert 'alt="Title"' in final


def test_missing_placeholder_raises():
    registry = {}
    _fig(registry, b"one", "Title", "Note")
    with pytest.raises(doc.PilotDocumentError, match="was not preserved"):
        doc.restore_figures("<p>no marker</p>", registry)


def test_duplicate_placeholder_raises():
    registry = {}
    marker = _fig(registry, b"one", "Title", "Note")
    with pytest.raises(doc.PilotDocumentError, match="was not preserved"):
        doc.restore_figures(marker + marker, registry)


def test_no_figure_document_is_unchanged():
    rendered = "<section id=\"x\"><h2>No figures</h2><p>Text</p></section>"
    assert doc.restore_figures(rendered, {}) == rendered
    assert "data-pilot-figure" not in rendered


def test_registries_are_isolated_per_document():
    one, two = {}, {}
    marker_one = _fig(one, b"1", "Doc one title", "note")
    marker_two = _fig(two, b"2", "Doc two title", "note")
    assert doc.restore_figures(marker_one, one).count("Doc one title") == 1
    assert doc.restore_figures(marker_two, two).count("Doc two title") == 1
    # Characterisation, not endorsement: tokens restart at 0 per document, so using the wrong
    # registry silently substitutes the other document's markup. The caller always pairs them.
    crossed = doc.restore_figures(marker_two, one)
    assert "Doc one title" in crossed and "Doc two title" not in crossed


def test_literal_marker_collision_is_rejected_as_duplicate():
    registry = {}
    marker = _fig(registry, b"one", "Title", "Note")
    with pytest.raises(doc.PilotDocumentError, match="was not preserved"):
        doc.restore_figures(marker + '<div data-pilot-figure="0"></div>', registry)


def test_methods_document_has_no_figure_placeholders():
    from test_pilot_document import _analysis

    context = {"analysis": _analysis(),
               "profile": {"layout": "technical", "display_name": "Researcher"},
               "rows_html": "", "parameters": {"period": "year"},
               "audience": "researcher"}
    registry = {}
    qmd = tabular_python.quarto_document(context, "methods", {"schema": "test"},
                                         figures=registry)
    assert registry == {}
    assert "data-pilot-figure" not in qmd


def _fixture_context():
    import tabular_render
    import tabular_run

    request = tabular_run.load_request(FIXTURES / "f1_ordinary.request.json")
    payload = (FIXTURES / "f1_ordinary.csv").read_bytes()
    prepared = tabular_run.prepare_payload(
        payload, source_filename="f1_ordinary.csv", mapping=request["mapping"],
        mode=request["mode"], period=request["period"])
    context = tabular_render._context(prepared, tabular_render._profile("researcher"),
                                      request.get("report"))
    context["audience"] = "researcher"
    return context


@pytest.mark.quarto_runtime
def test_real_quarto_restores_multiple_figures_and_shows_intermediate_placeholders(tmp_path):
    if shutil.which("quarto") is None:
        pytest.skip("real-Quarto integration requires the B2 image")
    context = _fixture_context()
    registry = {}
    qmd = tabular_python.quarto_document(context, "report", {"schema": "test"},
                                         figures=registry)
    assert len(registry) > 1
    shutil.copyfile(ROOT / "scripts" / "health_pipeline" / "templates" / "dashboard.css",
                    tmp_path / "dashboard.css")
    (tmp_path / "report.qmd").write_text(qmd, encoding="utf-8")
    completed = subprocess.run(["quarto", "render", "report.qmd", "--to", "html",
                                "--output", "report.html"],
                               cwd=tmp_path, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    intermediate = (tmp_path / "report.html").read_text(encoding="utf-8")
    markers = MARKER.findall(intermediate)
    assert markers == [str(index) for index in range(len(registry))]
    assert '<figure class="report-figure">' not in intermediate
    final = doc.restore_figures(intermediate, registry)
    assert "data-pilot-figure" not in final
    assert final.count('<figure class="report-figure">') == len(registry)
    assert final.count("Detailed statistics and methods") == len(registry)
    assert final.count("data:image/png;base64,") == 2 * len(registry)
    _save("intermediate-report.html", intermediate)
    _save("final-report.html", final)
    _save("figure-titles.json", json.dumps(list(registry.values()), indent=1))


@pytest.mark.quarto_runtime
def test_caller_does_not_publish_when_restoration_fails(tmp_path, monkeypatch):
    pytest.importorskip("matplotlib", reason="requires the frozen pilot environment")
    import tabular_run

    destination = tmp_path / "destination"

    def refuse(*args, **kwargs):
        raise doc.PilotDocumentError("injected restoration failure")

    monkeypatch.setattr(tabular_python.doc, "restore_figures", refuse)
    with pytest.raises(doc.PilotDocumentError, match="injected restoration failure"):
        tabular_run.run_tabular(FIXTURES / "f1_ordinary.csv",
                                FIXTURES / "f1_ordinary.request.json",
                                destination, renderer="python")
    leftovers = sorted(str(path) for path in tmp_path.glob(".*"))
    _save("caller-failure.txt",
          f"destination_exists={destination.exists()} leftovers={leftovers}")
    assert not destination.exists()
    assert not list(tmp_path.glob(".*.run-*"))
    assert not list(tmp_path.glob(".*.staging-*"))
