"""Beginner-friendly web page: pick an audience and period, get a report.

Run inside the report image: `docker compose up app`, then open
http://localhost:8501. Nothing here calculates statistics; it only builds a
validated request and calls the same code as `custom_report.py`.
"""
import functools
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
import web_request  # noqa: E402

DATA_ROOT = ROOT / "data" / "reference"
CACHE = ROOT / "results" / "cache" / "custom_reports"
OUT = ROOT / "results" / "app"
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


st.set_page_config(page_title="Infectious disease reports", layout="wide")
start_viewer()
st.title("Infectious disease reports")
st.write(
    "Official Swiss notifiable-disease data (FOPH). Choose who the report is for "
    "and the period, then press **Generate report**."
)

with st.form("request"):
    audience_label = st.radio("Who is the report for?", list(AUDIENCES), horizontal=True)
    period_label = st.radio("Which years?", list(PERIODS), horizontal=True)
    submitted = st.form_submit_button("Generate report", type="primary")
st.caption(AUDIENCE_HELP[AUDIENCES[audience_label]])

if submitted:
    lock = render_lock()
    if not lock.acquire(blocking=False):
        st.warning("Another report is being created. Please wait a minute and try again.")
    else:
        try:
            with st.spinner("Creating the report. The first time can take a few minutes..."):
                status, folder = make_report(AUDIENCES[audience_label], PERIODS[period_label])
            st.session_state["result"] = (status, str(folder), time.time())
        except ValueError as exc:
            st.error(f"Invalid request: {exc}")
        except subprocess.CalledProcessError:
            st.error("The report could not be built. See the container log for details.")
        finally:
            lock.release()

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
        if st.session_state.get("opened") != stamp:  # open once per new report, not on every rerun
            st.session_state["opened"] = stamp
            st.iframe(f'<!DOCTYPE html><script>window.open("{url}", "_blank");</script>', height=1)
