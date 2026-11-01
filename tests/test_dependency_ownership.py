"""Report dependencies have one declared production Python resolution."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text()


def test_dependency_ownership_document_names_existing_contracts():
    document = read("docs/dependency-ownership.md")
    for name in (
        "workflow/toolchain.json",
        "scripts/health_pipeline/requirements.lock.txt",
        "pyproject.toml",
        "renv.lock",
        "scripts/ci/requirements-lint.txt",
        "workflow/environment.yml",
    ):
        assert (ROOT / name).is_file()
        assert name in document
    assert "docs/dependency-ownership.md" in read("README.md")


def test_report_installs_and_checks_the_pipeline_resolution():
    report = read("Dockerfile.report")
    assert "COPY scripts/health_pipeline/requirements.lock.txt" in report
    assert "-r /opt/build/requirements.lock.txt" in report
    assert "uv pip check" in report
    assert "snakemake pytest" in report
    assert "pandas.__version__ == '2.2.3'" in report
    assert "requirements.ui.lock.txt" not in report
    assert "uv sync --locked" not in report


def test_ci_retains_report_image_build_without_legacy_ui_image():
    ci = read(".github/workflows/validate.yml")
    assert "docker build --file Dockerfile.report --tag health-report:reports-ci ." in ci
    assert "docker build --tag health-report:ci ." not in ci
    assert "locked uv sync, Quarto, Marimo" not in ci


def test_retired_ui_packaging_is_absent():
    for name in (
        "Dockerfile",
        "uv.lock",
        "scripts/health_pipeline/requirements.ui.in",
        "scripts/health_pipeline/requirements.ui.lock.txt",
    ):
        assert not (ROOT / name).exists()
