"""Report-container configuration must remain aligned and exercised in CI."""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_report_image_matches_toolchain_contract():
    contract = json.loads((ROOT / "workflow/toolchain.json").read_text(encoding="utf-8"))
    dockerfile = (ROOT / "Dockerfile.report").read_text(encoding="utf-8")

    assert f'FROM python:{contract["python"]["validated"]}-' in dockerfile
    assert f'ARG QUARTO_VERSION={contract["quarto"]["validated"]}' in dockerfile
    assert f'ARG UV_VERSION={contract["uv"]["validated"]}' in dockerfile
    assert "requirements.lock.txt" in dockerfile
    assert "reports/utils/requirements.txt" in dockerfile


def test_image_builds_natively_on_every_processor():
    """No platform pin: an Apple-chip Mac builds arm64 instead of emulating amd64."""
    dockerfile = (ROOT / "Dockerfile.report").read_text(encoding="utf-8")
    services = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))["services"]
    assert not any("platform" in service for service in services.values())
    assert "ARG TARGETARCH" in dockerfile and "linux-${TARGETARCH}.tar.gz" in dockerfile
    assert "linux-amd64" not in dockerfile


def test_services_share_one_image_without_github_credentials():
    services = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))["services"]
    assert set(services) == {"report", "sync", "app"}
    assert services["report"]["command"] == ["snakemake", "--cores", "2"]
    for service in services.values():
        assert service["build"]["dockerfile"] == "Dockerfile.report"
        assert service["image"] == "health-report:local"
        assert not any(name.startswith("GITHUB_") for name in service.get("environment", {}))


def test_ci_builds_and_verifies_reports_inside_container():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["container"]["steps"]

    build = next(
        i for i, step in enumerate(steps)
        if "--file Dockerfile.report" in step.get("run", "")
    )
    render = next(
        i for i, step in enumerate(steps)
        if "health-report:reports-ci" in step.get("run", "")
        and "snakemake --cores 2" in step.get("run", "")
    )
    verify = next(
        i for i, step in enumerate(steps)
        if "Nothing to be done" in step.get("run", "")
    )

    assert build < render < verify
    assert "researcher.html" in steps[verify]["run"]
    assert all("continue-on-error" not in step for step in steps)
