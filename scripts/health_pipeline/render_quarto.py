#!/usr/bin/env python3
"""Render one Quarto report (reports/<report>.qmd) from the harmonised results.

The reports are the .qmd documents in reports/; the code, styles and data files they use are
in reports/utils/. Rendering happens in a temporary build directory, so a half-written
report is never published and two reports can render at the same time without racing over
Quarto's intermediate files. The cleaned table stays where it is; the build directory gets
only the report code, and HEALTH_RESULTS points it at the results directory.

Outputs, next to --output: <report>.html and provenance_<report>.json.

Usage:  python render_quarto.py --report researcher --results results \
            --output results/site/researcher.html --data-root data/reference
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / "reports"
# Everything in reports/utils is copied next to the .qmd in the build directory, because the
# documents import the helpers and read the styles by name.
UTILS = SOURCE / "utils"
REQUIRED_INPUTS = ["harmonised.csv", "harmonised_snapshot.json", "datasets.csv", "checks.csv"]
# reports/general.qmd reads any table, as prepared by general_table.py.
GENERAL_INPUTS = ["table.csv", "profile.json", "checks.csv", "upload.json"]


def reports():
    return sorted(p.stem for p in SOURCE.glob("*.qmd"))


def render(report, results, output, quarto="quarto", data_root=None, topics=None, years=None, groups=None,
           audience=None):
    results = Path(results).resolve()
    output = Path(output).resolve()
    document = SOURCE / f"{report}.qmd"
    if not document.exists():
        raise SystemExit(f"no such report: {document} (available: {', '.join(reports())})")
    missing = [n for n in (GENERAL_INPUTS if report == "general" else REQUIRED_INPUTS)
               if not (results / n).exists()]
    if missing:
        raise SystemExit(f"missing pipeline outputs in {results}: {', '.join(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"quarto-{report}-") as tmp:
        build = Path(tmp)
        for source in [*sorted(p for p in UTILS.iterdir() if p.is_file()), document]:
            shutil.copyfile(source, build / source.name)
        env = os.environ.copy()
        env["HEALTH_RESULTS"] = str(results)
        env["HEALTH_REPORT_PROJECT"] = str(PROJECT)
        # Render with the interpreter that runs the pipeline: it is the one holding the
        # locked pandas, plotly and Jupyter kernel. Left to itself Quarto picks the first
        # python on PATH, which is a different installation and fails to start a kernel.
        env["QUARTO_PYTHON"] = sys.executable
        # provenance.py reads the retrieval records of the raw exports from here.
        if data_root:
            env["HEALTH_DATA_ROOT"] = str(Path(data_root).resolve())
        # Restricts the report to the diseases a reader selected; see helpers.SELECTED.
        if topics:
            env["HEALTH_TOPICS"] = ",".join(topics)
        # Limits the sections over time to these years, e.g. (2019, 2025); see helpers.FIRST_YEAR.
        if years:
            env["HEALTH_YEARS"] = f"{years[0]}-{years[1]}"
        # The general report only: values of the table's main group column to keep.
        if groups:
            env["HEALTH_GROUPS"] = json.dumps(list(groups))
        # The general report only: which view to write (researcher or public_health).
        if audience:
            env["HEALTH_AUDIENCE"] = audience
        # A reader's own table (upload_table.py): the report names it instead of the FOPH sources.
        upload = results / "upload.json"
        if upload.is_file():
            env["HEALTH_UPLOAD"] = json.loads(upload.read_text(encoding="utf-8"))["name"]
        subprocess.run([quarto, "render", document.name, "--to", "html"],
                       cwd=build, check=True, env=env)
        # Publish only after a successful render.
        shutil.copyfile(build / f"{report}.html", output)
        # Named after the output, not the report: two renders of the same report with
        # different disease selections write to different files and must not collide.
        provenance = build / f"provenance_{report}.json"
        if provenance.exists():
            shutil.copyfile(provenance, output.parent / f"provenance_{output.stem}.json")
        # The general report also leaves the rows it used and its summary statistics.
        for extra in ["data.csv", "summary.csv"]:
            if (build / extra).exists():
                shutil.copyfile(build / extra, output.parent / f"{output.stem}_{extra}")
    print(f"rendered {output}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help=f"one of: {', '.join(reports())}")
    ap.add_argument("--results", default="results")
    ap.add_argument("--output", required=True)
    ap.add_argument("--quarto", default="quarto")
    ap.add_argument("--data-root", help="raw exports the pipeline ingested, for provenance")
    ap.add_argument("--topics", help="comma-separated diseases to limit the report to "
                                     "(default: every disease)")
    ap.add_argument("--years", help="years to show in the sections over time, e.g. 2019-2025 "
                                    "(default: every year)")
    a = ap.parse_args()
    topics = [t.strip() for t in (a.topics or '').split(',') if t.strip()]
    years = tuple(int(y) for y in a.years.split('-')) if a.years else None
    render(a.report, a.results, a.output, a.quarto, a.data_root, topics, years)
