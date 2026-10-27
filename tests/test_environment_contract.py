import json
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "workflow/toolchain.json").read_text(encoding="utf-8"))
WORKFLOWS = (
    ".github/workflows/validate.yml",
    ".github/workflows/refresh-idd-data.yml",
)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_python_contract_is_aligned():
    supported = CONTRACT["python"]["supported"]
    validated = CONTRACT["python"]["validated"]
    project = tomllib.loads(text("pyproject.toml"))
    assert project["project"]["requires-python"] == supported
    assert f"FROM python:{validated}-" in text("Dockerfile.report")
    for workflow in WORKFLOWS:
        assert f'python-version: "{validated}"' in text(workflow).replace("'", '"')


def test_quarto_contract_is_aligned():
    quarto_version = CONTRACT["quarto"]["validated"]
    assert f"ARG QUARTO_VERSION={quarto_version}" in text("Dockerfile.report")
    for workflow in WORKFLOWS:
        assert f'version: "{quarto_version}"' in text(workflow).replace("'", '"')


def test_uv_version_is_aligned():
    assert f'ARG UV_VERSION={CONTRACT["uv"]["validated"]}' in text("Dockerfile.report")


def test_validation_runs_for_push_and_pull_requests():
    workflow = text(".github/workflows/validate.yml")
    assert "  push:" in workflow
    assert "  pull_request:" in workflow


def test_data_refresh_targets_main():
    content = text(".github/workflows/refresh-idd-data.yml")
    assert "ref: main" in content


def test_documentation_names_authoritative_contract():
    for path in ("README.md",):
        assert "workflow/toolchain.json" in text(path)


def test_canonical_data_root_is_used_everywhere_active():
    assert "data_root: data/reference" in text("workflow/config.yaml")
    for workflow in WORKFLOWS:
        assert "data_root=Data" not in text(workflow)
    # Compare real names: exists() is case-insensitive on Windows/macOS mounts.
    assert "Data" not in {p.name for p in ROOT.iterdir()}
