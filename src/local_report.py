"""Local UI adapter: reuse the report container, validator and cache.

Supported host: Linux/WSL with Docker Compose.
The lock coordinates this adapter only, not direct custom_report.py calls.
"""
import fcntl
import json
import os
import re
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIENCES = ("researcher", "health_institution", "public", "public_health_expert")


def prepare_request(audience, start_year, end_year):
    """Build date-consistent wording without changing source audience files."""
    if audience not in AUDIENCES:
        raise ValueError("Choose a supported audience.")
    if (
        type(start_year) is not int
        or type(end_year) is not int
        or not 2021 <= start_year <= end_year <= 2025
    ):
        raise ValueError("Choose an ordered year range within 2021–2025.")

    source = ROOT / "scripts/health_pipeline/config/stakeholders"
    request = json.loads((source / f"{audience}.json").read_text())
    request["years"] = [start_year, end_year]
    period = (
        str(start_year) if start_year == end_year
        else f"{start_year}–{end_year}"
    )
    label = request.get("presentation", {}).get(
        "display_name", audience.replace("_", " ").capitalize()
    )
    request["title"] = f"Notifiable disease report for {label}: {period}"
    request["question"] = (
        f"What do the notified-disease data show for {period} in Switzerland "
        f"and Liechtenstein, using {request['reference_year']} as the "
        f"comparison year and {request['index_base_year']} as the index baseline?"
    )
    return request


def run_request(audience, start_year, end_year):
    """Render a private output folder; return paths and verified cache status."""
    request = prepare_request(audience, start_year, end_year)

    base = ROOT / "results/local-ui"
    base.mkdir(parents=True, exist_ok=True)

    # Serialize snapshot/cache access across processes using this adapter.
    with (base / ".render.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        run = base / "runs" / uuid.uuid4().hex
        run.mkdir(parents=True)
        request_path = run / "request.json"
        request_path.write_text(json.dumps(request, indent=2) + "\n")
        out = run / "report"
        log = run / "render.log"

        command = [
            "docker", "compose", "run", "--rm", "-T", "report",
            "env", "-u", "GITHUB_TOKEN", "-u", "GH_TOKEN",
            "python", "scripts/health_pipeline/custom_report.py",
            request_path.relative_to(ROOT).as_posix(),
            "--out", out.relative_to(ROOT).as_posix(),
            "--cache", "results/cache/custom_reports",
        ]
        env = os.environ.copy()
        env["LOCAL_UID"] = str(os.getuid())
        env["LOCAL_GID"] = str(os.getgid())

        try:
            with log.open("w") as stream:
                subprocess.run(
                    command, cwd=ROOT, env=env, check=True,
                    stdout=stream, stderr=subprocess.STDOUT,
                )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(
                f"Local rendering failed. Inspect {log.relative_to(ROOT)}."
            ) from exc

        matches = re.findall(
            r"^cache (hit|miss): key=([0-9a-f]{64}) -> .+$",
            log.read_text(), re.MULTILINE,
        )
        required = (
            "report.html", "methods.html",
            "provenance.json", "request_provenance.json",
        )
        if len(matches) != 1 or any(
            not (out / name).is_file() for name in required
        ):
            raise RuntimeError(
                f"Render did not produce a complete result. "
                f"Inspect {log.relative_to(ROOT)}."
            )

        status, key = matches[0]
        provenance = json.loads((out / "request_provenance.json").read_text())
        if provenance.get("cache_key") != key:
            raise RuntimeError("Rendered cache identity does not match its log.")

        return {
            "status": status,
            "cache_key": key,
            "output": out,
            "log": log,
            "request": request_path,
        }
