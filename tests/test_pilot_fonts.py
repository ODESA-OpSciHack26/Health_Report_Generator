"""Batch D: packaged CJK chart-font identity, coverage and renderer use."""
import csv
import hashlib
import os
import warnings
from pathlib import Path

import pytest

matplotlib = pytest.importorskip("matplotlib", reason="requires the frozen pilot environment")
fontTools = pytest.importorskip("fontTools", reason="font inspection requires fontTools")

import pilot_charts
import tabular_python
import tabular_render
import tabular_run

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "tabular"
FONT = ROOT / "assets" / "fonts" / "noto-cjk" / "NotoSansCJKsc-Regular.otf"
LICENSE = ROOT / "assets" / "fonts" / "noto-cjk" / "LICENSE.txt"
FONT_SHA256 = "2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b"
LICENSE_SHA256 = "6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2"
EVIDENCE = os.environ.get("TABULAR_FONT_EVIDENCE")


def _record(name, text):
    if EVIDENCE:
        directory = Path(EVIDENCE)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(text, encoding="utf-8")


def _cmap():
    from fontTools.ttLib import TTFont
    font = TTFont(FONT)
    covered = set()
    for table in font["cmap"].tables:
        covered.update(table.cmap)
    return font, covered


def _labels():
    labels = []
    for name in ("f1_ordinary", "f5_labels", "f7_zero_negative"):
        with (FIXTURES / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("category"):
                    labels.append(row["category"])
    labels += ["Observed value", "not specified", "Change from the selected reference (%)",
               "Detailed statistics and methods", "−5", "+21.0%", "Über", "中文类别", "日本語"]
    return labels


def _context(name):
    request = tabular_run.load_request(FIXTURES / f"{name}.request.json")
    payload = (FIXTURES / f"{name}.csv").read_bytes()
    prepared = tabular_run.prepare_payload(
        payload, source_filename=f"{name}.csv", mapping=request["mapping"],
        mode=request["mode"], period=request["period"])
    context = tabular_render._context(prepared, tabular_render._profile("researcher"),
                                      request.get("report"))
    context["audience"] = "researcher"
    return context


def test_packaged_font_and_licence_match_recorded_identity():
    assert FONT.is_file() and LICENSE.is_file()
    assert hashlib.sha256(FONT.read_bytes()).hexdigest() == FONT_SHA256
    assert hashlib.sha256(LICENSE.read_bytes()).hexdigest() == LICENSE_SHA256
    assert FONT.stat().st_size == 16437364
    assert "SIL OPEN FONT LICENSE Version 1.1" in LICENSE.read_text(encoding="utf-8")


def test_font_family_and_cmap_cover_exercised_labels():
    font, covered = _cmap()
    family = [record.toUnicode() for record in font["name"].names if record.nameID == 1][0]
    style = [record.toUnicode() for record in font["name"].names if record.nameID == 2][0]
    assert family == "Noto Sans CJK SC" and style == "Regular"
    missing = sorted({hex(ord(char)) for label in _labels() for char in label
                      if ord(char) > 32 and ord(char) not in covered})
    _record("coverage.txt", f"family={family}\nstyle={style}\ncodepoints={len(covered)}\n"
                            f"labels={len(_labels())}\nmissing={missing}\n")
    assert missing == []


def test_renderer_selects_the_packaged_font_explicitly(monkeypatch):
    path = pilot_charts._font_path()
    assert path == FONT or path == pilot_charts.FONT_IMAGE
    with pilot_charts._font_context(matplotlib):
        assert matplotlib.rcParams["font.family"][0] == "Noto Sans CJK SC"
        assert matplotlib.rcParams["font.sans-serif"][0] == "Noto Sans CJK SC"
    _record("selected-font.txt", f"path={path}\nfamily=Noto Sans CJK SC\n")
    monkeypatch.setenv("HEALTH_REPORT_PILOT_FONT", str(FONT.with_name("missing.otf")))
    with pytest.raises(Exception, match="configured pilot font is missing"):
        pilot_charts._font_path()


def test_real_chart_generation_has_no_missing_glyph_warnings():
    context = _context("f5_labels")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plots = pilot_charts.graphs(context["analysis"], technical=True)
    missing = [str(item.message) for item in caught
               if "missing from font" in str(item.message).lower()]
    _record("warnings.txt", "\n".join(str(item.message) for item in caught) + "\n")
    assert plots
    assert missing == []


def test_html_text_captions_and_alt_text_remain_intact():
    context = _context("f5_labels")
    html = tabular_python.document_html(context, "report")
    assert "中文类别" in html
    assert "Über-Ärztliche-Überwachungsstelle-für-sehr-lange-Bezeichnungen" in html
    assert "Detailed statistics and methods" in html
    assert 'alt="Observed values in the supplied periods"' in html
    assert 'alt="Distribution diagnostic"' in html
