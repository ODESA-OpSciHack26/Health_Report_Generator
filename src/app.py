"""Home page: choose who the report is for, the data, the years and the diseases, get one HTML report.

Run inside the report image: `docker compose up app`, then open
http://localhost:8501. Nothing here calculates statistics: it brings the cleaned
table up to date with Snakemake (or prepares an uploaded table: upload_table.py for
this pipeline's own format, general_table.py for any other CSV) and renders
reports/<report>.qmd with render_quarto.py, the same code as `snakemake`.
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

import general_table  # noqa: E402
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
# The same two audiences for any uploaded table (reports/general.qmd writes one view for each).
GENERAL_STAKEHOLDERS = {
    "researcher": ("🔬", "Researcher",
                   "How was the table read, and can I check it? Columns, data checks, every statistic, "
                   "time structure and methods."),
    "public_health": ("🏥", "Public health officials",
                      "What changed, and where? Key points first, the largest groups and the latest change."),
}
# data source -> (option shown, what it gives)
SOURCES = {
    "foph": ("🏥 FOPH dataset", "Swiss and Liechtenstein notifiable-disease data in this project: reports for "
                               "researchers or public health officials."),
    "upload": ("📂 Upload your CSV", "Any CSV, TSV or Parquet file: charts and tables of its numbers, over time "
                                    "and by group."),
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
.stRadio [role="radiogroup"] { justify-content: center; gap: 2.5rem; }
.stRadio [role="radiogroup"] p { font-size: 1.15rem; font-weight: 600; }
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
def upload_lock():
    """Reports of uploaded tables share nothing with Snakemake, so they do not wait for its background build."""
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


def is_general(upload):
    return bool(upload) and upload.get("kind") == "general"


def make_report(report, topics, years, upload, groups=None, audience=None):
    """Render reports/<report>.qmd for this choice, or reuse an identical earlier render.

    `topics`, `years` and `groups` are empty / None for all of them. `upload` is the summary
    from upload_table.prepare() or general_table.prepare(), or None for the project's own data.
    `audience` picks the view of the general report.
    """
    if upload:
        folder = ("general-" if is_general(upload) else "") + upload["sha256"][:12]
        results, source = UPLOADS / folder, upload["sha256"]
    else:
        bring_up_to_date()  # the cleaned table and the pre-built full reports
        stamp = (RESULTS / "harmonised.csv").stat()
        results, source = RESULTS, [stamp.st_size, stamp.st_mtime_ns]
    key = hashlib.sha256(json.dumps([report, topics, years, source] + ([groups] if groups else [])
                                    + ([audience] if audience else [])).encode()).hexdigest()[:12]
    output = OUT / f"{report}{'_' + audience if audience else ''}-{key}.html"
    if output.is_file():
        return "hit", output
    if not upload and not topics and not years:
        shutil.copyfile(SITE / f"{report}.html", output)
        shutil.copyfile(SITE / f"provenance_{report}.json", OUT / f"provenance_{output.stem}.json")
        return "hit", output
    render_quarto.render(report, results, output, data_root=None if upload else DATA_ROOT,
                         topics=topics, years=years, groups=groups, audience=audience)
    return "miss", output


@st.cache_data(show_spinner=False)
def prepare_upload(data: bytes, name: str):
    """Check an uploaded table and write its results folder; returns (summary, error).

    A table with every column the disease reports read goes to them (upload_table.py);
    any other table goes to the general report (general_table.py).
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / Path(name).name
        path.write_bytes(data)
        try:
            if set(upload_table.REQUIRED) <= set(general_table.columns_of(path)):
                return upload_table.prepare(path, Path(name).name, UPLOADS), None
            return general_table.prepare(path, Path(name).name, UPLOADS), None
        except ValueError as exc:
            return None, str(exc)
        except Exception as exc:  # unreadable file: wrong format, broken Parquet, ...
            return None, f"the file could not be read ({exc})"


def set_diseases(groups, selected):
    for group, diseases in groups.items():
        st.session_state[f"group:{group}:{','.join(diseases)}"] = list(diseases) if selected else []


def set_values(key, values):
    st.session_state[key] = list(values)


def choose_stakeholder(report):
    st.session_state["stakeholder"] = report


def choose_audience(cards):
    """Two stakeholder cards; returns the chosen report id."""
    st.session_state.setdefault("stakeholder", "researcher")
    chosen_one = st.session_state["stakeholder"]
    for column, (report, (icon, name, what)) in zip(centred((1, 8, 1)).columns(2), cards.items()):
        with column.container(border=True):
            st.markdown(f'<div class="card"><div class="icon">{icon}</div><div class="name">{name}</div>'
                        f'<div class="what">{what}</div></div>', unsafe_allow_html=True)
            chosen = report == chosen_one
            st.button("✓ Selected" if chosen else "Choose", key=f"stakeholder:{report}", width="stretch",
                      type="primary" if chosen else "secondary", on_click=choose_stakeholder, args=(report,))
    return chosen_one


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

def choose_years(first, last, explain):
    """The years slider; returns the chosen (first, last)."""
    with centred((1, 3, 1)):
        if first < last:
            chosen = st.slider("Years", first, last, (first, last), label_visibility="collapsed")
        else:
            chosen = (first, last)
        span = str(chosen[0]) if chosen[0] == chosen[1] else f"{chosen[0]} – {chosen[1]}"
        st.markdown(f'<div class="years">{span}</div>', unsafe_allow_html=True)
    note(explain)
    return chosen


st.title("Health data reports")
st.markdown('<div class="lead">Start from the Federal Office of Public Health (FOPH) surveillance data in this '
            'project, or upload your own table. Make your choices and press <b>Generate report</b>; '
            'the report opens in a new tab.</div>', unsafe_allow_html=True)

# 1. Data: the project's FOPH data, or a reader's own table.
step("1. Data")
with centred((1, 6, 1)):
    source = st.radio("Data", list(SOURCES), format_func=lambda s: SOURCES[s][0], key="source",
                      horizontal=True, label_visibility="collapsed")
note(SOURCES[source][1])
if source == "foph":
    if not prebuild["done"]:
        note("Preparing the full reports in the background, so the default choice is ready at once...")
    elif prebuild["ok"] is False:
        note("The background build of the full reports failed; see the container log. "
             "Reports are built on request.")

upload, data_ready = None, True
if source == "upload":
    data_ready = False
    with centred((1, 6, 1)):
        file = st.file_uploader("Any table: CSV, TSV or Parquet", type=["csv", "tsv", "txt", "parquet"])
        st.caption("Any table works, filtered or not: you get charts and tables of its numbers, over time when "
                   "it has a date or year column, and split by its text columns. A table in this pipeline's own "
                   "format (harmonised.csv) gets the full disease reports instead. Your file is used only for "
                   "your reports.")
        if file is not None:
            with st.spinner("Checking the table..."):
                upload, error = prepare_upload(file.getvalue(), file.name)
            if error:
                st.error(f"This table cannot be used: {error}")
            elif is_general(upload):
                data_ready = True
                shown = f"over time by **{upload['time']}** ({upload['period']}s)" if upload["time"] else \
                    "as a snapshot (no date or year column found)"
                st.success(f"**{upload['name']}**: {upload['rows']:,} rows. Numbers: "
                           f"{', '.join(m['name'] for m in upload['measures'])}. Groups: "
                           f"{', '.join(upload['groups']) or 'none'}. Shown {shown}.")
            else:
                data_ready = True
                st.success(f"**{upload['name']}**: {upload['rows']:,} rows, {len(upload['diseases'])} report "
                           f"diseases, {upload['years'][0]} to {upload['years'][1]}.")
# An uploaded table gets its report at once, shown right here; the steps below can change it.
result_area = centred((1, 6, 1)).container() if upload else None

groups, audience = None, None
if is_general(upload):
    # Any other table: the general report, in the chosen audience's view; then its years and main groups.
    step("2. Stakeholder")
    report_id, topics = "general", []
    audience = choose_audience(GENERAL_STAKEHOLDERS)
    step("3. Years")
    if upload["years"]:
        first, last = upload["years"]
        chosen_years = choose_years(first, last, "Charts and tables over time show these years.")
    else:
        first = last = chosen_years = None
        note("Your table has no date or year column, so the report shows it as one snapshot.")
    main = upload["main_group"]
    if main:
        step(f"4. {main}")
        values = upload["main_group_values"]
        key = f"general:{upload['sha256'][:12]}"
        st.session_state.setdefault(key, list(values))
        _, left, right, _ = st.columns([2, 1.2, 1.2, 2])
        left.button("Select all", on_click=set_values, args=(key, values), width="stretch")
        right.button("Clear", on_click=set_values, args=(key, []), width="stretch")
        picked = st.pills(main, values, selection_mode="multi", key=key, label_visibility="collapsed") or []
        chosen = [v for v in values if v in picked]
        if len(chosen) < len(values) or upload["main_group_more"]:
            groups = chosen
        note(f"{len(chosen)} of {len(values)} selected" + (f" (the {len(values)} largest are listed)"
                                                            if upload["main_group_more"] else ""))
        data_ready = data_ready and bool(chosen)
elif source == "upload" and not upload:
    note("Upload a table to see the next steps.")
else:
    # 2. Stakeholder
    step("2. Stakeholder")
    report_id = choose_audience(STAKEHOLDERS)

    # 3. Years
    step("3. Years")
    if upload:
        first, last = upload["years"]
    else:
        parquet = RESULTS / "harmonised.parquet"
        first, last = year_range(parquet.stat().st_mtime_ns if parquet.is_file() else 0)
    chosen_years = choose_years(
        first, last, "Charts and tables over time show these years. The current status of each disease always "
                     "uses the latest data, compared with the same week or month in the previous 5 to 10 years.")

    # 4. Diseases (an uploaded table offers only the diseases it contains)
    step("4. Diseases")
    available = {g: {t: n for t, n in d.items() if not upload or t in upload["diseases"]}
                 for g, d in GROUPS.items()}
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
    data_ready = data_ready and bool(topics)

st.divider()
generate = centred((2, 3, 2)).button("📄 Generate report", type="primary", width="stretch",
                                     disabled=not data_ready)

# A newly uploaded table is reported once straight away, with the choices as they start.
auto = bool(upload) and data_ready and st.session_state.get("auto") != upload["sha256"]
if auto:
    st.session_state["auto"] = upload["sha256"]
result_area = result_area or st.container()

if generate or auto:
    lock = upload_lock() if upload else render_lock()
    with result_area, st.spinner("Creating the report. A new choice takes about half a minute..."):
        # Waits for another reader's report (and, for the project's data, the background build).
        if not lock.acquire(timeout=900):
            st.warning("Another report is still being created. Please try again in a minute.")
        else:
            try:
                status, output = make_report(
                    report_id,
                    [] if topics == list(DISEASES) else topics,
                    None if chosen_years == (first, last) else list(chosen_years),
                    upload,
                    groups,
                    audience,
                )
                st.session_state["result"] = (status, str(output), time.time())
            except (subprocess.CalledProcessError, SystemExit, OSError):
                st.error("The report could not be built. See the container log for details.")
            finally:
                lock.release()

status, path, stamp = st.session_state.get("result", (None, "", None))
report = Path(path) if path else None
if report and report.is_file():
    provenance = report.with_name(f"provenance_{report.stem}.json")
    with result_area:
        st.success("Report ready." + (" (reused an identical earlier report)" if status == "hit" else ""))
        url = f"http://localhost:{VIEWER_PORT}/{report.name}"
        st.link_button("Open report in new tab", url, type="primary")
        downloads = [("Download report", report, "text/html"),
                     ("Download provenance", provenance, "application/json"),
                     # the general report also saves the rows it used and its summary statistics
                     ("Download data (CSV)", report.with_name(f"{report.stem}_data.csv"), "text/csv"),
                     ("Download summary (CSV)", report.with_name(f"{report.stem}_summary.csv"), "text/csv")]
        downloads = [d for d in downloads if d[1].is_file()]
        for column, (text, file, kind) in zip(st.columns(len(downloads)), downloads):
            column.download_button(text, file.read_bytes(), file.name, kind)
        st.caption(
            "One self-contained HTML file: it works offline and can be emailed or put online. "
            "If your browser blocked the new tab, use the button above. "
            + ("Change the choices below and press **Generate report** for another version. " if upload else "")
            + f"Saved in `{report.relative_to(ROOT).as_posix()}`."
        )
        if st.session_state.get("opened") != stamp:  # open once per new report, not on every rerun
            st.session_state["opened"] = stamp
            st.iframe(f'<!DOCTYPE html><script>window.open("{url}", "_blank");</script>', height=1)
