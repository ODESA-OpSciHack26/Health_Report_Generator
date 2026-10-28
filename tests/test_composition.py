"""Composition recipe validation and render plumbing."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import publish
from test_composer_contracts import build_bundle

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "scripts" / "health_pipeline" / "config" / "composer" / "compositions" / "researcher.json"


def write_recipe(tmp_path, blocks, **extra):
    payload = {"contract": "health-report/composition-recipe/1", "audience": "researcher",
               "blocks": blocks, **extra}
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(payload))
    return path


def test_researcher_recipe_order_is_data():
    recipe = publish.load_composition(RECIPE)
    assert [entry["block"] for entry in recipe["blocks"]] == [
        "intro", "reference-comparison", "limitations", "reproduction"]
    assert len({entry["instance_id"] for entry in recipe["blocks"]}) == 4


def test_unknown_block_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unknown block type"):
        publish.load_composition(write_recipe(tmp_path, [{"block": "gallery", "instance_id": "i-g"}]))
    assert "gallery" not in publish.KNOWN_BLOCKS


def test_duplicate_instance_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Duplicate block instance id"):
        publish.load_composition(write_recipe(tmp_path, [
            {"block": "intro", "instance_id": "i-same"},
            {"block": "limitations", "instance_id": "i-same"}]))


def test_unknown_recipe_field_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported composition fields"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": "intro", "instance_id": "i-a"}], script="alert(1)"))


def test_empty_recipe_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="non-empty blocks"):
        publish.load_composition(write_recipe(tmp_path, []))


def test_render_passes_recipe_path_only_to_report(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True)
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append(list(command))
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    publish.render(bundle["bundle"], tmp_path / "out" / "report.html", "html", "quarto",
                   provenance={"schema": "test"}, composition=RECIPE)
    report = [c for c in commands if "report.qmd" in c][0]
    methods = [c for c in commands if "methods.qmd" in c][0]
    recipe_args = [arg for arg in report if arg.startswith("block_recipe:")]
    assert len(recipe_args) == 1
    assert Path(recipe_args[0].split(":", 1)[1]).is_absolute()
    assert not any(arg.startswith("block_recipe:") for arg in methods)


def test_legacy_mode_sends_no_recipe(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True)
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append(list(command))
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    publish.render(bundle["bundle"], tmp_path / "out" / "report.html", "html", "quarto",
                   provenance={"schema": "test"})
    assert not any(arg.startswith("block_recipe:") for c in commands for arg in c)


def _capture(tmp_path, monkeypatch, fmt, **kwargs):
    bundle = build_bundle(tmp_path, archive=True)
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append(list(command))
        suffix = command[2].split(".")[0]
        (Path(cwd) / (suffix + "." + fmt)).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    publish.render(bundle["bundle"], tmp_path / "out" / f"report.{fmt}", fmt, "quarto", **kwargs)
    return commands


def test_composed_html_suppresses_alternate_format_offer(tmp_path, monkeypatch):
    commands = _capture(tmp_path, monkeypatch, "html",
                        provenance={"schema": "test"}, composition=RECIPE)
    report = [c for c in commands if "report.qmd" in c][0]
    methods = [c for c in commands if "methods.qmd" in c][0]
    assert ["-M", "format-links:false"] == report[report.index("-M"):report.index("-M") + 2]
    assert "-M" not in methods
    assert any(arg.startswith("block_recipe:") for arg in report)


def test_composed_pdf_is_rejected_before_rendering(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(publish.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(ValueError, match="not supported"):
        publish.render(tmp_path / "bundle", tmp_path / "out" / "report.pdf", "pdf", "quarto",
                       provenance={"schema": "test"}, composition=RECIPE)
    assert called == []


def test_legacy_pdf_is_still_supported(tmp_path, monkeypatch):
    commands = _capture(tmp_path, monkeypatch, "pdf", provenance={"schema": "test"})
    report = [c for c in commands if "report.qmd" in c][0]
    assert "-M" not in report
    assert not any(arg.startswith("block_recipe:") for arg in report)
