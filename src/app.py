"""Beginner-friendly web page: pick a report, get it as one HTML file.

Run inside the report image: `docker compose up app`, then open
http://localhost:8501. Nothing here calculates statistics.

- "Quarto report" tab: the Python Quarto reports in reports/ (researcher,
  public_health), rendered by render_quarto.py for the diseases you pick.
- "Audience report (R)" tab: builds a validated request and calls the same code
  as `custom_report.py`.
"""
import ast
import functools
import hashlib
import http.server
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "health_pipeline"))

import custom_report  # noqa: E402
import render_quarto  # noqa: E402
import web_request  # noqa: E402

DATA_ROOT = ROOT / "data" / "reference"
RESULTS = ROOT / "results"
CACHE = RESULTS / "cache" / "custom_reports"
OUT = RESULTS / "app"
QUARTO_OUT = OUT / "quarto"
VIEWER_PORT = 8502  # serves saved reports so links inside a report (methods.html, data/) work

AUDIENCES = {
    "General public": "public",
    "Health institution": "health_institution",
    "Researcher": "researcher",
}
AUDIENCE_HELP = {
    "public": "Plain language, with a 'How sure can we be?' section.",
    "health_institution": "Monitoring brief: biggest changes and small-number warnings.",
    "researcher": "Technical: filters, coverage, quality checks and methods.",
}
PERIODS = {f"{a} to {b}": [a, b] for a, b in web_request.SUPPORTED_WINDOWS}

QUARTO_REPORTS = {
    "Researcher": "researcher",
    "Public health officials": "public_health",
}
QUARTO_HELP = {
    "researcher": "How was it measured, and can I reproduce it? Coverage, quality checks, methods, provenance.",
    "public_health": "What needs attention now, and where? Current status, trends and regions.",
}


def load_diseases():
    """Disease ids and names from reports/shared/helpers.py, in the report's own order.

    Read without importing, so the page does not load pandas and plotly just to list them.
    """
    tree = ast.parse((ROOT / "reports" / "shared" / "helpers.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ALL_DISEASES" for t in node.targets):
            return {topic: name for topic, (name, _group) in ast.literal_eval(node.value).items()}
    raise RuntimeError("ALL_DISEASES not found in reports/shared/helpers.py")


DISEASES = load_diseases()


@st.cache_resource
def render_lock():
    """Only one report renders at a time; the pipeline shares working state."""
    return threading.Lock()


@st.cache_resource
def start_viewer():
    """Serve results/app on its own port; an embedded frame cannot resolve a report's relative links."""
    OUT.mkdir(parents=True, exist_ok=True)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(OUT))
    server = http.server.ThreadingHTTPServer(("0.0.0.0", VIEWER_PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def make_report(audience, years):
    stakeholder = web_request.build_stakeholder({"audience": audience, "years": years})
    with tempfile.TemporaryDirectory() as tmp:
        request = Path(tmp) / "request.json"
        request.write_text(json.dumps(stakeholder), encoding="utf-8")
        out = OUT / f"{audience}_{years[0]}-{years[1]}"
        status, _key, out = custom_report.build_custom(request, DATA_ROOT, out, CACHE)
    return status, Path(out)


def make_quarto_report(report, topics):
    """Render reports/<report>.qmd for these diseases, or reuse an identical earlier render.

    Snakemake first brings the cleaned table up to date (results/harmonised.csv); that is a
    no-op when nothing changed. The disease order is kept: it sets the order of rows,
    panels and columns in the report.
    """
    subprocess.run(["snakemake", "--cores", "2", "results/harmonised.csv"], cwd=ROOT, check=True)
    cleaned = RESULTS / "harmonised.csv"
    stamp = cleaned.stat()
    # Every disease in the report's own order is the full report, as `snakemake quarto` builds it.
    selected = [] if topics == list(DISEASES) else topics
    key = hashlib.sha256(json.dumps(
        [report, selected, stamp.st_size, stamp.st_mtime_ns]).encode()).hexdigest()[:12]
    output = QUARTO_OUT / f"{report}-{key}.html"
    if output.is_file():
        return "hit", output
    render_quarto.render(report, RESULTS, output, data_root=DATA_ROOT, topics=selected)
    return "miss", output


def run_locked(build, *args):
    """Run one build under the render lock; returns its result, or None after showing an error."""
    lock = render_lock()
    if not lock.acquire(blocking=False):
        st.warning("Another report is being created. Please wait a minute and try again.")
        return None
    try:
        with st.spinner("Creating the report. The first time can take a few minutes..."):
            return build(*args)
    except ValueError as exc:
        st.error(f"Invalid request: {exc}")
    except (subprocess.CalledProcessError, SystemExit):
        st.error("The report could not be built. See the container log for details.")
    finally:
        lock.release()
    return None


def open_once(url, stamp, slot):
    """Open a new report in a new tab once, not on every rerun."""
    if st.session_state.get(slot) != stamp:
        st.session_state[slot] = stamp
        st.iframe(f'<!DOCTYPE html><script>window.open("{url}", "_blank");</script>', height=1)


st.set_page_config(page_title="Infectious disease reports", layout="wide")
start_viewer()
st.title("Infectious disease reports")
st.write(
    "Official Swiss notifiable-disease data (FOPH). Choose a report, "
    "then press **Generate report**."
)

quarto_tab, audience_tab = st.tabs(["Quarto report", "Audience report (R)"])

with quarto_tab:
    with st.form("quarto_request"):
        report_label = st.radio("Which report?", list(QUARTO_REPORTS), horizontal=True)
        topics = st.multiselect(
            "Which diseases?", list(DISEASES), default=list(DISEASES),
            format_func=DISEASES.get,
            help="The report lists diseases in the order you pick them.",
        )
        quarto_submitted = st.form_submit_button("Generate report", type="primary")
    st.caption(QUARTO_HELP[QUARTO_REPORTS[report_label]])

    if quarto_submitted:
        if not topics:
            st.warning("Pick at least one disease.")
        else:
            built = run_locked(make_quarto_report, QUARTO_REPORTS[report_label], topics)
            if built:
                st.session_state["quarto_result"] = (built[0], str(built[1]), time.time())

    if "quarto_result" in st.session_state:
        status, path, stamp = st.session_state["quarto_result"]
        report = Path(path)
        provenance = report.with_name(f"provenance_{report.stem}.json")
        if report.is_file():
            st.success("Report ready." + (" (reused an identical earlier report)" if status == "hit" else ""))
            url = f"http://localhost:{VIEWER_PORT}/{report.relative_to(OUT).as_posix()}"
            st.link_button("Open report in new tab", url, type="primary")
            left, right, _ = st.columns([1, 1, 4])
            left.download_button("Download report", report.read_bytes(), f"{report.stem}.html", "text/html")
            if provenance.is_file():
                right.download_button("Download provenance", provenance.read_bytes(),
                                      provenance.name, "application/json")
            st.caption(
                "One self-contained HTML file: it works offline and can be emailed or put online. "
                f"Saved in `{report.relative_to(ROOT).as_posix()}`."
            )
            open_once(url, stamp, "quarto_opened")

with audience_tab:
    with st.form("request"):
        audience_label = st.radio("Who is the report for?", list(AUDIENCES), horizontal=True)
        period_label = st.radio("Which years?", list(PERIODS), horizontal=True)
        submitted = st.form_submit_button("Generate report", type="primary")
    st.caption(AUDIENCE_HELP[AUDIENCES[audience_label]])

    if submitted:
        built = run_locked(make_report, AUDIENCES[audience_label], PERIODS[period_label])
        if built:
            st.session_state["result"] = (built[0], str(built[1]), time.time())

    if "result" in st.session_state:
        status, folder, stamp = st.session_state["result"]
        folder = Path(folder)
        report, methods = folder / "report.html", folder / "methods.html"
        if report.is_file():
            st.success("Report ready." + (" (reused an identical earlier report)" if status == "hit" else ""))
            url = f"http://localhost:{VIEWER_PORT}/{folder.name}/report.html"
            st.link_button("Open report in new tab", url, type="primary")
            left, right, _ = st.columns([1, 1, 4])
            left.download_button("Download report", report.read_bytes(), "report.html", "text/html")
            if methods.is_file():
                right.download_button("Download methods", methods.read_bytes(), "methods.html", "text/html")
            st.caption(
                f"The report opens as a normal full page (same Quarto report as the standard build). "
                f"If your browser blocked the new tab, use the button above. "
                f"Files are also saved in `{folder.relative_to(ROOT).as_posix()}`."
            )
            open_once(url, stamp, "opened")
