"""Create a simple descriptive report for an uploaded table."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates"


def _chart_html(frame: pd.DataFrame, out: Path) -> tuple[str, str]:
    """Create one self-contained Plotly chart, or explain why a chart is unsafe."""
    try:
        import plotly.express as px
        import plotly.io as pio
    except ImportError:
        return "", "Plotly is not available in this environment; the table was retained without a chart."

    numeric = frame.select_dtypes(include="number").columns.tolist()
    categorical = [c for c in frame.columns if c not in numeric]
    time_like = []
    for column in categorical:
        parsed = pd.to_datetime(frame[column], errors="coerce")
        if parsed.notna().mean() >= 0.8:
            time_like.append(column)

    fig = None
    rule = ""
    if time_like and numeric:
        time = time_like[0]
        work = frame.copy()
        work["_time"] = pd.to_datetime(work[time], errors="coerce")
        work = work.dropna(subset=["_time"])
        if len(work) >= 2:
            measure = numeric[0]
            grouped = work.groupby("_time", as_index=False)[measure].sum()
            fig = px.line(grouped, x="_time", y=measure, markers=True,
                          title=f"{measure} over time", labels={"_time": time})
            rule = "date/period + numeric → time trend"
    elif categorical and numeric:
        group = categorical[0]
        measure = numeric[0]
        grouped = frame.groupby(group, dropna=False, as_index=False)[measure].sum()
        grouped = grouped.nlargest(15, measure).sort_values(measure)
        fig = px.bar(grouped, x=measure, y=group, orientation="h",
                     title=f"{measure} by {group}")
        rule = "category + numeric → ranked bar chart"
    elif len(numeric) >= 2:
        fig = px.scatter(frame, x=numeric[0], y=numeric[1],
                         title=f"{numeric[1]} compared with {numeric[0]}")
        rule = "numeric + numeric → scatter plot"
    elif numeric:
        measure = numeric[0]
        fig = px.histogram(frame, x=measure, marginal="box",
                           title=f"Distribution of {measure}")
        rule = "numeric → distribution and box plot"
    elif categorical:
        group = categorical[0]
        counts = frame[group].value_counts(dropna=False).head(15).rename_axis(group).reset_index(name="rows")
        fig = px.bar(counts.sort_values("rows"), x="rows", y=group, orientation="h",
                     title=f"Rows by {group}")
        rule = "category only → frequency bar chart"

    if fig is None:
        return "", "No safe automatic chart rule matched this table; the report contains the table and data-quality explanation."
    fig.update_layout(template="plotly_white", height=480, margin=dict(l=40, r=30, t=70, b=40))
    chart_path = out / "automatic_chart.html"
    chart_path.write_text(pio.to_html(fig, full_html=False, include_plotlyjs="inline"), encoding="utf-8")
    return chart_path.read_text(encoding="utf-8"), rule


def build(input_file: str, output: str, audience: str) -> Path:
    source = Path(input_file)
    out = Path(output) / "reports" / audience
    out.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(source, sep="\t" if source.suffix.lower() == ".tsv" else ",")
    numeric = frame.select_dtypes(include="number").columns.tolist()
    summary = frame.describe(include="all").transpose().reset_index(names="column")
    summary.to_csv(out / "summary.csv", index=False)
    frame.to_csv(out / "data.csv", index=False)
    chart_html, chart_rule = _chart_html(frame, out)
    title = f"Descriptive health report — {audience.replace('_', ' ').title()}"
    rows = "\n".join(f"<tr><td>{c}</td><td>{frame[c].dtype}</td><td>{frame[c].nunique(dropna=True)}</td></tr>" for c in frame.columns)
    style = """
    :root { font-family: system-ui, -apple-system, sans-serif; color: #1f2937; background: #f7f8fa; }
    body { max-width: 1040px; margin: 0 auto; padding: 42px 24px 64px; line-height: 1.5; }
    header { border-bottom: 1px solid #d9dee7; margin-bottom: 28px; padding-bottom: 22px; }
    h1 { font-size: 2.15rem; line-height: 1.15; margin: 0 0 10px; color: #111827; }
    h2 { margin-top: 34px; color: #111827; font-size: 1.3rem; }
    .muted { color: #667085; }
    .cards { display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0; }
    .card { background: #fff; border: 1px solid #e1e5eb; border-radius: 8px; padding: 16px 18px; min-width: 150px; }
    .value { display: block; font-size: 1.45rem; font-weight: 650; color: #111827; }
    .label { color: #667085; font-size: .9rem; }
    .table-wrap { overflow-x: auto; background: #fff; border: 1px solid #e1e5eb; border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #edf0f3; }
    th { background: #f1f3f6; color: #344054; font-weight: 650; }
    tr:last-child td { border-bottom: 0; }
    footer { margin-top: 38px; padding-top: 16px; border-top: 1px solid #d9dee7; color: #667085; font-size: .9rem; }
    @media (max-width: 600px) { body { padding: 26px 14px 42px; } h1 { font-size: 1.7rem; } .card { flex: 1 1 120px; } }
    """
    preview = frame.head(20).to_html(index=False, classes="data-table", border=0)
    html = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{title}</title><style>{style}</style></head><body>
<header><h1>{title}</h1><p class='muted'>Generated locally from <strong>{source.name}</strong>.</p></header>
<main><h2>At a glance</h2><div class='cards'><div class='card'><span class='value'>{len(frame)}</span><span class='label'>Rows</span></div><div class='card'><span class='value'>{len(frame.columns)}</span><span class='label'>Columns</span></div><div class='card'><span class='value'>{len(numeric)}</span><span class='label'>Numeric measures</span></div></div>
<h2>Columns</h2><div class='table-wrap'><table><thead><tr><th>Column</th><th>Type</th><th>Distinct values</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Data preview</h2><div class='table-wrap'>{preview}</div></main><footer>This is an automatic descriptive summary. See the accompanying methods page for processing details.</footer>
</body></html>"""
    chart_section = (f"<h2>Automatic visual summary</h2><p class='muted'>{chart_rule}</p>{chart_html}"
                     if chart_html else f"<h2>Automatic visual summary</h2><p>{chart_rule}</p>")
    html = html.replace("<h2>Data preview</h2>", chart_section + "<h2>Data preview</h2>")
    (out / "report.html").write_text(html, encoding="utf-8")
    (out / "methods.html").write_text(f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Methods and provenance</title><style>{style}</style></head><body><header><h1>Methods and provenance</h1><p class='muted'>How this report was produced.</p></header><main><h2>Input</h2><p><strong>File:</strong> {source.name}</p><p><strong>Rows:</strong> {len(frame)} &nbsp; <strong>Columns:</strong> {len(frame.columns)}</p><h2>Processing</h2><p>The table was read locally and summarised descriptively. Numeric columns were treated as measures and text columns as descriptive fields. No IDD-specific disease classification, population denominator, or causal interpretation was applied.</p><h2>Audience</h2><p>This report was prepared for the <strong>{audience.replace('_', ' ')}</strong> audience.</p></main><footer>Machine-readable provenance is stored alongside this page.</footer></body></html>""", encoding="utf-8")
    (out / "report.css").write_text(style, encoding="utf-8")
    # CSV reports are deliberately static: the QMD remains editable, but rendering
    # does not require a notebook kernel to recalculate charts.
    qmd = f'''---
title: "Descriptive data report — {audience.replace('_', ' ').title()}"
subtitle: "A reproducible summary of the uploaded table"
format:
  html:
    css: report.css
    toc: true
    embed-resources: true
    theme: cosmo
    page-layout: article
---

<style>
:root {{ --ink: #263238; --blue: #173f63; --soft: #f5f7fa; --border: #dde3ea; }}
body {{ background: #fbfcfe; color: var(--ink); }}
h1, h2, h3 {{ color: var(--blue); }}
.summary-grid {{ display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: .8rem; margin: .6rem 0 1.3rem; }}
.summary-card {{ background: #245b8a; color: white; border-radius: 12px; padding: 1rem 1.05rem; min-height: 92px; box-shadow: 0 3px 10px rgba(30,55,80,.10); }}
.summary-card .label {{ display: block; font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; opacity: .95; font-weight: 650; }}
.summary-card .value {{ display: block; font-size: 1.75rem; font-weight: 800; margin-top: .25rem; }}
table {{ width: 100%; background: white; border-collapse: separate; border-spacing: 0; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }}
thead th {{ background: var(--blue) !important; color: white !important; font-weight: 650; padding: .65rem .75rem !important; }}
tbody td {{ padding: .58rem .75rem !important; border-bottom: 1px solid #edf0f3 !important; }}
tbody tr:nth-child(even) {{ background: #f8fafc; }}
@media (max-width: 800px) {{ .summary-grid {{ grid-template-columns: repeat(2, minmax(140px, 1fr)); }} }}
@media print {{ * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }} .summary-card {{ background: #245B8A !important; color: white !important; }} }}
</style>

## Input

This report was generated locally from **{source.name}**. It is a descriptive summary and does not apply IDD-specific classifications.

<div class="summary-grid">
<div class="summary-card"><span class="label">Rows</span><span class="value">{len(frame):,}</span></div>
<div class="summary-card"><span class="label">Columns</span><span class="value">{len(frame.columns):,}</span></div>
<div class="summary-card"><span class="label">Numeric measures</span><span class="value">{len(frame.select_dtypes(include="number").columns):,}</span></div>
<div class="summary-card"><span class="label">Missing cells</span><span class="value">{int(frame.isna().sum().sum()):,}</span></div>
</div>

## Automatic visual summary

{chart_rule}.

'''
    if chart_html:
        fence = "```"
        while fence in chart_html:
            fence += "`"
        qmd += f"\n\n{fence}{{=html}}\n{chart_html}\n{fence}\n\n"
    qmd += "\n## Data preview\n\n" + frame.head(20).to_markdown(index=False) + "\n"
    qmd += "\n## Reproducibility note\n\nThe input table, generated summary, provenance record, chart asset, and this editable Quarto source are stored together. This CSV report is descriptive and does not apply IDD-specific classifications.\n"
    (out / "report.qmd").write_text(qmd, encoding="utf-8")
    if shutil.which("quarto"):
        rendered = subprocess.run(
            ["quarto", "render", "report.qmd", "--to", "html", "--output", "report.html"],
            cwd=out, capture_output=True, text=True, check=False,
        )
        if rendered.returncode != 0:
            (out / "quarto_render.log").write_text(rendered.stdout + "\n" + rendered.stderr, encoding="utf-8")
    provenance = {"source_filename": source.name, "audience": audience, "rows": len(frame), "columns": list(frame.columns), "generated_at_utc": datetime.now(timezone.utc).isoformat()}
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--audience", required=True)
    args = parser.parse_args()
    print(build(args.input, args.output, args.audience))
