#!/usr/bin/env python3
"""Local precommit/clean-release gates; pipeline tools run in the report service."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def source_hashes():
    raw = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT)
    paths = sorted(set(name.decode() for name in raw.split(b"\0") if name))
    result = {}
    for name in paths:
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Source inventory requires regular files: " + name)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["precommit", "clean-release"], required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", args.name):
        parser.error("Name must be a simple path-free identifier.")
    status = git("status", "--porcelain", "--untracked-files=all")
    if args.phase == "clean-release" and status:
        parser.error("Clean-release requires a clean source worktree.")
    prefix = "reproduced/" + args.name
    logs = ROOT / (prefix + "-evidence")
    tabular = prefix + "-tabular"
    canonical = prefix + "-canonical"
    if any(path.exists() for path in [logs, ROOT / tabular, ROOT / canonical]):
        parser.error("Gate evidence/output exists; preserve it and select a new name.")
    original_hashes = source_hashes()
    commit = git("rev-parse", "HEAD")
    logs.mkdir(parents=True)
    record = {
        "schema": "health-report/handover-gates/1", "phase": args.phase,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit, "source_worktree_clean": status == "",
        "source_worktree_status": status.splitlines(),
        "source_sha256": original_hashes, "stages": [],
        "browser_acceptance": "NOT TESTED by this runner",
        "image_build": "Existing report image; no rebuild claim",
        "outputs": {"tabular": tabular,
                    "canonical": canonical if args.phase == "clean-release" else None},
    }
    (logs / "source-state.json").write_text(json.dumps(record, indent=2) + "\n")
    base = ["docker", "compose", "run", "--rm", "--no-deps", "-T", "--user",
            f"{os.getuid()}:{os.getgid()}", "report"]

    def stage(name, command):
        print("START:", name, flush=True)
        path = logs / (name + ".log")
        started = time.monotonic()
        with path.open("w") as handle:
            completed = subprocess.run(base + command, cwd=ROOT, stdout=handle,
                                       stderr=subprocess.STDOUT, check=False)
        result = {"stage": name, "exit_code": completed.returncode,
                  "seconds": round(time.monotonic() - started, 2),
                  "log": path.relative_to(ROOT).as_posix()}
        record["stages"].append(result)
        print(("PASS:" if completed.returncode == 0 else "FAIL:"), name, flush=True)
        lines = path.read_text(errors="replace").splitlines()
        print("\n".join(lines[-4:] if completed.returncode == 0 else lines[-60:]), flush=True)
        if completed.returncode:
            raise RuntimeError("Gate failed; preserve its log: " + name)
        return path

    success = False
    try:
        stage("versions", ["sh", "-ec", "python --version; quarto --version; Rscript --version"])
        stage("new-tests", ["python", "-m", "pytest", "-q", "tests/test_tabular_run.py", "tests/test_evidence_archive.py"])
        stage("full-tests", ["python", "-m", "pytest", "-q"])
        lint = ("export UV_CACHE_DIR=/tmp/health-report-uv-cache\n"
                "export RUFF_CACHE_DIR=/tmp/health-report-ruff-cache\n"
                "test \"$(cat scripts/ci/requirements-lint.txt)\" = 'ruff==0.14.0'\n"
                "uvx --from ruff==0.14.0 ruff check .")
        stage("pinned-lint", ["sh", "-ec", lint])
        stage("one-command-example", ["python", "scripts/health_pipeline/tabular_run.py", "build",
            "--input", "examples/tabular/observations.csv", "--request", "examples/tabular/request.json",
            "--output", tabular])
        stage("verify-example", ["python", "scripts/health_pipeline/tabular_run.py", "verify", "--output", tabular])
        if args.phase == "clean-release":
            stage("canonical-build", ["snakemake", "--cores", "2", "--config", "out=" + canonical])
            stage("check-outputs", ["python", "scripts/health_pipeline/check_outputs.py", "--out", canonical])
            stage("verify-release", ["python", "scripts/health_pipeline/verify_release.py", "--out", canonical])
            for name, script in [("shiny-smoke", "tests/shiny_smoke.R"), ("dashboard-smoke", "tests/dashboard_smoke.R")]:
                stage(name, ["Rscript", script, canonical + "/reports/researcher/app"])
            dry = stage("post-build-dry-run", ["snakemake", "--dry-run", "--cores", "1", "--config", "out=" + canonical])
            passed = "Nothing to be done" in dry.read_text()
            record["stages"].append({"stage": "require-no-op", "exit_code": 0 if passed else 1})
            if not passed:
                raise RuntimeError("Canonical rebuild was not a no-op.")
        if git("rev-parse", "HEAD") != commit or source_hashes() != original_hashes:
            raise RuntimeError("Source revision/files changed while gates ran.")
        if args.phase == "clean-release" and git("status", "--porcelain", "--untracked-files=all"):
            raise RuntimeError("Source worktree is no longer clean.")
        success = True
    finally:
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        record["all_gates_passed"] = success
        (logs / "summary.json").write_text(json.dumps(record, indent=2) + "\n")
        print("===== GATE SUMMARY =====", flush=True)
        for item in record["stages"]:
            print(item["stage"], item["exit_code"], flush=True)
        print("all_gates_passed=" + str(success).lower(), flush=True)
        print("Evidence:", logs.relative_to(ROOT), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
