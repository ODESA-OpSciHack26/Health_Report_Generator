from __future__ import annotations

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    from datetime import datetime, timezone
    import io
    import pathlib
    import subprocess
    import sys

    import marimo as mo
    import pandas as pd

    return datetime, io, mo, pathlib, pd, subprocess, sys, timezone


@app.cell
def _(mo):
    audience = mo.ui.dropdown(
        options={"Researcher": "researcher", "Public health": "health_institution", "Public": "public"},
        value="Public health", label="Audience type",
    )
    source = mo.ui.dropdown(
        options={"Local IDD dataset": "idd", "Upload CSV/TSV": "upload"},
        value="Local IDD dataset", label="Data source",
    )
    mo.vstack([
        mo.md("# Local health report generator\n\nGenerate a report locally from the IDD dataset or an uploaded CSV/TSV file."),
        mo.hstack([audience, source]),
    ])
    return audience, source


@app.cell
def _(mo, source):
    upload = None
    idd_button = None
    csv_button = None
    if source.value == "idd":
        idd_button = mo.ui.run_button(label="Generate local IDD report")
        controls = idd_button
    else:
        upload = mo.ui.file(filetypes=[".csv", ".tsv"], multiple=False, label="Upload CSV/TSV")
        csv_button = mo.ui.run_button(label="Generate CSV/TSV report")
        controls = mo.vstack([upload, csv_button])
    restart = mo.ui.button(label="Restart analysis")
    mo.hstack([controls, restart])
    return csv_button, idd_button, restart, upload


@app.cell
def _(audience, csv_button, datetime, idd_button, io, mo, pathlib, pd, restart, source, subprocess, sys, timezone, upload):
    if restart.value:
        result = mo.md("Analysis reset. Choose an audience and data source to begin.")
    elif source.value == "idd":
        if not idd_button.value:
            result = mo.callout(mo.md(f"Local IDD data selected for the **{audience.value}** audience. Select **Generate local IDD report**."), kind="info")
        else:
            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            output_root = f"results/runs/idd/{run_id}"
            completed = subprocess.run(
                ["snakemake", "--cores", "2", "--config", f"out={output_root}", f"stakeholder={audience.value}"],
                capture_output=True, text=True, check=False,
            )
            if completed.returncode == 0:
                result = mo.callout(mo.md(f"The **{audience.value}** IDD report is ready in `{output_root}/reports/{audience.value}/`."), kind="success")
            else:
                result = mo.callout(mo.md(f"The local IDD report failed:\n\n```text\n{completed.stderr[-4000:]}\n```"), kind="danger")
    elif not upload or not upload.value:
        result = mo.md("Upload a CSV/TSV file to generate a report.")
    elif not csv_button.value:
        result = mo.md("Your file is ready. Select **Generate CSV/TSV report**.")
    else:
        item = upload.value[0]
        name = getattr(item, "name", "uploaded.csv")
        contents = getattr(item, "contents", b"")
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_root = pathlib.Path("results/runs/csv") / run_id
        input_path = run_root / "upload" / name
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_bytes(contents)
        completed = subprocess.run(
            [sys.executable, "scripts/health_pipeline/ingest_tabular.py", str(input_path), "--output-root", str(run_root / "data")],
            capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0:
            result = mo.callout(mo.md(f"Could not read this file:\n\n```text\n{completed.stderr[-4000:]}\n```"), kind="danger")
        else:
            audiences = ("researcher", "health_institution", "public")
            failures = []
            for report_audience in audiences:
                completed = subprocess.run(
                    [sys.executable, "scripts/health_pipeline/generic_report.py", str(input_path), "--output", str(run_root), "--audience", report_audience],
                    capture_output=True, text=True, check=False,
                )
                if completed.returncode != 0:
                    failures.append(f"{report_audience}: {completed.stderr[-1200:]}")
            if not failures:
                result = mo.callout(mo.md(f"Reports for all three audiences are ready in `{run_root}/reports/`."), kind="success")
            else:
                failure_text = "\n".join(failures)
                result = mo.callout(mo.md(f"The CSV/TSV report failed:\n\n```text\n{failure_text}\n```"), kind="danger")
    result


@app.cell
def _(mo):
    mo.md("---\n\nReports are generated locally and remain with the project outputs.")


if __name__ == "__main__":
    app.run()
