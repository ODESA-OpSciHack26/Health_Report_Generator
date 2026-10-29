"""Block emission at render time: saved records only, explicit evidence path, honest failure."""
import json
import os
import subprocess
from pathlib import Path

import pytest

import publish
from test_composer_contracts import build_bundle

ROOT = Path(__file__).resolve().parents[1]


def block(bundle):
    return publish.build_block(bundle["bundle"], bundle["results"], ROOT)


def test_block_carries_saved_values_and_identities(tmp_path):
    bundle = build_bundle(tmp_path, archive=True)
    record = block(bundle)
    assert record["status"] == "verified"
    assert record["subject"] == "virus"
    assert record["reference_year"] == 2019 and record["latest_year"] == 2025
    assert record["measure"] == "cases"
    assert record["reference_count"] == {"metric_id": "virus:2019:count", "value": "10"}
    assert record["latest_count"] == {"metric_id": "virus:2025:count", "value": "16"}
    assert record["result"]["value"] == 60.0
    assert record["result"]["formula"] == "percent_change"
    assert record["result"]["availability"] == "available"
    assert set(record["identities"]) == {"analytical", "result", "instance"}
    assert record["implementation"]["analysis"]["file"].endswith("analyse.py")
    assert record["lineage"]["source_file"] == "data/virus/data.csv"
    assert record["lineage"]["source_row"] == "2"
    assert record["effective"]["presentation"]["digits"] == 1


def test_block_selection_is_deterministic(tmp_path):
    bundle = build_bundle(tmp_path, archive=True)
    assert block(bundle) == block(bundle)


def test_contract_failure_returns_no_values(tmp_path):
    bundle = build_bundle(tmp_path, archive=True)
    metrics = bundle["bundle"] / "metrics.csv"
    metrics.write_text(metrics.read_text().replace("60.0", "61.0"))
    record = block(bundle)
    assert record["status"] == "failed"
    assert record["code"] == "inconsistent"
    assert "result" not in record and "identities" not in record
    assert any(item["code"] == "digest_disagreement" for item in record["findings"])


def test_render_passes_absolute_evidence_path(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True)
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append((list(command), Path(cwd)))
        target = Path(cwd) / (command[2].replace(".qmd", ".html"))
        target.write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    out = tmp_path / "out" / "report.html"
    publish.render(bundle["bundle"], out, "html", "quarto",
                   provenance={"schema": "test"}, provenance_out=tmp_path / "provenance.json")
    report_commands = [c for c, _ in commands if "report.qmd" in c]
    assert len(report_commands) == 1
    flag = report_commands[0].index("-P")
    evidence_arg = report_commands[0][flag + 1]
    assert evidence_arg.startswith("evidence_file:")
    evidence_path = Path(evidence_arg.split(":", 1)[1])
    assert evidence_path.is_absolute()
    assert evidence_path.name == "provenance.json"
    sidecar = json.loads((tmp_path / "provenance.json").read_text())
    assert sidecar["blocks"][0]["status"] == "verified"
    assert sidecar["blocks"][0]["subject"] == "virus"


def test_methods_render_does_not_receive_evidence_path(tmp_path, monkeypatch):
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
    methods = [c for c in commands if "methods.qmd" in c][0]
    assert not any(arg.startswith("evidence_file:") for arg in methods)
    assert "download_prefix:data/" in methods
