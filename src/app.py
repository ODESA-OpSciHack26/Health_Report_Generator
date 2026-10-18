"""Home page: choose who the report is for, the data, the years and the diseases, get one HTML report.

Run inside the report image: `docker compose up app`, then open
http://localhost:8501. Nothing here calculates statistics: it brings the cleaned
table up to date with Snakemake (or prepares an uploaded table with upload_table.py)
and renders reports/<report>.qmd with render_quarto.py, the same code as `snakemake`.
"""
import ast
import functools
import hashlib
import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "health_pipeline"))

import render_quarto  # noqa: E402
import upload_table  # noqa: E402

DATA_ROOT = ROOT / "data" / "reference"
RESULTS = ROOT / "results"
SITE = RESULTS / "site"
UPLOADS = RESULTS / "uploads"
OUT = RESULTS / "app"
VIEWER_PORT = 8502  # serves saved reports on their own port, so they open as normal full pages

# report id -> (icon, name, what the report answers)
STAKEHOLDERS = {
    "researcher": ("🔬", "Researcher",
                   "How was it measured, and can I reproduce it? Methods, quality checks, trends, "
                   "seasonality, age groups and cantons."),
    "public_health": ("🏥", "Public health officials",
                      "What needs attention now, and where? Diseases above their usual level, "
                      "cantons most affected, this year against last."),
}
# Centred headings, cards and disease tiles (the page itself uses Streamlit's centred layout).
STYLE = """
<style>
h1 { text-align: center; }
.stElementContainer:has(> .stButtonGroup) { align-self: center; }
.stButtonGroup > div:last-child { justify-content: center; }
.stButtonGroup [data-testid="stWidgetLabel"] { justify-content: center; font-weight: 600; }
.note { text-align: center; color: #5f6368; font-size: 0.85rem; margin: 0.3rem 0 0.6rem; }
.step { text-align: center; margin: 1.6rem 0 0.6rem; font-size: 1.45rem; font-weight: 600; }
.lead { text-align: center; color: #5f6368; margin-bottom: 0.4rem; }
.card { text-align: center; padding: 0.4rem 0.2rem 0.2rem; }
.card .icon { font-size: 2.8rem; line-height: 1.2; }
.card .name { font-size: 1.2rem; font-weight: 600; margin-top: 0.3rem; }
.card .what { color: #5f6368; font-size: 0.88rem; min-height: 3.8rem; margin-top: 0.3rem; }
.years { text-align: center; font-size: 1.15rem; font-weight: 600; }
</style>
"""


def load_diseases():
    """{group: {topic: name}} from reports/shared/helpers.py, in the report's own order.

    Read without importing, so the page does not load plotly just to list them.
    """
    tree = ast.parse((ROOT / "reports" / "shared" / "helpers.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ALL_DISEASES" for t in node.targets):
            groups = {}
            for topic, (name, group) in ast.literal_eval(node.value).items():
                groups.setdefault(group, {})[topic] = name
            return groups
    raise RuntimeError("ALL_DISEASES not found in reports/shared/helpers.py")


GROUPS = load_diseases()
DISEASES = {topic: name for group in GROUPS.values() for topic, name in group.items()}


@st.cache_data
def year_range(stamp):
    """First and last year of disease data in the cleaned table; `stamp` refreshes it when the table changes."""
    path = RESULTS / "harmonised.parquet"
    if not path.is_file():
        return 2013, time.localtime().tm_year
    years = pd.read_parquet(path, columns=["topic", "year"])
    years = years[years.topic.isin(DISEASES)].year
    return int(years.min()), int(years.max())


@st.cache_resource
def render_lock():
    """Only one build runs at a time; Snakemake and the renders share working state."""
    return threading.Lock()


@st.cache_resource
def start_viewer():
    """Serve results/app on its own port, so a report opens as a normal full page."""
    OUT.mkdir(parents=True, exist_ok=True)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(OUT))
    server = http.server.ThreadingHTTPServer(("0.0.0.0", VIEWER_PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@st.cache_resource
def build_state():
    """Shared across readers: has the background build finished, and what did it build from."""
    return {"done": False, "ok": None, "fingerprint": None}


def fingerprint():
    """Size and modification time of every file Snakemake's outputs depend on.

    Statting them takes about a second; asking Snakemake whether anything changed takes
    several, mostly on a Windows folder mounted into Docker.
    """
    files = []
    for path in [DATA_ROOT, ROOT / "scripts" / "health_pipeline", ROOT / "reports", ROOT / "workflow",
                 ROOT / "Snakefile"]:
        files += [path] if path.is_file() else sorted(
            p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return hashlib.sha256(json.dumps(
        [(f.as_posix(), f.stat().st_size, f.stat().st_mtime_ns) for f in files]).encode()).hexdigest()


def bring_up_to_date():
    """Run `snakemake` (cleaned table and both full reports) unless nothing changed since its last success.

    Call with the render lock held.
    """
    state, now = build_state(), fingerprint()
    if state["fingerprint"] != now:
        subprocess.run(["snakemake", "--cores", "2"], cwd=ROOT, check=True)
        state["fingerprint"] = now


@st.cache_resource
def start_prebuild():
    """Build both full reports (all diseases, all years) in the background when the app starts.

    The most common choice is then ready at once. A request waits for this to finish.
    """
    state, lock = build_state(), render_lock()

    def build():
        with lock:
            try:
                bring_up_to_date()
                state["ok"] = True
            except subprocess.CalledProcessError:
                state["ok"] = False
        state["done"] = True

    threading.Thread(target=build, daemon=True).start()
    return state


def make_report(report, topics, years, upload):
    """Render reports/<report>.qmd for this choice, or reuse an identical earlier render.

    `topics` and `years` are empty / None for all of them. `upload` is the summary from
    upload_table.prepare(), or None for the project's own data.
    """
    if upload:
        results, source = UPLOADS / upload["sha256"][:12], upload["sha256"]
    else:
        bring_up_to_date()  # the cleaned table and the pre-built full reports
        stamp = (RESULTS / "harmonised.csv").stat()
        results, source = RESULTS, [stamp.st_size, stamp.st_mtime_ns]
    key = hashlib.sha256(json.dumps([report, topics, years, source]).encode()).hexdigest()[:12]
    output = OUT / f"{report}-{key}.html"
    if output.is_file():
        return "hit", output
    if not upload and not topics and not years:
        shutil.copyfile(SITE / f"{report}.html", output)
        shutil.copyfile(SITE / f"provenance_{report}.json", OUT / f"provenance_{output.stem}.json")
        return "hit", output
    render_quarto.render(report, results, output, data_root=None if upload else DATA_ROOT,
                         topics=topics, years=years)
    return "miss", output


@st.cache_data(show_spinner=False)
def prepare_upload(data: bytes, name: str):
    """Check an uploaded table and write its results folder; returns (summary, error)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / Path(name).name
        path.write_bytes(data)
        try:
            return upload_table.prepare(path, Path(name).name, UPLOADS), None
        except ValueError as exc:
            return None, str(exc)
        except Exception as exc:  # unreadable file: wrong format, broken Parquet, ...
            return None, f"the file could not be read ({exc})"


def set_diseases(groups, selected):
    for group, diseases in groups.items():
        st.session_state[f"group:{group}:{','.join(diseases)}"] = list(diseases) if selected else []


def choose_stakeholder(report):
    st.session_state["stakeholder"] = report


def step(text):
    st.markdown(f'<div class="step">{text}</div>', unsafe_allow_html=True)


def note(text):
    st.markdown(f'<div class="note">{text}</div>', unsafe_allow_html=True)


def centred(ratio=(1, 4, 1)):
    """The middle column of three, to keep a control compact and centred."""
    return st.columns(ratio)[1]


st.set_page_config(page_title="Infectious disease reports", page_icon="📊", layout="centered")
st.markdown(STYLE, unsafe_allow_html=True)
start_viewer()
prebuild = start_prebuild()

st.title("Infectious disease reports")
st.markdown('<div class="lead">Swiss and Liechtenstein notifiable-disease data from the Federal Office of '
            'Public Health (FOPH). Make your choices and press <b>Generate report</b>; '
            'the report opens in a new tab.</div>', unsafe_allow_html=True)
if not prebuild["done"]:
    note("Preparing the full reports in the background, so the default choice is ready at once...")
elif prebuild["ok"] is False:
    note("The background build of the full reports failed; see the container log. Reports are built on request.")

# Own data (optional, folded away): a reader's cleaned table instead of the project's.
upload, data_ready = None, True
with centred((1, 6, 1)).expander("📂 Use your own data (optional)"):
    if st.toggle("Use my own cleaned table instead of the FOPH data in this project"):
        data_ready = False
        file = st.file_uploader(
            "Cleaned table, as made by this pipeline (`results/harmonised.csv` or `harmonised.parquet`)",
            type=["csv", "parquet"])
        st.caption(f"Needed columns: {', '.join(upload_table.REQUIRED)}. The file is used only for your "
                   "reports; the project's data is not changed.")
        if file is not None:
            with st.spinner("Checking the table..."):
                upload, error = prepare_upload(file.getvalue(), file.name)
            if error:
                st.error(f"This table cannot be used: {error}")
            else:
                data_ready = True
                st.success(f"**{upload['name']}**: {upload['rows']:,} rows, {len(upload['diseases'])} report "
                           f"diseases, {upload['years'][0]} to {upload['years'][1]}.")

# 1. Stakeholder
step("1. Stakeholder")
st.session_state.setdefault("stakeholder", "researcher")
stakeholder = st.session_state["stakeholder"]
for column, (report, (icon, name, what)) in zip(centred((1, 8, 1)).columns(2), STAKEHOLDERS.items()):
    with column.container(border=True):
        st.markdown(f'<div class="card"><div class="icon">{icon}</div><div class="name">{name}</div>'
                    f'<div class="what">{what}</div></div>', unsafe_allow_html=True)
        chosen = report == stakeholder
        st.button("✓ Selected" if chosen else "Choose", key=f"stakeholder:{report}", width="stretch",
                  type="primary" if chosen else "secondary", on_click=choose_stakeholder, args=(report,))

# 2. Years
step("2. Years")
if upload:
    first, last = upload["years"]
else:
    parquet = RESULTS / "harmonised.parquet"
    first, last = year_range(parquet.stat().st_mtime_ns if parquet.is_file() else 0)
with centred((1, 3, 1)):
    if first < last:
        chosen_years = st.slider("Years", first, last, (first, last), label_visibility="collapsed")
    else:
        chosen_years = (first, last)
    span = str(chosen_years[0]) if chosen_years[0] == chosen_years[1] else f"{chosen_years[0]} – {chosen_years[1]}"
    st.markdown(f'<div class="years">{span}</div>', unsafe_allow_html=True)
note("Charts and tables over time show these years. The current status of each disease always uses "
     "the latest data, compared with the same week or month in the previous 5 to 10 years.")

# 3. Diseases (an uploaded table offers only the diseases it contains)
step("3. Diseases")
available = {g: {t: n for t, n in d.items() if not upload or t in upload["diseases"]} for g, d in GROUPS.items()}
available = {g: d for g, d in available.items() if d}
_, left, right, _ = st.columns([2, 1.2, 1.2, 2])
left.button("Select all", on_click=set_diseases, args=(available, True), width="stretch")
right.button("Clear", on_click=set_diseases, args=(available, False), width="stretch")
picked = set()
for group, diseases in available.items():
    key = f"group:{group}:{','.join(diseases)}"
    st.session_state.setdefault(key, list(diseases))  # every disease to start with
    picked |= set(st.pills(group, list(diseases), selection_mode="multi",
                           format_func=diseases.get, key=key) or [])
# The report's own disease order, whatever order the tiles were clicked in.
offered = [t for d in available.values() for t in d]
topics = [t for t in offered if t in picked]
note(f"{len(topics)} of {len(offered)} diseases selected")

st.divider()
generate = centred((2, 3, 2)).button("📄 Generate report", type="primary", width="stretch",
                                     disabled=not (topics and data_ready))

if generate:
    lock = render_lock()
    with st.spinner("Creating the report. A new choice takes about half a minute..."):
        # Waits for the background build or another reader's report.
        if not lock.acquire(timeout=900):
            st.warning("Another report is still being created. Please try again in a minute.")
        else:
            try:
                status, output = make_report(
                    stakeholder,
                    [] if topics == list(DISEASES) else topics,
                    None if chosen_years == (first, last) else list(chosen_years),
                    upload,
                )
                st.session_state["result"] = (status, str(output), time.time())
            except (subprocess.CalledProcessError, SystemExit, OSError):
                st.error("The report could not be built. See the container log for details.")
            finally:
                lock.release()

if "result" in st.session_state:
    status, path, stamp = st.session_state["result"]
    report = Path(path)
    provenance = report.with_name(f"provenance_{report.stem}.json")
    if report.is_file():
        st.success("Report ready." + (" (reused an identical earlier report)" if status == "hit" else ""))
        url = f"http://localhost:{VIEWER_PORT}/{report.name}"
        st.link_button("Open report in new tab", url, type="primary")
        left, right, _ = st.columns([1, 1, 4])
        left.download_button("Download report", report.read_bytes(), report.name, "text/html")
        if provenance.is_file():
            right.download_button("Download provenance", provenance.read_bytes(),
                                  provenance.name, "application/json")
        st.caption(
            "One self-contained HTML file: it works offline and can be emailed or put online. "
            "If your browser blocked the new tab, use the button above. "
            f"Saved in `{report.relative_to(ROOT).as_posix()}`."
        )
        if st.session_state.get("opened") != stamp:  # open once per new report, not on every rerun
            st.session_state["opened"] = stamp
            st.iframe(f'<!DOCTYPE html><script>window.open("{url}", "_blank");</script>', height=1)
