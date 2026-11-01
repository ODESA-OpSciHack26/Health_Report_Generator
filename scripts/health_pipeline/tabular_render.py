"""Opt-in verified tabular HTML reports from the canonical shared QMD."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import tabular_bundle as bundles
import source_identity
from tabular_describe import describe, normalize_report_options

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
AUDIENCES = ("researcher", "health_institution", "public")
SCHEMA = "health-report/tabular-render/1"
SCHEMA_V2 = "health-report/tabular-render/2"
EMBED = re.compile(r'<script type="application/json" id="report-provenance">(.*?)</script>', re.S)
HELPERS = ("report_helpers.R", "audience_reports.R", "tabular_report.R", "tabular_charts.R", "dashboard.css")
PILOT_FILES = ("pilot_document.py", "pilot_charts.py", "tabular_python.py",
               "tabular_render.py", "tabular_run.py", "tabular_bundle.py",
               "tabular_prepare.py", "tabular_input.py", "tabular_describe.py",
               "source_identity.py")
PILOT_LOCK = HERE / "requirements.pilot.lock.txt"
BASE_LOCK = HERE / "requirements.lock.txt"


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sources():
    paths = [HERE / "report_shared.qmd", Path(__file__),
             HERE / "tabular_bundle.py", HERE / "tabular_prepare.py", HERE / "tabular_input.py", HERE / "tabular_run.py", HERE / "tabular_describe.py"]
    paths += [HERE / "templates" / name for name in HELPERS]
    paths += [HERE / "config/stakeholders" / f"{audience}.json" for audience in AUDIENCES]
    return {path.relative_to(PROJECT).as_posix(): _hash(path) for path in paths}


def _pilot_sources():
    paths = [HERE / name for name in PILOT_FILES]
    paths.append(HERE / "templates" / "dashboard.css")
    paths += [HERE / "config/stakeholders" / f"{audience}.json" for audience in AUDIENCES]
    return {path.relative_to(PROJECT).as_posix(): _hash(path) for path in paths}


def _matplotlib_version():
    try:
        import importlib.metadata as metadata
        return metadata.version("matplotlib")
    except Exception as exc:  # explicit: the Python renderer requires its pilot environment
        raise ValueError(
            "the Python tabular renderer requires matplotlib from the frozen pilot "
            "environment; use --renderer r or install requirements.pilot.lock.txt") from exc


def _pilot_software(quarto):
    return {"python": platform.python_version(),
            "quarto": _tool_version([quarto, "--version"]),
            "matplotlib": _matplotlib_version(),
            "R": "not used"}


def _pilot_environment():
    return {"base_lock": BASE_LOCK.name, "base_lock_sha256": _hash(BASE_LOCK),
            "pilot_lock": PILOT_LOCK.name if PILOT_LOCK.is_file() else None,
            "pilot_lock_sha256": _hash(PILOT_LOCK) if PILOT_LOCK.is_file() else None,
            "python": platform.python_version(), "matplotlib": _matplotlib_version(),
            "note": ("experimental pilot environment derived from the production lock; "
                     "not a production resolution")}


def _record_python(prepared, snapshot, audience, profile, software, code, analysis,
                   identity, environment):
    record = _record_base(prepared, snapshot, audience, profile, software, code)
    record["schema"] = SCHEMA_V2
    record["output"] = {"format": "html",
                        "documents": ["report.html", "methods.html"],
                        "template": "health-report/tabular-python/2"}
    record["descriptive_analysis"] = {
        "schema": analysis["schema"], "path": "../analysis.json",
        "sha256": hashlib.sha256(bundles._json_bytes(analysis)).hexdigest(),
        "policy": analysis["policy"]}
    record["effective_parameters"]["report"] = analysis["parameters"]
    record["limitations"][0] = ("No cross-category totals or category-period pooling; descriptive "
                                "comparisons are not causal or clinical conclusions.")
    record["code"] = {"source_identity": identity,
                      "renderer": {"implementation": "python",
                                   "entry_point": "scripts/health_pipeline/tabular_python.py",
                                   "files": code},
                      "environment": environment}
    return record


def _profile(audience):
    cfg = json.loads((HERE / "config/stakeholders" / f"{audience}.json").read_text())
    if cfg["id"] != audience:
        raise ValueError("Audience profile identity mismatch.")
    profile = cfg["presentation"]
    layouts = {"researcher": ("technical", "full"),
               "health_institution": ("dashboard", "monitoring"),
               "public": ("editorial", "plain_language")}
    if (profile["layout"], profile["detail_level"]) != layouts[audience]:
        raise ValueError("Unsupported canonical audience profile.")
    return dict(profile)


def _rows_html(prepared):
    rows = json.loads(bundles._table_bytes(prepared.table))["rows"]
    cells = []
    for index, row in enumerate(rows, 1):
        fields = [str(index)] + ["Missing" if value is None else str(value) for value in row]
        cells.append("<tr>" + "".join("<td>" + html.escape(value) + "</td>" for value in fields) + "</tr>")
    return ('<div class="table-scroll"><table class="report-table" id="tabular-source-rows">'
            '<thead><tr><th>Source data row</th><th>Category</th><th>Value</th>'
            '<th>Period start</th></tr></thead><tbody>' + "".join(cells) + '</tbody></table></div>')


def _context(prepared, profile):
    pr = prepared.provenance
    return {"profile": profile, "rows_html": _rows_html(prepared),
            "source": pr["input"], "parameters": pr["parameters"],
            "output": pr["output"], "temporal_policy": pr["temporal_policy"]}


def _sections(profile):
    common = ["overview", "data-quality", "observations", "limitations", "provenance"]
    return common + (["parameters", "reproduction"] if profile["layout"] == "technical" else [])


def _tool_version(command):
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()


def _record(prepared, snapshot, audience, profile, software, code):
    output = {"format": "html", "documents": ["report.html", "methods.html"]}
    template_sha = code.get("scripts/health_pipeline/report_shared.qmd")
    if template_sha is not None:
        output["shared_template"] = "scripts/health_pipeline/report_shared.qmd"
        output["shared_template_sha256"] = template_sha
    return {"schema": SCHEMA,
            "rendered_at_utc": datetime.now(timezone.utc).isoformat(),
            "output": output,
            "stakeholder": {"id": audience, "presentation": profile},
            "effective_parameters": {"input_kind": "tabular", "audience": audience,
                                     "presentation": profile, "sections": _sections(profile),
                                     "preparation": prepared.provenance["parameters"]},
            "filters": [], "aggregation": "none",
            "data": {"publisher": "Reader-supplied table; source authenticity not established",
                     "bundle_path": "../bundle",
                     "manifest_sha256": _hash(snapshot / "manifest.json"),
                     "table_sha256": _hash(snapshot / "table.json"),
                     "preparation_provenance_sha256": _hash(snapshot / "provenance.json"),
                     "source_sha256": prepared.provenance["input"]["sha256"]},
            "preparation": prepared.provenance, "software": software,
            "code_files_on_disk": code,
            "limitations": ["No aggregation, disease classification, rates or causal interpretation.",
                            "Missing values are retained; no uncertainty intervals are calculated.",
                            "No upload-security, browser or external source-authenticity acceptance."]}



_context_base = _context

def _context(prepared, profile, report_options=None):
    context = _context_base(prepared, profile)
    context["analysis"] = describe(prepared, report_options)
    return context


_record_base = _record

def _record(prepared, snapshot, audience, profile, software, code, report_options=None):
    record = _record_base(prepared, snapshot, audience, profile, software, code)
    analysis = describe(prepared, report_options)
    record["descriptive_analysis"] = {
        "schema": analysis["schema"], "path": "../analysis.json",
        "sha256": hashlib.sha256(bundles._json_bytes(analysis)).hexdigest(),
        "policy": analysis["policy"],
    }
    record["effective_parameters"]["report"] = analysis["parameters"]
    record["limitations"][0] = "No cross-category totals or category-period pooling; descriptive comparisons are not causal or clinical conclusions."
    return record


def _validate_identity_shape(identity):
    """Shape-only validation: no checkout is required for basic package integrity."""
    expected = {"schema", "origin", "verification", "commit", "tree", "tracked_dirty",
                "staged_count", "unstaged_count", "untracked_inputs",
                "untracked_outside_inputs", "content", "collected_at_utc", "limits"}
    if not isinstance(identity, dict) or set(identity) != expected:
        raise ValueError("Invalid v2 source-identity block.")
    if identity["schema"] != "health-report/source-identity/1":
        raise ValueError("Invalid v2 source-identity schema.")
    if identity["origin"] not in ("host-supplied", "runtime-git", "unavailable"):
        raise ValueError("Invalid v2 source-identity origin.")
    if identity["verification"] not in ("supplied-digest-match", "computed-in-runtime"):
        raise ValueError("Invalid v2 source-identity verification.")
    content = identity["content"]
    if (not isinstance(content, dict) or set(content) != {"roots", "count", "digest"}
            or not isinstance(content["count"], int) or content["count"] < 0
            or not isinstance(content["digest"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", content["digest"])):
        raise ValueError("Invalid v2 source-identity content summary.")
    if not isinstance(content["roots"], list) or not all(
            isinstance(item, str) for item in content["roots"]):
        raise ValueError("Invalid v2 source-identity roots.")


def verify_tabular_reports(destination, *, verify_source=False):
    """Check exact artifacts, hashes, reproduced bundle and HTML provenance.

    v1 packages keep their original exact-record verification. v2 packages are checked for
    artifact/bundle/analysis/provenance integrity without requiring a checkout; passing
    ``verify_source=True`` additionally rebuilds the renderer/environment record from the
    current checkout and re-hashes the declared source inputs.
    """
    root = bundles._safe_path(destination)
    if not root.is_dir():
        raise ValueError("Report directory is missing.")
    paths = list(root.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("Symlinks are forbidden in reports.")
    if any(not path.is_file() and not path.is_dir() for path in paths):
        raise ValueError("Non-regular report artifacts are forbidden.")
    expected_dirs = {"bundle", *AUDIENCES}
    actual_dirs = {path.relative_to(root).as_posix() for path in paths if path.is_dir()}
    if actual_dirs != expected_dirs:
        raise ValueError("Unexpected report directory set.")
    names = {path.relative_to(root).as_posix() for path in paths if path.is_file()}
    sources = names & {"bundle/source.csv", "bundle/source.tsv"}
    if len(sources) != 1:
        raise ValueError("Expected one captured source.")
    expected = {"render_manifest.json", "analysis.json", "bundle/manifest.json", "bundle/table.json",
                "bundle/provenance.json", *sources}
    expected |= {f"{audience}/{name}" for audience in AUDIENCES
                 for name in ("report.html", "methods.html", "provenance.json")}
    if names != expected:
        raise ValueError("Missing or unexpected rendered artifacts.")
    captured = {name: bundles._read_regular(root / name) for name in names}
    manifest = bundles._json_load(captured["render_manifest.json"])
    if (not isinstance(manifest, dict) or set(manifest) != {"schema", "artifacts"}
            or manifest["schema"] not in (SCHEMA, SCHEMA_V2)):
        raise ValueError("Invalid render manifest.")
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != names - {"render_manifest.json"}:
        raise ValueError("Invalid render artifact set.")
    for name, description in artifacts.items():
        payload = captured[name]
        if (not isinstance(description, dict) or set(description) != {"sha256", "bytes"}
                or type(description["bytes"]) is not int
                or description["bytes"] != len(payload)
                or description["sha256"] != hashlib.sha256(payload).hexdigest()):
            raise ValueError("Rendered artifact hash or size mismatch.")
    prepared = bundles.verify_prepared_bundle(root / "bundle")
    snapshot = root / "bundle"
    saved_analysis = bundles._json_load(captured["analysis.json"])
    if not isinstance(saved_analysis, dict):
        raise ValueError("Invalid descriptive result object.")
    report_options = normalize_report_options(saved_analysis.get("parameters"))
    if captured["analysis.json"] != bundles._json_bytes(describe(prepared, report_options)):
        raise ValueError("Saved descriptive results differ from independently reproduced analysis.")
    version = manifest["schema"]
    code = _sources() if version == SCHEMA else _pilot_sources()
    for audience in AUDIENCES:
        record = bundles._json_load(captured[f"{audience}/provenance.json"])
        try:
            stamp = datetime.fromisoformat(record["rendered_at_utc"])
            if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
                raise ValueError("Invalid UTC render timestamp.")
            if record.get("schema") != version:
                raise ValueError("Render provenance schema differs from the manifest.")
            software = record["software"]
        except (KeyError, TypeError) as exc:
            raise ValueError("Invalid render provenance.") from exc
        if version == SCHEMA:
            if (set(software) != {"python", "quarto", "R"}
                    or software["python"] != platform.python_version()
                    or any(not isinstance(value, str) or not value for value in software.values())):
                raise ValueError("Invalid recorded renderer software.")
            expected_record = _record(prepared, snapshot, audience, _profile(audience),
                                      software, code, report_options)
            expected_record["rendered_at_utc"] = record["rendered_at_utc"]
            if bundles._json_bytes(record) != bundles._json_bytes(expected_record):
                raise ValueError("Render provenance disagrees with verified bundle or profile.")
        else:
            if (set(software) != {"python", "quarto", "matplotlib", "R"}
                    or software["python"] != platform.python_version()
                    or software["R"] != "not used"
                    or any(not isinstance(software[key], str) or not software[key]
                           for key in ("python", "quarto", "matplotlib"))):
                raise ValueError("Invalid recorded Python renderer software.")
            identity = (record.get("code") or {}).get("source_identity")
            _validate_identity_shape(identity)
            if verify_source:
                environment = _pilot_environment()
                expected_record = _record_python(prepared, snapshot, audience,
                                                 _profile(audience), software, code,
                                                 saved_analysis, identity, environment)
                expected_record["rendered_at_utc"] = record["rendered_at_utc"]
                if bundles._json_bytes(record) != bundles._json_bytes(expected_record):
                    raise ValueError("Render provenance disagrees with the current checkout.")
                current = source_identity.content_manifest(PROJECT)
                if (identity["content"]["digest"] != current["digest"]
                        or identity["content"]["count"] != current["count"]):
                    raise ValueError("Recorded source content does not match the current checkout.")
        for name in ("report.html", "methods.html"):
            text = captured[f"{audience}/{name}"].decode("utf-8")
            matches = EMBED.findall(text)
            if len(matches) != 1 or bundles._json_load(matches[0].replace("<\\/", "</").encode()) != record:
                raise ValueError("Embedded provenance differs from sidecar.")
            if (f'data-tabular-audience="{audience}"' not in text
                    or "table-filter" not in text):
                raise ValueError("Tabular audience or interactive table marker is missing.")
    return manifest


def _render_python_reports(prepared, destination, *, quarto, report_options,
                           source_identity_path):
    """Explicit Python candidate path; no R invocation and no fallback."""
    import tabular_python  # imported only for the selected Python renderer

    analysis = describe(prepared, report_options)
    profiles = {audience: _profile(audience) for audience in AUDIENCES}
    software = _pilot_software(quarto)
    code = _pilot_sources()
    identity = source_identity.resolve(PROJECT, source_identity_path)
    environment = _pilot_environment()
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        snapshot = bundles.publish_prepared_bundle(prepared, stage / "bundle")
        (stage / "analysis.json").write_bytes(bundles._json_bytes(analysis))
        for audience in AUDIENCES:
            profile = profiles[audience]
            folder = stage / audience
            folder.mkdir()
            context = _context(prepared, profile, report_options)
            context["audience"] = audience
            record = _record_python(prepared, snapshot, audience, profile, software, code,
                                    analysis, identity, environment)
            (folder / "provenance.json").write_bytes(bundles._json_bytes(record))
            with tempfile.TemporaryDirectory(prefix="health-tabular-python-") as work:
                work = Path(work)
                shutil.copyfile(HERE / "templates" / "dashboard.css", work / "dashboard.css")
                (work / "provenance.json").write_bytes(bundles._json_bytes(record))
                for document in ("report", "methods"):
                    figures = {}
                    tables = {}
                    (work / f"{document}.qmd").write_text(
                        tabular_python.quarto_document(context, document, record,
                                                      figures=figures, tables=tables),
                        encoding="utf-8")
                    subprocess.run([quarto, "render", f"{document}.qmd", "--to", "html",
                                    "--output", f"{document}.html"],
                                   cwd=work, env=os.environ.copy(), check=True)
                    result = work / f"{document}.html"
                    if not result.is_file() or result.stat().st_size == 0:
                        raise ValueError("Quarto returned without a nonempty document.")
                    rendered = tabular_python.doc.restore_figures(
                        result.read_text(encoding="utf-8"), figures)
                    rendered = tabular_python.doc.restore_tables(rendered, tables)
                    result.write_text(rendered, encoding="utf-8")
                    shutil.copyfile(result, folder / result.name)
        names = sorted(path.relative_to(stage).as_posix()
                       for path in stage.rglob("*") if path.is_file())
        manifest = {"schema": SCHEMA_V2, "artifacts": {
            name: {"bytes": (stage / name).stat().st_size, "sha256": _hash(stage / name)}
            for name in names}}
        (stage / "render_manifest.json").write_bytes(bundles._json_bytes(manifest))
        verify_tabular_reports(stage)
        bundles._rename_no_replace(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination


def render_tabular_reports(bundle, destination, *, quarto="quarto", report_options=None,
                           renderer="r", source_identity_path=None):
    """Verify before Quarto, stage all three audiences, then publish as one set.

    ``renderer='python'`` is the experimental pilot path. It is never selected implicitly and
    never falls back to R; its dependency failure is an actionable error.
    """
    if renderer not in ("r", "python"):
        raise ValueError(f"Unsupported tabular renderer: {renderer!r}")
    prepared = bundles.verify_prepared_bundle(bundle)
    report_options = normalize_report_options(report_options)
    destination = bundles._safe_path(destination)
    if not destination.name or not destination.parent.is_dir():
        raise ValueError("A named output and existing parent are required.")
    if os.path.lexists(destination):
        raise FileExistsError(str(destination))
    if renderer == "python":
        return _render_python_reports(prepared, destination, quarto=quarto,
                                      report_options=report_options,
                                      source_identity_path=source_identity_path)
    if source_identity_path:
        raise ValueError("source identity is supported only with --renderer python")
    analysis = describe(prepared, report_options)
    profiles = {audience: _profile(audience) for audience in AUDIENCES}
    software = {"python": platform.python_version(),
                "quarto": _tool_version([quarto, "--version"]),
                "R": _tool_version(["Rscript", "--version"])}
    code = _sources()
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        snapshot = bundles.publish_prepared_bundle(prepared, stage / "bundle")
        (stage / "analysis.json").write_bytes(bundles._json_bytes(analysis))
        for audience in AUDIENCES:
            profile = profiles[audience]
            folder = stage / audience
            folder.mkdir()
            record = _record(prepared, snapshot, audience, profile, software, code, report_options)
            (folder / "provenance.json").write_bytes(bundles._json_bytes(record))
            with tempfile.TemporaryDirectory(prefix="health-tabular-render-") as work:
                work = Path(work)
                shutil.copyfile(HERE / "report_shared.qmd", work / "report.qmd")
                for name in HELPERS:
                    shutil.copyfile(HERE / "templates" / name, work / name)
                (work / "provenance.json").write_bytes(bundles._json_bytes(record))
                context = _context(prepared, profile, report_options)
                context["audience"] = audience
                (work / "tabular_context.json").write_bytes(bundles._json_bytes(context))
                env = os.environ.copy()
                env["HEALTH_REPORT_PROJECT"] = str(PROJECT)
                env["R_PROFILE_USER"] = str(PROJECT / ".Rprofile")
                for document in ("report", "methods"):
                    parameters = {"data_dir": ".", "input_kind": "tabular",
                                  "tabular_document": document}
                    (work / "params.yml").write_bytes(bundles._json_bytes(parameters))
                    subprocess.run([
                        quarto, "render", "report.qmd", "--to", "html",
                        "--execute-params", "params.yml", "--output", f"{document}.html",
                        "-M", "title:" + report_options["title"] + " | " + profile["display_name"],
                    ], cwd=work, env=env, check=True)
                    result = work / f"{document}.html"
                    if not result.is_file() or result.stat().st_size == 0:
                        raise ValueError("Quarto returned without a nonempty document.")
                    shutil.copyfile(result, folder / result.name)
        names = sorted(path.relative_to(stage).as_posix()
                       for path in stage.rglob("*") if path.is_file())
        manifest = {"schema": SCHEMA, "artifacts": {
            name: {"bytes": (stage / name).stat().st_size, "sha256": _hash(stage / name)}
            for name in names}}
        (stage / "render_manifest.json").write_bytes(bundles._json_bytes(manifest))
        verify_tabular_reports(stage)
        bundles._rename_no_replace(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--quarto", default="quarto")
    parser.add_argument("--renderer", choices=("r", "python"), default="r")
    parser.add_argument("--source-identity")
    arguments = parser.parse_args()
    render_tabular_reports(arguments.bundle, arguments.output, quarto=arguments.quarto,
                           renderer=arguments.renderer,
                           source_identity_path=arguments.source_identity)
    print("Verified tabular HTML reports published for all three audiences.")
