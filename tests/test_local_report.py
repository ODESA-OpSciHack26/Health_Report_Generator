"""Local execution must reuse the container backend without GitHub dispatch."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "local_report", ROOT / "src/local_report.py"
)
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


@pytest.fixture
def backend(tmp_path, monkeypatch):
    source = tmp_path / "scripts/health_pipeline/config/stakeholders"
    source.mkdir(parents=True)
    original = ROOT / "scripts/health_pipeline/config/stakeholders"
    for audience in local.AUDIENCES:
        (source / f"{audience}.json").write_bytes(
            (original / f"{audience}.json").read_bytes()
        )
    monkeypatch.setattr(local, "ROOT", tmp_path)
    return tmp_path


def test_container_backend_preserves_request_and_uses_safe_arguments(
    backend, monkeypatch
):
    seen = {}
    key = "a" * 64

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        out = backend / command[command.index("--out") + 1]
        out.mkdir(parents=True)
        for name in ("report.html", "methods.html", "provenance.json"):
            (out / name).write_text("fixture")
        (out / "request_provenance.json").write_text(
            json.dumps({"cache_key": key})
        )
        kwargs["stdout"].write(f"cache miss: key={key} -> {out}\n")

    monkeypatch.setattr(local.subprocess, "run", fake_run)
    result = local.run_request("public_health_expert", 2022, 2025)

    request = json.loads(result["request"].read_text())
    original = json.loads((
        backend / "scripts/health_pipeline/config/stakeholders/"
        "public_health_expert.json"
    ).read_text())
    assert request == {
        **original,
        "years": [2022, 2025],
        "title": "Notifiable disease report for Public health expert: 2022–2025",
        "question": (
            "What do the notified-disease data show for 2022–2025 in Switzerland "
            "and Liechtenstein, using 2019 as the comparison year and 2019 "
            "as the index baseline?"
        ),
    }
    assert result["status"] == "miss"
    assert result["cache_key"] == key
    assert seen["command"][:7] == [
        "docker", "compose", "run", "--rm", "-T", "report", "env"
    ]
    assert "scripts/health_pipeline/custom_report.py" in seen["command"]
    assert seen["kwargs"]["check"] is True
    assert "shell" not in seen["kwargs"]


@pytest.mark.parametrize("audience,start,end", [
    ("../../public", 2021, 2025),
    ("public", 2025, 2021),
    ("public", 2020, 2025),
    ("public", 2021, 2026),
    ("public", True, 2025),
])
def test_invalid_input_cannot_launch_container(
    backend, monkeypatch, audience, start, end
):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid input launched a process.")

    monkeypatch.setattr(local.subprocess, "run", forbidden)
    with pytest.raises(ValueError):
        local.run_request(audience, start, end)
    assert not (backend / "results").exists()


def test_process_failure_is_not_reported_as_success(backend, monkeypatch):
    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(local.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="Local rendering failed"):
        local.run_request("public", 2021, 2025)


def test_successful_exit_without_outputs_is_rejected(backend, monkeypatch):
    monkeypatch.setattr(local.subprocess, "run", lambda *a, **kw: None)
    with pytest.raises(RuntimeError, match="complete result"):
        local.run_request("public", 2021, 2025)


@pytest.mark.parametrize("audience", local.AUDIENCES)
@pytest.mark.parametrize("start,end", [(2023, 2024), (2024, 2024), (2021, 2025)])
def test_wording_matches_selected_years_and_preserves_other_settings(
    backend, audience, start, end
):
    source_path = (
        backend / "scripts/health_pipeline/config/stakeholders"
        / f"{audience}.json"
    )
    before = source_path.read_bytes()
    original = json.loads(before)
    request = local.prepare_request(audience, start, end)

    period = str(start) if start == end else f"{start}–{end}"
    assert request["years"] == [start, end]
    assert period in request["title"]
    assert period in request["question"]
    assert "2019 as the comparison year" in request["question"]
    assert "2019 as the index baseline" in request["question"]

    if end < 2025:
        assert "2025" not in request["title"]
        assert "2025" not in request["question"]

    changed = {"years", "title", "question"}
    assert {
        key: value for key, value in request.items() if key not in changed
    } == {
        key: value for key, value in original.items() if key not in changed
    }
    assert source_path.read_bytes() == before
