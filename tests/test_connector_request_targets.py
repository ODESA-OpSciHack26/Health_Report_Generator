"""Configured forks must be used by artifact lookup."""
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORK = "example-user/example-fork"


@pytest.fixture
def connector_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "src"))
    monkeypatch.setenv("GITHUB_REPOSITORY", FORK)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-not-a-real-secret")
    monkeypatch.setenv("GITHUB_OWNER", "wrong-owner")
    monkeypatch.setenv("GITHUB_REPO", "wrong-repo")
    monkeypatch.setenv("GITHUB_APP_REF", "main")
    monkeypatch.setenv("GITHUB_WORKFLOW", "refresh-idd-data.yml")
    monkeypatch.setenv("GITHUB_BRANCH", "main")

    config = importlib.import_module("github_config")
    downloader = importlib.import_module("artifact_download")
    return config, downloader


def test_artifact_lookup_targets_configured_fork(
    connector_modules, monkeypatch
):
    _, downloader = connector_modules
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"workflow_runs": []},
        )

    monkeypatch.setattr(downloader.requests, "get", fake_get)

    with pytest.raises(RuntimeError, match="No successful"):
        downloader.download_latest_report()

    assert len(calls) == 1
    assert calls[0][0] == (
        f"https://api.github.com/repos/{FORK}/actions/workflows/"
        "refresh-idd-data.yml/runs"
    )
    assert calls[0][1]["params"]["branch"] == "main"


def test_local_ui_does_not_dispatch_github_actions():
    content = (ROOT / "src/ui.py").read_text()
    assert "snakemake" in content
    assert "generic_report.py" in content
    assert "requests.post" not in content

