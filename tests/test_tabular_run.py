"""One-command orchestration tests reuse the mocked renderer fixture."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/health_pipeline"))

import tabular_run as runner  # noqa: E402
from tabular_render import verify_tabular_reports  # noqa: E402
from test_tabular_render import fake_quarto as _fake_quarto  # noqa: E402

fake_quarto = _fake_quarto


def inputs(tmp_path, mode="timeseries"):
    source = tmp_path / "input.csv"
    source.write_text("category,value,date\nAlpha,10,2023-01-01\nBeta,,\n")
    mapping = {"category": "category", "measure": "value"}
    if mode == "timeseries":
        mapping["time"] = "date"
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "schema": runner.REQUEST_SCHEMA,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "mapping": mapping, "mode": mode,
        "period": "year" if mode == "timeseries" else None,
    }))
    return source, request


@pytest.mark.parametrize("mode", ["snapshot", "timeseries"])
def test_one_command_produces_verified_three_audience_set(tmp_path, fake_quarto, mode):
    source, request = inputs(tmp_path, mode)
    destination = tmp_path / "new-parent" / "reports"
    runner.run_tabular(source, request, destination)
    verify_tabular_reports(destination)
    assert len(fake_quarto) == 6
    assert (destination / "bundle/source.csv").read_bytes() == source.read_bytes()
    assert not list(destination.parent.glob(".*.run-*"))


@pytest.mark.parametrize("attack", ["hash", "mode", "extra", "schema", "mapping"])
def test_bad_request_blocks_renderer_and_publication(tmp_path, monkeypatch, attack):
    source, request = inputs(tmp_path)
    data = json.loads(request.read_text())
    if attack == "hash":
        data["source_sha256"] = "0" * 64
    elif attack == "mode":
        data["mode"] = "auto"
    elif attack == "extra":
        data["unknown"] = True
    elif attack == "schema":
        data["schema"] = "future"
    else:
        data["mapping"]["measure"] = "absent"
    request.write_text(json.dumps(data))
    def forbidden(*args, **kwargs):
        raise AssertionError("Renderer should not run")
    monkeypatch.setattr(runner, "render_tabular_reports", forbidden)
    destination = tmp_path / "absent-parent/reports"
    with pytest.raises(ValueError):
        runner.run_tabular(source, request, destination)
    assert not destination.parent.exists()


def test_failure_leaves_no_output_and_preserves_input(tmp_path, monkeypatch):
    source, request = inputs(tmp_path)
    before = source.read_bytes()
    def fail(*args, **kwargs):
        raise RuntimeError("render failure")
    monkeypatch.setattr(runner, "render_tabular_reports", fail)
    with pytest.raises(RuntimeError):
        runner.run_tabular(source, request, tmp_path / "out")
    assert source.read_bytes() == before
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".*.run-*"))


def test_existing_output_preserved(tmp_path, fake_quarto):
    source, request = inputs(tmp_path)
    destination = tmp_path / "out"
    destination.mkdir()
    (destination / "sentinel").write_text("keep")
    with pytest.raises(FileExistsError):
        runner.run_tabular(source, request, destination)
    assert (destination / "sentinel").read_text() == "keep"
    assert not fake_quarto


def test_request_duplicate_keys_rejected(tmp_path):
    path = tmp_path / "request.json"
    path.write_text('{"schema":1,"schema":2}')
    with pytest.raises(ValueError):
        runner.load_request(path)


def test_checked_in_example_request_pins_exact_bytes():
    root = ROOT / "examples/tabular"
    request = runner.load_request(root / "request.json")
    assert request["source_sha256"] == hashlib.sha256((root / "observations.csv").read_bytes()).hexdigest()


def test_documented_paths_exist():
    for name in ["docs/m4-tabular-reproduction.md", "docs/m4-browser-review.md",
                 "scripts/health_pipeline/evidence_archive.py"]:
        assert (ROOT / name).is_file()
