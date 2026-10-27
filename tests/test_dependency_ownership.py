"""M2: retain explicit boundaries between dependency environments."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text()


def test_dependency_ownership_document_names_existing_contracts():
    document = read("docs/dependency-ownership.md")
    paths = [
        "workflow/toolchain.json",
        "scripts/health_pipeline/requirements.lock.txt",
        "scripts/health_pipeline/requirements.ui.in",
        "scripts/health_pipeline/requirements.ui.lock.txt",
        "pyproject.toml",
        "uv.lock",
        "renv.lock",
        "scripts/ci/requirements-lint.txt",
        "workflow/environment.yml",
    ]
    for name in paths:
        assert (ROOT / name).is_file()
        assert name in document
    assert "docs/dependency-ownership.md" in read("README.md")


def test_report_overlay_preserves_shared_pipeline_pins():

    pipeline = pins(read("scripts/health_pipeline/requirements.lock.txt"))
    overlay_text = read("scripts/health_pipeline/requirements.ui.lock.txt")
    overlay = pins(overlay_text)
    assert pipeline and overlay
    assert "-c scripts/health_pipeline/requirements.lock.txt" in overlay_text
    shared = set(pipeline) & set(overlay)
    assert shared
    assert not {
        name: (pipeline[name], overlay[name])
        for name in shared if pipeline[name] != overlay[name]
    }


def test_report_and_optional_ui_installation_paths_remain_distinct():
    report = read("Dockerfile.report")
    optional = read("Dockerfile")
    pipeline = "COPY scripts/health_pipeline/requirements.lock.txt"
    overlay = "COPY scripts/health_pipeline/requirements.ui.lock.txt"
    assert report.index(pipeline) < report.index(overlay)
    assert "-r /opt/build/requirements.lock.txt" in report
    assert "-r /opt/build/requirements.ui.lock.txt" in report
    assert "uv sync --locked" in optional
    assert "uv sync --locked" not in report


def pins(text):
    return {
        name.lower().replace("_", "-").replace(".", "-"): version
        for name, version in re.findall(
            r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", text, re.MULTILINE
        )
    }


def test_pin_parser_stops_at_whitespace_and_continuations():
    plain = (
        "typing_extensions==4.16.0\n"
        "tzdata==2026.5\n"
        "urllib3==2.8.0\n"
    )
    assert pins(plain) == {
        "typing-extensions": "4.16.0",
        "tzdata": "2026.5",
        "urllib3": "2.8.0",
    }

    hashed = "\n".join([
        "typing_extensions==4.16.0 " + chr(92),
        "    --hash=sha256:example",
        "tzdata==2026.5",
        "",
    ])
    assert pins(hashed) == {
        "typing-extensions": "4.16.0",
        "tzdata": "2026.5",
    }
