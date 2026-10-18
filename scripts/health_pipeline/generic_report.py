"""Create a simple descriptive report for an uploaded table."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def build(input_file: str, output: str, audience: str) -> Path:
    source = Path(input_file)
    out = Path(output) / "reports" / audience
    out.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(source, sep="\t" if source.suffix.lower() == ".tsv" else ",")
    numeric = frame.select_dtypes(include="number").columns.tolist()
    text = [c for c in frame.columns if c not in numeric]
    summary = frame.describe(include="all").transpose().reset_index(names="column")
    summary.to_csv(out / "summary.csv", index=False)
    frame.to_csv(out / "data.csv", index=False)
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
    (out / "report.html").write_text(html, encoding="utf-8")
    (out / "methods.html").write_text(f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Methods and provenance</title><style>{style}</style></head><body><header><h1>Methods and provenance</h1><p class='muted'>How this report was produced.</p></header><main><h2>Input</h2><p><strong>File:</strong> {source.name}</p><p><strong>Rows:</strong> {len(frame)} &nbsp; <strong>Columns:</strong> {len(frame.columns)}</p><h2>Processing</h2><p>The table was read locally and summarised descriptively. Numeric columns were treated as measures and text columns as descriptive fields. No IDD-specific disease classification, population denominator, or causal interpretation was applied.</p><h2>Audience</h2><p>This report was prepared for the <strong>{audience.replace('_', ' ')}</strong> audience.</p></main><footer>Machine-readable provenance is stored alongside this page.</footer></body></html>""", encoding="utf-8")
    qmd = f"""---\ntitle: '{title}'\nformat: html\n---\n\n# Input\n\nSource file: `{source.name}`\n\nRows: {len(frame)}  \nColumns: {len(frame.columns)}\n\n# Column summary\n\n```{{python}}\nimport pandas as pd\ndf = pd.read_csv('data.csv')\ndf.describe(include='all').T\n```\n"""
    (out / "report.qmd").write_text(qmd, encoding="utf-8")
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
