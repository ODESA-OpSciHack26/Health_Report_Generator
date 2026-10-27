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

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
AUDIENCES = ("researcher", "health_institution", "public")
SCHEMA = "health-report/tabular-render/1"
EMBED = re.compile(r'<script type="application/json" id="report-provenance">(.*?)</script>', re.S)
HELPERS = ("report_helpers.R", "audience_reports.R", "tabular_report.R", "dashboard.css")


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sources():
    paths = [HERE / "report_shared.qmd", Path(__file__),
             HERE / "tabular_bundle.py", HERE / "tabular_prepare.py", HERE / "tabular_input.py", HERE / "tabular_run.py"]
    paths += [HERE / "templates" / name for name in HELPERS]
    paths += [HERE / "config/stakeholders" / f"{audience}.json" for audience in AUDIENCES]
    return {path.relative_to(PROJECT).as_posix(): _hash(path) for path in paths}


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
    return {"schema": SCHEMA,
            "rendered_at_utc": datetime.now(timezone.utc).isoformat(),
            "output": {"format": "html", "documents": ["report.html", "methods.html"],
                       "shared_template": "scripts/health_pipeline/report_shared.qmd",
                       "shared_template_sha256": code["scripts/health_pipeline/report_shared.qmd"]},
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


def verify_tabular_reports(destination):
    """Check exact artifacts, hashes, reproduced bundle and HTML provenance.

    This is not independent rerendering or authentication of the intended source.
    HTML-byte hashes require an external trusted identity against wholesale replacement.
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
    expected = {"render_manifest.json", "bundle/manifest.json", "bundle/table.json",
                "bundle/provenance.json", *sources}
    expected |= {f"{audience}/{name}" for audience in AUDIENCES
                 for name in ("report.html", "methods.html", "provenance.json")}
    if names != expected:
        raise ValueError("Missing or unexpected rendered artifacts.")
    captured = {name: bundles._read_regular(root / name) for name in names}
    manifest = bundles._json_load(captured["render_manifest.json"])
    if (not isinstance(manifest, dict) or set(manifest) != {"schema", "artifacts"}
            or manifest["schema"] != SCHEMA):
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
    code = _sources()
    for audience in AUDIENCES:
        record = bundles._json_load(captured[f"{audience}/provenance.json"])
        try:
            stamp = datetime.fromisoformat(record["rendered_at_utc"])
            if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
                raise ValueError("Invalid UTC render timestamp.")
            software = record["software"]
            if (set(software) != {"python", "quarto", "R"}
                    or software["python"] != platform.python_version()
                    or any(not isinstance(value, str) or not value for value in software.values())):
                raise ValueError("Invalid recorded renderer software.")
            expected_record = _record(prepared, snapshot, audience, _profile(audience), software, code)
            expected_record["rendered_at_utc"] = record["rendered_at_utc"]
        except (KeyError, TypeError) as exc:
            raise ValueError("Invalid render provenance.") from exc
        if bundles._json_bytes(record) != bundles._json_bytes(expected_record):
            raise ValueError("Render provenance disagrees with verified bundle or profile.")
        for name in ("report.html", "methods.html"):
            text = captured[f"{audience}/{name}"].decode("utf-8")
            matches = EMBED.findall(text)
            if len(matches) != 1 or bundles._json_load(matches[0].replace("<\\/", "</").encode()) != record:
                raise ValueError("Embedded provenance differs from sidecar.")
            if (f'data-tabular-audience="{audience}"' not in text
                    or "table-filter" not in text):
                raise ValueError("Tabular audience or interactive table marker is missing.")
    return manifest


def render_tabular_reports(bundle, destination, *, quarto="quarto"):
    """Verify before Quarto, stage all three audiences, then publish as one set."""
    prepared = bundles.verify_prepared_bundle(bundle)
    destination = bundles._safe_path(destination)
    if not destination.name or not destination.parent.is_dir():
        raise ValueError("A named output and existing parent are required.")
    if os.path.lexists(destination):
        raise FileExistsError(str(destination))
    profiles = {audience: _profile(audience) for audience in AUDIENCES}
    software = {"python": platform.python_version(),
                "quarto": _tool_version([quarto, "--version"]),
                "R": _tool_version(["Rscript", "--version"])}
    code = _sources()
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        snapshot = bundles.publish_prepared_bundle(prepared, stage / "bundle")
        for audience in AUDIENCES:
            profile = profiles[audience]
            folder = stage / audience
            folder.mkdir()
            record = _record(prepared, snapshot, audience, profile, software, code)
            (folder / "provenance.json").write_bytes(bundles._json_bytes(record))
            with tempfile.TemporaryDirectory(prefix="health-tabular-render-") as work:
                work = Path(work)
                shutil.copyfile(HERE / "report_shared.qmd", work / "report.qmd")
                for name in HELPERS:
                    shutil.copyfile(HERE / "templates" / name, work / name)
                (work / "provenance.json").write_bytes(bundles._json_bytes(record))
                context = _context(prepared, profile)
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
                        "-M", "title:Uploaded table | " + profile["display_name"],
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
    arguments = parser.parse_args()
    render_tabular_reports(arguments.bundle, arguments.output, quarto=arguments.quarto)
    print("Verified tabular HTML reports published for all three audiences.")
