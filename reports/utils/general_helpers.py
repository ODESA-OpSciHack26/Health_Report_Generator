"""The general report (general.qmd): the uploaded table, the reader's choices and the charts.

general_table.py has already read the table and decided what each column is (profile.json);
this module loads it, applies the years and groups chosen on the home page and draws the
charts. general.qmd imports everything from here.
"""
import base64
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly
import plotly.graph_objects as go
from IPython.display import HTML, display

import helpers as h  # chart style, and the chart library embedded for offline reading
from provenance import _run, git, sha256

RESULTS = Path(os.environ.get("HEALTH_RESULTS", "."))
profile = json.loads((RESULTS / "profile.json").read_text(encoding="utf-8"))
info = json.loads((RESULTS / "upload.json").read_text(encoding="utf-8"))
checks = pd.read_csv(RESULTS / "checks.csv")
raw = pd.read_csv(RESULTS / "table.csv", low_memory=False)

# Who the report is for, chosen on the home page: the researcher view shows how the table was read
# and every statistic; the public health view leads with what changed and keeps the detail short.
AUDIENCE = os.environ.get("HEALTH_AUDIENCE", "researcher")
RESEARCH = AUDIENCE != "public_health"
TIME, PERIOD, GROUPS = profile["time"], profile["period"], profile["groups"]
MEASURES = {m["name"]: m["how"] for m in profile["measures"]}
COUNTED = {m["name"] for m in profile["measures"] if m.get("counted")}
REAL = [m for m in MEASURES if m not in COUNTED]
MAIN = GROUPS[0] if GROUPS else None
for g in GROUPS:
    raw[g] = raw[g].astype("string").fillna("(empty)")

# The reader's choices on the home page: a range of years and some values of the main group.
YEARS = tuple(int(y) for y in os.environ["HEALTH_YEARS"].split("-")) if os.environ.get("HEALTH_YEARS") else None
CHOSEN = json.loads(os.environ.get("HEALTH_GROUPS") or "null")

table = raw.copy()
if TIME:
    if PERIOD == "year":
        table["_period"] = pd.to_datetime(table[TIME].astype("Int64").astype("string") + "-01-01", errors="coerce")
    else:
        table["_period"] = pd.to_datetime(table[TIME], errors="coerce")
    if PERIOD == "day" and table["_period"].nunique() > 400:  # daily data over years: show months
        PERIOD = "month"
    freq = {"year": "Y", "month": "M", "week": "W", "day": "D"}[PERIOD]
    table["_period"] = table["_period"].dt.to_period(freq).dt.start_time
    if YEARS:
        table = table[table["_period"].dt.year.between(*YEARS)]
if CHOSEN and MAIN:
    table = table[table[MAIN].isin(CHOSEN)]

PALETTE = ["#2a78d6", "#e8743b", "#19a979", "#945ecf", "#d64e8c", "#13a4b4", "#7f6f5f", "#b2a200"]
HOW = {"sum": "added up", "mean": "averaged"}


def label(period) -> str:
    if pd.isna(period):
        return "unknown"
    return {"year": f"{period:%Y}", "month": f"{period:%Y-%m}",
            "week": f"{period.isocalendar()[0]}-W{period.isocalendar()[1]:02d}"}.get(PERIOD, f"{period:%Y-%m-%d}")


def number(x) -> str:
    if pd.isna(x):
        return "–"
    return f"{x:,.0f}" if abs(x) >= 100 or float(x).is_integer() else f"{x:,.2f}"


def percent(new, old) -> str:
    if pd.isna(new) or old is None or pd.isna(old) or old == 0:
        return "–"
    return f"{(new - old) / abs(old) * 100:+.1f}%"


def combine(frame: pd.DataFrame, by, measure: str) -> pd.Series:
    return frame.groupby(by, dropna=True)[measure].agg(MEASURES[measure])


def show(frame: pd.DataFrame):
    styler = frame.style.hide(axis="index").set_properties(**{"text-align": "left", "font-size": "0.92rem"})
    display(HTML(styler.to_html()))


def figure(title: str, y_title: str, height: int = 340) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**h.LAYOUT, height=height, title=dict(text=title, font=dict(size=15)))
    fig.update_yaxes(title=y_title, gridcolor=h.GRID, showgrid=True, rangemode="tozero")
    return fig


def trend(frame: pd.DataFrame, measure: str):
    total = combine(frame, "_period", measure)
    fig = figure(f"{measure}: {'total' if MEASURES[measure] == 'sum' else 'average'} per {PERIOD}", measure)
    fig.add_scatter(x=[label(p) for p in total.index], y=total.values, mode="lines+markers",
                    line=dict(color=h.BLUE, width=2), name=measure)
    fig.update_xaxes(type="category", nticks=12)
    fig.show()


def ranked(frame: pd.DataFrame, group: str, measure: str, title: str):
    top = combine(frame, group, measure).sort_values(ascending=False).head(15).reset_index()
    h.bar_figure(top, measure, group, title + (" (largest 15)" if len(top) == 15 else ""), measure,
                 height=max(260, 30 * len(top) + 80)).show()


def histogram(frame: pd.DataFrame, measure: str):
    fig = figure(f"Distribution of {measure}", "Rows")
    fig.add_histogram(x=frame[measure].dropna(), marker=dict(color=h.BLUE), nbinsx=30, name=measure)
    fig.update_layout(hovermode="closest", bargap=0.05)
    fig.update_xaxes(title=measure)
    fig.show()


timed = table.dropna(subset=["_period"]) if TIME else table
periods = sorted(timed["_period"].unique()) if TIME else []
span = (f"{label(periods[0])} – {label(periods[-1])}" if len(periods) > 1 else label(periods[0])) if periods else "–"

# Files that go with the report: the rows it used and its summary statistics.
table.drop(columns=[c for c in table.columns if c.startswith("_")]).to_csv("data.csv", index=False)


def provenance_section(columns: list) -> str:
    """Write provenance_general.json and return the Provenance section as Markdown."""
    source = RESULTS / "table.csv"
    here = Path.cwd()
    record = {
        "report": "general.qmd",
        "audience": AUDIENCE,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": f"Uploaded table {info['name']}, supplied by the reader.",
        "input": {"file": info["name"], "sha256": info["sha256"], "bytes": info["bytes"], "rows": info["rows"],
                  "uploaded_at": info["uploaded_at"], "prepared_by": "scripts/health_pipeline/general_table.py",
                  "prepared_table_sha256": sha256(source)},
        "columns": profile,
        "report_parameters": {"audience": AUDIENCE, "years": list(YEARS) if YEARS else "all",
                              (MAIN or "group"): CHOSEN or "all"},
        "quality_checks": {k: int(v) for k, v in checks.status.value_counts().items()},
        "code": {name: sha256(here / name)
                 for name in ["general.qmd", "general_helpers.py", "helpers.py", "provenance.py", "general_style.css"]
                 if (here / name).is_file()},
        "git": git(),
        "environment": {"python": platform.python_version(), "pandas": pd.__version__, "plotly": plotly.__version__,
                        "quarto": _run(["quarto", "--version"]), "platform": platform.platform()},
    }
    text = json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n"
    (here / "provenance_general.json").write_text(text, encoding="utf-8")
    download = "data:application/json;base64," + base64.b64encode(text.encode("utf-8")).decode("ascii")
    facts = [
        ("Source", record["source"]),
        ("Uploaded (UTC)", info["uploaded_at"]),
        ("Input checksum (SHA-256)", f"`{info['sha256']}`"),
        ("Rows and columns", f"{info['rows']:,} rows, {len(columns)} columns"),
        ("Report parameters", "<br>".join(f"{k}: {', '.join(v) if isinstance(v, list) and k != 'years' else v}"
                                          for k, v in record["report_parameters"].items())),
        ("Quality checks", ", ".join(f"{n} {s}" for s, n in sorted(record["quality_checks"].items()))),
        ("Code version (git commit)", f"`{record['git']['commit']}`"
         + (" plus uncommitted changes" if record["git"]["uncommitted_changes"] else "")),
        ("Tools", f"Python {record['environment']['python']}, pandas {pd.__version__}, plotly {plotly.__version__}, "
                  f"Quarto {record['environment']['quarto']}"),
        ("Report generated (UTC)", record["generated_at"]),
    ]
    return ("| Item | Value |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in facts)
            + "\n\nThe full machine-readable record can be saved as a file: "
              f'<a download="provenance_general.json" href="{download}">download provenance_general.json</a>. '
              "The rows used and the summary statistics are saved next to the report as CSV files.\n\n"
            + "<details><summary>Full provenance record (JSON)</summary>\n\n```json\n" + text + "```\n\n</details>\n")
