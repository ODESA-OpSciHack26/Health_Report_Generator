"""Local composer website: choose an audience, generate, optionally edit a saved copy.

One small stdlib HTTP service (no framework, no build tool, no CDN) in front of the existing
composition validator, workspace service, renderer, provenance and CLI replay:

* presets        fixed choices; a standard preset uses its maintained recipe and the saved
                 bundle for the same audience, so a mismatched pair cannot be selected;
* drafts         editing a standard creates one managed working copy (recipe plus editor-only
                 inclusion state) under the work root; the maintained recipe is never touched;
* generation     a bounded background job (one active render) that renders the exact snapshot
                 bytes through ``composer_workspace.render_preview`` -> ``publish.render``;
* serving        the page, the JSON API and the *completed* report package from one origin.

The browser never sends filesystem paths. It names a preset and an action; the server maps those
to configured directories and refuses anything outside them.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts" / "health_pipeline"))

import composer_workspace as workbench  # noqa: E402

WEB_DIR = HERE / "composer_web"
CUSTOM = "custom"
# The three maintained audiences are the standard choices; ``custom`` is an editing mode over
# the selected standard, never a fourth audience or a new stakeholder id.
AUDIENCES = (("researcher", "Researcher"),
             ("health_institution", "Health institution"),
             ("public", "Public"))
PRESET_IDS = tuple(preset for preset, _ in AUDIENCES) + (CUSTOM,)
JOB_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{10}$")
MAX_BODY = 64 * 1024
COLLECTION_EMPTY_MESSAGE = ("Select at least one disease, or turn off "
                            "‘Annual trends by disease’.")
# Identity of the renderer for reuse matching. Bump only when the inputs of this identity
# change meaning; records written with another version are not reused.
REUSE_VERSION = 1
REUSE_FILES = ("scripts/health_pipeline/publish.py",
               "scripts/health_pipeline/report_shared.qmd",
               "scripts/health_pipeline/templates/report_helpers.R",
               "scripts/health_pipeline/templates/audience_reports.R",
               "scripts/health_pipeline/templates/methods.qmd",
               "scripts/health_pipeline/templates/dashboard.css")
# Only these composition options are exposed on the website. reference-comparison.topic is
# deliberately absent: it selects a different saved result and changes analytical identities.
SITE_OPTIONS = {
    "series-collection": {"style": "presentation.style",
                          "default_topic": "presentation.default_topic"},
    "series-trend": {"style": "presentation.style"},
}
EDIT_ACTIONS = ("move-up", "move-down", "set-style", "set-topics", "set-default-open",
                "include", "exclude")
GEOGRAPHY_LABELS = {"CHFL": "Switzerland and Liechtenstein", "CH": "Switzerland"}
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".csv": "text/csv; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
}


class SiteError(Exception):
    """A user-facing error with an HTTP status."""

    def __init__(self, status, message, code="invalid_request"):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json_atomic(path, payload):
    path = Path(path)
    temporary = path.parent / f".tmp-{uuid.uuid4().hex}"
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@dataclass
class Job:
    job_id: str
    preset: str
    mode: str
    recipe_sha256: str
    classification: str | None = None
    classification_basis: str | None = None
    created_ns: int | None = field(default_factory=lambda: time.time_ns())
    reuse_key: str | None = None
    reuse_components: dict | None = None
    package_sha256: str | None = None
    package_files: int | None = None
    status: str = "queued"
    created_utc: str = field(default_factory=_now)
    started_utc: str | None = None
    finished_utc: str | None = None
    preview_dir: str | None = None
    error: str | None = None
    replay_command: str | None = None
    snapshot: str | None = None

    def as_dict(self):
        return {"job_id": self.job_id, "preset": self.preset, "mode": self.mode,
                "classification": self.classification,
                "classification_basis": self.classification_basis,
                "created_ns": self.created_ns,
                "reuse_key": self.reuse_key,
                "reuse_components": self.reuse_components,
                "package_sha256": self.package_sha256,
                "package_files": self.package_files,
                "recipe_sha256": self.recipe_sha256, "status": self.status,
                "created_utc": self.created_utc, "started_utc": self.started_utc,
                "finished_utc": self.finished_utc, "error": self.error,
                "replay_command": self.replay_command, "snapshot": self.snapshot,
                "preview_dir": self.preview_dir,
                "report_url": self.report_url, "open_url": self.report_url}

    @property
    def report_url(self):
        if self.status != "succeeded" or not self.preview_dir:
            return None
        return f"/reports/{self.job_id}/report.html"


class Site:
    """Server-side state: presets, drafts, jobs, artifact containment."""

    def __init__(self, work_root, inputs_root, data_root, recipes_root, workflow_config=None,
                 quarto="quarto", render=None, access_token=None):
        # Per-run authentication: a random token, written to a file only the local steward can
        # read and never printed to the service log. Every page, API and artifact request needs
        # the session cookie derived from it.
        self.access_token = access_token or secrets.token_urlsafe(24)
        self.session_cookie = "composer_session=" + hashlib.sha256(
            self.access_token.encode("utf-8")).hexdigest()[:32]
        self.work_root = Path(work_root).expanduser().resolve()
        self.inputs_root = Path(inputs_root).expanduser().resolve()
        self.data_root = Path(data_root).expanduser().resolve()
        self.recipes_root = Path(recipes_root).expanduser().resolve()
        self.workflow_config = Path(workflow_config).resolve() if workflow_config else None
        self.quarto = quarto
        self.render = render
        self.drafts_root = self.work_root / "drafts"
        self.jobs_root = self.work_root / "jobs"
        self.drafts_root.mkdir(parents=True, exist_ok=True)
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._environment = None
        self._environment_lock = threading.Lock()
        self._active: str | None = None
        self._threads: dict[str, threading.Thread] = {}
        self._recover_interrupted()

    # Fields a browser may see. Paths, snapshots and preview directories stay internal.
    PUBLIC_FIELDS = ("job_id", "preset", "mode", "classification", "status", "created_utc",
                     "started_utc", "finished_utc", "recipe_sha256", "error",
                     "replay_command", "report_url", "open_url")

    @classmethod
    def public_job(cls, payload):
        public = {key: payload.get(key) for key in cls.PUBLIC_FIELDS}
        # Records written before this revision carry bundle_id and no preset. The audience is
        # recorded evidence; the render mode is not, so it stays blank instead of being guessed.
        public["preset"] = public["preset"] or payload.get("bundle_id")
        return public

    def wait_idle(self, timeout=15.0):
        """Join any render workers (tests and shutdown); never used from a request handler."""
        with self._lock:
            threads = list(self._threads.values())
        for thread in threads:
            thread.join(timeout)

    # ------------------------------------------------------------------ presets
    def _recipe_path(self, preset):
        return self.recipes_root / f"{preset}.json"

    def _bundle_path(self, audience):
        return self.inputs_root / audience / "data"

    def _bundle_source(self, bundle):
        """Compact, honest source summary: what data a report for this choice describes."""
        stakeholder = _read_json(bundle / "stakeholder.json")
        manifest = _read_json(bundle / "bundle.json")
        included = 0
        selection = bundle / "selection.csv"
        if selection.is_file():
            import csv
            with selection.open(newline="", encoding="utf-8") as handle:
                included = sum(1 for row in csv.DictReader(handle)
                               if (row.get("status") or "").strip().lower() == "included")
        snapshot = manifest.get("snapshot_id") or ""
        return {"title": stakeholder.get("title"),
                "years": stakeholder.get("years") or [],
                "reference_year": stakeholder.get("reference_year"),
                "geography": GEOGRAPHY_LABELS.get(stakeholder.get("geography"),
                                                  stakeholder.get("geography")),
                "snapshot_id": snapshot,
                "snapshot_short": snapshot[:12],
                "included_topics": included}

    def preset(self, preset):
        """Resolve one standard choice to its maintained recipe and its own saved bundle."""
        if preset not in PRESET_IDS:
            raise SiteError(HTTPStatus.BAD_REQUEST, f"Unknown choice {preset!r}.")
        if preset == CUSTOM:
            raise SiteError(HTTPStatus.BAD_REQUEST,
                            "Custom is an editing mode over a standard choice, not a dataset.")
        recipe = self._recipe_path(preset)
        if not recipe.is_file():
            raise SiteError(HTTPStatus.NOT_FOUND,
                            f"The {preset!r} recipe is not installed in this deployment.")
        bundle = self._bundle_path(preset)
        if not (bundle / "bundle.json").is_file() or not (bundle / "stakeholder.json").is_file():
            raise SiteError(HTTPStatus.NOT_FOUND,
                            f"No saved bundle for {preset!r}; nothing is substituted for it.")
        audience = _read_json(bundle / "stakeholder.json").get("id")
        if audience != preset:
            raise SiteError(HTTPStatus.CONFLICT,
                            f"The saved bundle identifies itself as {audience!r}, "
                            f"not {preset!r}.")
        return recipe, bundle

    def _block_key(self, entry, eligible):
        """Semantic view of one block for default-vs-draft comparison (not an identity)."""
        block = entry["block"]
        key = {"block": block, "instance_id": entry["instance_id"],
               "topics": None, "default_topic": None}
        presentation = entry.get("presentation") or {}
        if block == "series-collection":
            topics = entry.get("topics")
            resolved = list(eligible) if topics == "eligible" else list(topics or [])
            key["topics"] = "eligible" if resolved == list(eligible) else resolved
            key["measure"] = entry.get("measure")
            key["years"] = entry.get("years")
            default = presentation.get("default_topic")
            key["default_topic"] = default or (resolved[0] if resolved else None)
        elif block == "series-trend":
            key["topic"] = entry.get("topic")
            key["measure"] = entry.get("measure")
            key["years"] = entry.get("years")
            key["default_topic"] = presentation.get("default_topic") or entry.get("topic")
        elif block == "reference-comparison":
            key["topic"] = entry.get("topic")
        key["style"] = presentation.get("style") or "standard"
        return key

    def _signature(self, composition, eligible):
        return {"contract": composition["contract"], "audience": composition["audience"],
                "blocks": [self._block_key(entry, eligible) for entry in composition["blocks"]]}

    def _differences(self, pending, maintained, eligible):
        """Structured, human-phrasable differences between the draft and its default."""
        default = self._signature(maintained, eligible)["blocks"]
        draft = self._signature(pending, eligible)["blocks"]
        by_default = {entry["instance_id"]: entry for entry in default}
        by_draft = {entry["instance_id"]: entry for entry in draft}
        excluded = [entry["instance_id"] for entry in default
                    if entry["instance_id"] not in by_draft]
        draft_order = [entry["instance_id"] for entry in draft]
        default_order = [entry["instance_id"] for entry in default
                         if entry["instance_id"] in by_draft]
        style = [key for key in draft_order
                 if by_draft[key]["style"] != by_default[key]["style"]]
        selection = [key for key in draft_order
                     if by_draft[key]["topics"] != by_default[key]["topics"]
                     or by_draft[key]["default_topic"] != by_default[key]["default_topic"]]
        return {"excluded": excluded, "reordered": draft_order != default_order,
                "style": style, "selection": selection}

    # ------------------------------------------------------------------ reuse identity
    @staticmethod
    def _tool_version(command):
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None
        text = (done.stdout or "").strip() or (done.stderr or "").strip()
        return text.splitlines()[0] if text else None

    def environment_identity(self):
        """Renderer/code/environment identity, computed once per process."""
        with self._environment_lock:
            if self._environment is not None:
                return self._environment
            files = {}
            for relative in REUSE_FILES:
                path = ROOT / relative
                files[relative] = workbench.file_digest(path) if path.is_file() else None
            workflow = self.workflow_config
            self._environment = {
                "files": files,
                "software": {"python": platform.python_version(),
                             "quarto": self._tool_version([self.quarto, "--version"]),
                             "R": self._tool_version(["Rscript", "--version"])},
                "workflow_config_sha256": (workbench.file_digest(workflow)
                                           if workflow and Path(workflow).is_file() else None),
            }
            return self._environment

    def _normalised_composition(self, recipe, eligible):
        """Canonical view used for matching only: equivalent settings compare equal."""
        blocks = []
        for entry in recipe["blocks"]:
            item = json.loads(json.dumps(entry))
            if item["block"] in ("series-collection", "series-trend"):
                presentation = dict(item.get("presentation") or {})
                presentation["style"] = presentation.get("style") or "standard"
                if item["block"] == "series-collection":
                    topics = item.get("topics")
                    resolved = list(eligible) if topics == "eligible" else list(topics or [])
                    item["topics"] = "eligible" if resolved == list(eligible) else resolved
                    presentation["default_topic"] = (presentation.get("default_topic")
                                                     or (resolved[0] if resolved else None))
                item["presentation"] = presentation
            blocks.append(item)
        return {**recipe, "blocks": blocks}

    def reuse_components(self, recipe, bundle, eligible):
        """Every input that can change the generated package, as one comparable record."""
        manifest = _read_json(Path(bundle) / "bundle.json")
        files = manifest.get("files") or {}
        manifest_digest = hashlib.sha256(
            "\n".join(f"{name}:{value}" for name, value in sorted(files.items()))
            .encode("utf-8")).hexdigest()
        normalised = self._normalised_composition(recipe, eligible)
        return {"version": REUSE_VERSION,
                "composition_sha256": hashlib.sha256(
                    workbench.recipe_bytes(normalised)).hexdigest(),
                "bundle": {"snapshot_id": manifest.get("snapshot_id"),
                           "manifest_sha256": manifest_digest,
                           "stakeholder_sha256": workbench.file_digest(
                               Path(bundle) / "stakeholder.json")},
                "environment": self.environment_identity(),
                "render": {"format": "html", "preview": True}}

    @staticmethod
    def reuse_key(components):
        return hashlib.sha256(json.dumps(components, sort_keys=True,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()

    def _package_digest(self, directory):
        directory = Path(directory)
        entries = []
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                return None, 0
            if path.is_file():
                entries.append(path.relative_to(directory).as_posix() + ":"
                               + workbench.file_digest(path))
        return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest(), len(entries)

    def _reuse_eligible(self, record, key):
        if record.get("status") != "succeeded":
            return False, "not a completed generation"
        if not record.get("reuse_key") or not record.get("package_sha256"):
            return False, "generated before reuse metadata existed"
        if record["reuse_key"] != key:
            return False, "settings, inputs or renderer differ"
        snapshot = self.work_root / (record.get("snapshot") or "")
        if not record.get("snapshot") or not snapshot.is_file():
            return False, "the recorded snapshot is missing"
        if workbench.file_digest(snapshot) != record.get("recipe_sha256"):
            return False, "the snapshot does not match its recorded digest"
        package = self.work_root / (record.get("preview_dir") or "")
        if not record.get("preview_dir") or not package.is_dir():
            return False, "the published package is missing"
        if not (package / "report.html").is_file():
            return False, "the report file is missing"
        digest_value, _count = self._package_digest(package)
        if digest_value is None:
            return False, "the package contains a symlink"
        if digest_value != record["package_sha256"]:
            return False, "the published files have changed"
        return True, None

    def _reuse_payload(self, record):
        return {"available": True, "job_id": record["job_id"],
                "created_utc": record.get("created_utc"),
                "finished_utc": record.get("finished_utc"),
                "recipe_sha256": record.get("recipe_sha256"),
                "classification": record.get("classification"),
                "package_files": record.get("package_files"),
                "report_url": f"/reports/{record['job_id']}/report.html",
                "replay_command": record.get("replay_command")}

    def _pending_recipe(self, preset):
        """The composition the editor currently describes, or raise if it is not renderable."""
        recipe_path, bundle = self.preset(preset)
        eligible = self.topics(preset)
        draft = self.draft(preset)
        if draft is None:
            return workbench.open_recipe(recipe_path), bundle, eligible
        problem = draft.pending_problem()
        if problem is not None:
            if problem["kind"] == "empty-selection":
                raise SiteError(HTTPStatus.BAD_REQUEST, COLLECTION_EMPTY_MESSAGE,
                                code="collection_empty")
            raise SiteError(HTTPStatus.BAD_REQUEST,
                            f"The draft cannot be generated yet: {problem['message']}",
                            code="draft_not_ready")
        return draft.pending(), bundle, eligible

    def reuse_candidate(self, preset):
        """Newest eligible successful job for the current pending settings, or None."""
        try:
            recipe, bundle, eligible = self._pending_recipe(preset)
        except SiteError:
            return None
        key = self.reuse_key(self.reuse_components(recipe, bundle, eligible))
        best = None
        for directory in sorted(self.jobs_root.glob("*"), reverse=True):
            record_path = directory / "job.json"
            if not record_path.is_file():
                continue
            try:
                record = _read_json(record_path)
            except (OSError, ValueError):
                continue
            allowed, _reason = self._reuse_eligible(record, key)
            if not allowed:
                continue
            stamp = (record.get("finished_utc") or record.get("created_utc") or "",
                     record.get("created_ns") or 0, record.get("job_id") or "")
            if best is None or stamp > best[0]:
                best = (stamp, record)
        return self._reuse_payload(best[1]) if best else None

    def confirm_reuse(self, preset, job_id):
        """Revalidate one retained job against the current settings before showing it."""
        recipe, bundle, eligible = self._pending_recipe(preset)
        key = self.reuse_key(self.reuse_components(recipe, bundle, eligible))
        record = self._job_record(job_id)
        allowed, reason = self._reuse_eligible(record, key)
        if not allowed:
            raise SiteError(HTTPStatus.CONFLICT,
                            f"That report can no longer be reused: {reason}.",
                            code="reuse_unavailable")
        return self._reuse_payload(record)

    def presets(self):
        entries = []
        for preset, label in AUDIENCES:
            entry = {"id": preset, "label": label, "available": True, "reason": None,
                     "source": None, "recipe_sha256": None, "draft": False,
                     "customized": False, "draft_error": None}
            try:
                recipe_path, bundle = self.preset(preset)
                entry["recipe_sha256"] = workbench.file_digest(recipe_path)
                entry["source"] = self._bundle_source(bundle)
            except SiteError as error:
                entry.update({"available": False, "reason": error.message})
                entries.append(entry)
                continue
            try:
                draft = self.draft(preset)
                if draft is not None:
                    eligible = self.topics(preset)
                    entry["draft"] = True
                    entry["customized"] = (
                        self._signature(draft.pending(), eligible)
                        != self._signature(workbench.open_recipe(recipe_path), eligible))
            except (SiteError, workbench.WorkspaceError) as error:
                # A broken draft does not take the audience away; it is reported, not hidden.
                entry["draft_error"] = str(error)
            entries.append(entry)
        entries.append({"id": CUSTOM, "label": "Custom", "available": False, "draft": False,
                        "customized": False, "draft_error": None, "source": None,
                        "recipe_sha256": None,
                        "reason": "Build from the block library — coming in the next revision."})
        return entries

    # ------------------------------------------------------------------ drafts
    def _draft_root(self, audience):
        if audience not in dict(AUDIENCES):
            raise SiteError(HTTPStatus.BAD_REQUEST, f"Unknown audience {audience!r}.")
        target = self.drafts_root / audience
        resolved = Path(os.path.realpath(target))
        if self.drafts_root.resolve() not in resolved.parents:
            raise SiteError(HTTPStatus.BAD_REQUEST, "Draft escapes the work root.")
        return resolved

    def draft(self, preset):
        """The saved custom copy for this audience, or None. Read-only."""
        audience = self.custom_audience(preset)
        root = self._draft_root(audience)
        if not (root / workbench.DRAFT_EDITOR).is_file():
            return None
        try:
            return workbench.open_draft(root)
        except workbench.WorkspaceError as error:
            raise SiteError(HTTPStatus.CONFLICT, str(error), code="draft_invalid") from None

    def custom_audience(self, preset):
        """Custom edits the selected standard, so it needs a standard choice."""
        if preset == CUSTOM:
            raise SiteError(HTTPStatus.BAD_REQUEST,
                            "Choose the standard audience this custom copy is based on.")
        self.preset(preset)
        return preset

    def ensure_draft(self, preset):
        """Create the managed working copy on an explicit action; resume an existing one."""
        existing = self.draft(preset)
        if existing is not None:
            return existing
        try:
            return workbench.create_draft(self._draft_root(preset), self._recipe_path(preset),
                                          based_on=preset)
        except workbench.WorkspaceError as error:
            raise SiteError(HTTPStatus.CONFLICT, str(error), code="draft_refused") from None

    def topics(self, audience):
        bundle = self._bundle_path(audience)
        try:
            return workbench.available_topics(bundle)
        except workbench.WorkspaceError as error:
            raise SiteError(HTTPStatus.CONFLICT, str(error), code="bundle_unreadable") from None

    def _block_document(self, recipe, excluded, eligible, pending_by_id):
        """Every saved section, included or not, with the values the editor should show."""
        document = []
        for entry in recipe["blocks"]:
            instance_id = entry["instance_id"]
            pending = pending_by_id.get(instance_id) or entry
            presentation = pending.get("presentation") or {}
            item = {"instance_id": instance_id, "block": entry["block"],
                    "included": instance_id not in excluded}
            reason = workbench.REQUIRED_BLOCKS.get(entry["block"])
            item["required"] = reason is not None
            item["required_reason"] = reason
            editable = []
            if "style" in SITE_OPTIONS.get(entry["block"], {}):
                item["style"] = presentation.get("style") or "standard"
                editable.append("style")
            if entry["block"] in workbench.SELECTABLE_BLOCKS:
                topics = pending.get("topics")
                selected = list(eligible) if topics == "eligible" else list(topics or [])
                default_topic = presentation.get("default_topic")
                item.update({"selected_topics": selected,
                             "default_topic": default_topic or (selected[0] if selected else None),
                             "topic_choices": list(eligible)})
                editable.extend(["topics", "default_topic"])
            item["editable"] = editable
            document.append(item)
        return document

    def editor_document(self, preset):
        """What the page shows for an audience: source summary, sections, draft readiness."""
        recipe_path, bundle = self.preset(preset)
        eligible = self.topics(preset)
        maintained = workbench.open_recipe(recipe_path)
        draft = self.draft(preset)
        if draft is None:
            pending = dict(maintained)
            excluded, revision, renderable = [], 0, maintained
        else:
            pending, excluded, revision = draft.pending(), list(draft.excluded), draft.revision
            renderable = draft.effective()
        pending_by_id = {entry["instance_id"]: entry for entry in pending["blocks"]}
        problem = draft.pending_problem() if draft is not None else None
        blocking = None
        if problem is not None:
            blocking = (COLLECTION_EMPTY_MESSAGE if problem["kind"] == "empty-selection"
                        else problem["message"])
        customized = (self._signature(pending, eligible)
                      != self._signature(maintained, eligible))
        return {"preset": preset, "label": dict(AUDIENCES)[preset], "audience": preset,
                "draft": draft is not None, "revision": revision,
                "customized": customized, "ready": problem is None,
                "blocking_reason": blocking,
                "differences": self._differences(pending, maintained, eligible),
                "source": self._bundle_source(bundle),
                "eligible_topics": list(eligible),
                "source_recipe_sha256": workbench.file_digest(recipe_path),
                "default_recipe_sha256": hashlib.sha256(
                    workbench.recipe_bytes(maintained)).hexdigest(),
                "renderable_sha256": hashlib.sha256(
                    workbench.recipe_bytes(renderable)).hexdigest(),
                "pending_sha256": hashlib.sha256(workbench.recipe_bytes(pending)).hexdigest(),
                "excluded": excluded,
                "reuse": self.reuse_candidate(preset),
                "blocks": self._block_document(draft.recipe if draft else maintained,
                                               excluded, eligible, pending_by_id),
                "required_blocks": dict(workbench.REQUIRED_BLOCKS)}

    def _plan_edit(self, draft, action, instance, value):
        """Map a website action onto the workspace service and validate it; writes nothing."""
        if action in ("move-up", "move-down", "include", "exclude"):
            return workbench.edit_plan(draft, action, instance)
        entry = next((item for item in draft.recipe["blocks"]
                      if item["instance_id"] == instance), None)
        if entry is None:
            raise SiteError(HTTPStatus.BAD_REQUEST, f"Unknown section {instance!r}.")
        option = SITE_OPTIONS.get(entry["block"], {}).get(
            action.replace("set-", "").replace("-", "_"))
        if option is None:
            raise SiteError(HTTPStatus.BAD_REQUEST,
                            f"Section {entry['block']!r} does not offer {action!r} "
                            "on this website.", code="option_not_exposed")
        return workbench.edit_plan(draft, "set-option", instance, value, option=option)

    def _probe_draft(self, preset):
        """A transient draft over the maintained recipe: validation without any write."""
        return workbench.Draft(
            root=self._draft_root(self.custom_audience(preset)),
            recipe=workbench.open_recipe(self._recipe_path(preset)),
            editor={"schema": workbench.DRAFT_SCHEMA_V2, "audience": preset,
                    "excluded": [], "selection": {}, "revision": 0})

    def save_draft_edit(self, preset, action, instance, value):
        """Apply one editor action and return the rebuilt document plus any notice."""
        if action not in EDIT_ACTIONS:
            raise SiteError(HTTPStatus.BAD_REQUEST, f"Unknown edit action {action!r}.")
        draft = self.draft(preset)                      # read-only: no copy is created here
        eligible = self.topics(preset)
        note = None
        try:
            if action in ("set-topics", "set-default-open"):
                # Disease choice is pending editor state: it may be incomplete on purpose.
                if draft is None:
                    workbench.plan_selection(self._probe_draft(preset), action, instance,
                                             value, eligible)
                    draft = self.ensure_draft(preset)
                selection, note = workbench.plan_selection(draft, action, instance, value,
                                                           eligible)
                workbench.commit_selection(draft, selection)
            else:
                if draft is None:
                    # Validate against the maintained recipe first, so a rejected action
                    # never leaves an empty copy behind.
                    self._plan_edit(self._probe_draft(preset), action, instance, value)
                    draft = self.ensure_draft(preset)
                recipe, excluded = self._plan_edit(draft, action, instance, value)
                workbench.commit_edit(draft, recipe, excluded)
        except workbench.WorkspaceError as error:
            raise SiteError(HTTPStatus.BAD_REQUEST, str(error), code="edit_rejected") from None
        document = self.editor_document(preset)
        if note:
            document["notes"] = [note]
        return document

    def reset_preset(self, preset):
        """Restore the copy to its maintained default in place; history is untouched."""
        draft = self.draft(preset)
        if draft is None:
            raise SiteError(HTTPStatus.CONFLICT,
                            "Nothing to reset: this audience has no custom copy.",
                            code="no_draft")
        try:
            workbench.reset_draft(draft, self._recipe_path(preset), based_on=preset)
        except workbench.WorkspaceError as error:
            raise SiteError(HTTPStatus.CONFLICT, str(error), code="reset_refused") from None
        return self.editor_document(preset)

    # ------------------------------------------------------------------ jobs
    def _job_dir(self, job_id):
        if not JOB_ID.fullmatch(str(job_id or "")):
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown job.")
        return self.jobs_root / job_id

    def _recover_interrupted(self):
        for directory in self.jobs_root.glob("*") if self.jobs_root.is_dir() else []:
            record = directory / "job.json"
            if not record.is_file():
                continue
            try:
                payload = _read_json(record)
            except (OSError, ValueError):
                continue
            if payload.get("status") in ("queued", "running"):
                payload["status"] = "interrupted"
                payload["finished_utc"] = _now()
                payload["error"] = ("The service stopped before this render finished; "
                                    "no report was produced.")
                _write_json_atomic(record, payload)

    def submit(self, preset):
        """Render the audience's current composition; the mode follows from the comparison."""
        recipe_path, bundle = self.preset(preset)
        eligible = self.topics(preset)
        maintained = workbench.open_recipe(recipe_path)
        draft = self.draft(preset)
        customized = False
        if draft is not None:
            customized = (self._signature(draft.pending(), eligible)
                          != self._signature(maintained, eligible))
        if customized:
            problem = draft.pending_problem()
            if problem is not None:
                if problem["kind"] == "empty-selection":
                    raise SiteError(HTTPStatus.BAD_REQUEST, COLLECTION_EMPTY_MESSAGE,
                                    code="collection_empty")
                raise SiteError(HTTPStatus.BAD_REQUEST,
                                f"The draft cannot be generated yet: {problem['message']}",
                                code="draft_not_ready")
            draft = workbench.commit_pending(draft, eligible)
            recipe = draft.effective()
            mode = "customized"
        else:
            recipe = maintained
            mode = "standard"
        audience = preset
        classification = ("customized" if (self._signature(recipe, eligible)
                                          != self._signature(maintained, eligible))
                          else "default")
        classification_basis = hashlib.sha256(workbench.recipe_bytes(maintained)).hexdigest()
        components = self.reuse_components(recipe, bundle, eligible)
        reuse_key = self.reuse_key(components)
        job_id = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-"
                  + uuid.uuid4().hex[:10])
        with self._lock:
            if self._active is not None:
                raise SiteError(HTTPStatus.CONFLICT,
                                "A render is already running; wait for it to finish.",
                                code="render_busy")
            self._active = job_id
        job_directory = self.jobs_root / job_id
        job = None
        try:
            job_directory.mkdir(parents=True)
            # Immutable bytes: the recipe (maintained, or the draft's effective view) is written
            # once, then hashed and re-validated through the shared loader, so a later edit
            # cannot change this job, its report or its replay command.
            snapshot = job_directory / "composition.json"
            with open(snapshot, "xb") as handle:
                handle.write(workbench.recipe_bytes(recipe))
                handle.flush()
                os.fsync(handle.fileno())
            recorded = workbench.open_recipe(snapshot)
            if recorded["audience"] != audience:
                raise SiteError(HTTPStatus.BAD_REQUEST,
                                f"Recipe audience {recorded['audience']!r} does not match the "
                                f"selected bundle {audience!r}.")
            package = job_directory / "package"
            job = Job(job_id=job_id, preset=preset, mode=mode,
                      recipe_sha256=workbench.file_digest(snapshot),
                      classification=classification,
                      classification_basis=classification_basis,
                      reuse_key=reuse_key, reuse_components=components,
                      snapshot=str(snapshot.relative_to(self.work_root)),
                      preview_dir=str(package.relative_to(self.work_root)))
            _, command = workbench.replay_command(
                recipe_path=snapshot, bundle=bundle, output_dir=job_directory / "replay",
                data_root=self.data_root, workflow_config=self.workflow_config)
            job.replay_command = command
            _write_json_atomic(job_directory / "job.json", job.as_dict())
            thread = threading.Thread(target=self._run, args=(job, snapshot, bundle, package),
                                      name=f"render-{job_id}", daemon=True)
            with self._lock:
                self._threads[job_id] = thread
            thread.start()
            return self.public_job(job.as_dict())
        except Exception as error:                      # noqa: BLE001 - always release the slot
            if job is not None:
                job.status = "failed"
                job.finished_utc = _now()
                job.error = f"{type(error).__name__}: {error}"
                try:
                    _write_json_atomic(job_directory / "job.json", job.as_dict())
                except OSError:
                    pass
            with self._lock:
                self._active = None
                self._threads.pop(job_id, None)
            if isinstance(error, SiteError):
                raise
            raise SiteError(HTTPStatus.INTERNAL_SERVER_ERROR,
                            "The render could not be started; nothing was replaced.",
                            code="submit_failed") from None

    def _run(self, job, snapshot, bundle, package):
        job_directory = self.jobs_root / job.job_id
        try:
            job.status = "running"
            job.started_utc = _now()
            _write_json_atomic(job_directory / "job.json", job.as_dict())
            result = workbench.render_preview(
                snapshot, bundle, package, quarto=self.quarto, data_root=self.data_root,
                workflow_config=self.workflow_config, render=self.render, origin=self.work_root)
            job.status = "succeeded"
            job.preview_dir = str(Path(result.directory).resolve().relative_to(self.work_root))
            digest_value, count = self._package_digest(package)
            job.package_sha256 = digest_value
            job.package_files = count
        except Exception as error:                      # noqa: BLE001 - recorded, sanitised
            job.status = "failed"
            job.error = f"{type(error).__name__}: {error}"
        finally:
            job.finished_utc = _now()
            _write_json_atomic(job_directory / "job.json", job.as_dict())
            with self._lock:
                self._active = None
                self._threads.pop(job.job_id, None)

    def _job_record(self, job_id):
        record = self._job_dir(job_id) / "job.json"
        if not record.is_file():
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown job.")
        payload = _read_json(record)
        if payload.get("status") == "succeeded":
            payload["report_url"] = f"/reports/{job_id}/report.html"
            payload["open_url"] = payload["report_url"]
        return payload

    def job(self, job_id):
        return self.public_job(self._job_record(job_id))

    def jobs(self):
        entries = []
        for directory in sorted(self.jobs_root.glob("*"), reverse=True):
            if not (directory / "job.json").is_file():
                continue
            entries.append(self.public_job(self._job_record(directory.name)))
        return entries[:20]

    def _snapshot_summary(self, payload):
        """What the job actually rendered, read from its own immutable snapshot."""
        path = payload.get("snapshot")
        if not path:
            return {"available": False, "blocks": [], "detail": "No snapshot was recorded."}
        target = Path(os.path.realpath(self.work_root / path))
        if self.work_root not in target.parents or not target.is_file():
            return {"available": False, "blocks": [],
                    "detail": "The recorded snapshot is no longer on disk."}
        try:
            recipe = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"available": False, "blocks": [],
                    "detail": "The recorded snapshot is not readable."}
        blocks = [{"block": entry.get("block"), "instance_id": entry.get("instance_id")}
                  for entry in recipe.get("blocks") or []]
        return {"available": True, "blocks": blocks, "block_count": len(blocks),
                "audience": recipe.get("audience"), "detail": None}

    def _current_reuse_context(self, preset):
        """The key and composition digest the current editor settings would render."""
        try:
            recipe, bundle, eligible = self._pending_recipe(preset)
        except SiteError:
            return None, None
        components = self.reuse_components(recipe, bundle, eligible)
        return (self.reuse_key(components), components["composition_sha256"])

    def _history_reuse_view(self, record, current_key, current_composition):
        """Why a retained report can (or cannot) be reused with the current settings.

        This is presentation metadata only: the job's own status and classification are never
        rewritten because it fails today's reuse check.
        """
        if record.get("status") != "succeeded":
            return {"eligible": False, "code": "not_completed",
                    "reason": "This report did not complete."}
        if not record.get("reuse_key") or not record.get("package_sha256"):
            return {"eligible": False, "code": "no_metadata",
                    "reason": "Older report: reuse metadata was not recorded."}
        if current_key is None:
            return {"eligible": False, "code": "settings_not_ready",
                    "reason": "Current settings are not valid, so nothing can be reused."}
        if record["reuse_key"] != current_key:
            return {"eligible": False, "code": "different_identity",
                    "reason": "Different settings, saved input, or renderer version."}
        allowed, reason = self._reuse_eligible(record, current_key)
        if not allowed:
            return {"eligible": False, "code": "artifact",
                    "reason": f"Not reusable: {reason}."}
        return {"eligible": True, "code": "eligible",
                "reason": "Matches the current settings and can be reused."}

    def _composition_match(self, record, current_composition):
        """Composition-only comparison (sections, order, diseases) for history display."""
        if current_composition is None:
            return "unknown"
        snapshot = self.work_root / (record.get("snapshot") or "")
        if not record.get("snapshot") or not snapshot.is_file():
            return "unknown"
        try:
            recipe = _read_json(snapshot)
            bundle = self._bundle_path(record.get("preset") or
                                       record.get("bundle_id") or "")
            eligible = self.topics(record.get("preset") or record.get("bundle_id") or "")
        except (OSError, ValueError, SiteError):
            return "unknown"
        components = self.reuse_components(recipe, bundle, eligible)
        return ("same" if components["composition_sha256"] == current_composition
                else "different")

    def saved(self):
        """Where the data and the managed copies live, plus honest history rows."""
        entries = []
        contexts = {}

        def context(audience):
            if audience not in dict(AUDIENCES):
                return None, None
            if audience not in contexts:
                contexts[audience] = self._current_reuse_context(audience)
            return contexts[audience]

        for directory in sorted(self.jobs_root.glob("*"), reverse=True):
            if not (directory / "job.json").is_file():
                continue
            payload = self._job_record(directory.name)
            item = self.public_job(payload)
            item["snapshot_summary"] = self._snapshot_summary(payload)
            item["classification_basis"] = payload.get("classification_basis")
            audience = payload.get("preset") or payload.get("bundle_id")
            key, composition = context(audience)
            item["reuse"] = self._history_reuse_view(payload, key, composition)
            item["composition_match"] = self._composition_match(payload, composition)
            entries.append(item)
        return {"work_root": self.work_root.as_posix(),
                "inputs_root": self.inputs_root.as_posix(),
                "drafts": sorted(path.name for path in self.drafts_root.glob("*")
                                 if (path / workbench.DRAFT_EDITOR).is_file()),
                "jobs": entries[:20]}

    # ------------------------------------------------------------------ artifacts
    def artifact(self, job_id, relative):
        record = self._job_record(job_id)
        if record.get("status") != "succeeded" or not record.get("preview_dir"):
            raise SiteError(HTTPStatus.NOT_FOUND, "No completed report for this job.")
        base = Path(os.path.realpath(self.work_root / record["preview_dir"]))
        if self.work_root not in base.parents:
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        target = Path(os.path.realpath(base / relative))
        if target != base and base not in target.parents:
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        if target.is_symlink() or base.is_symlink():
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        if not target.is_file():
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        content_type = CONTENT_TYPES.get(target.suffix.lower())
        if content_type is None:
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        return target, content_type


class Handler(BaseHTTPRequestHandler):
    server_version = "composer-site/2"
    sys_version = ""
    site: Site = None            # injected
    allowed_hosts: set = set()

    # ------------------------------------------------------------------ plumbing
    def log_message(self, fmt, *args):
        message = "%s %s" % (self.address_string(), fmt % args)
        # The only request carrying the run token is the entry URL; the token is a credential
        # and must not be copied into a log file or a terminal scrollback.
        message = re.sub(r"(token=)[^&\s\"]+", r"\1[redacted]", message)
        print(message, file=sys.stderr, flush=True)

    def _host_ok(self):
        host = (self.headers.get("Host") or "").strip()
        return host in self.allowed_hosts

    def _authorised(self):
        expected = self.site.session_cookie.split("=", 1)[1]
        for part in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "composer_session":
                return hmac.compare_digest(value, expected)
        return False

    def _token_matches(self):
        supplied = self._query().get("token", "")
        return bool(supplied) and hmac.compare_digest(supplied, self.site.access_token)

    def _deny(self):
        body = (b"<!DOCTYPE html><title>Composer access</title><p>This service needs its "
                b"per-run access token. Open the URL printed by the launcher, or read the token "
                b"file it named, and append <code>?token=&lt;token&gt;</code>.</p>")
        self._send(HTTPStatus.UNAUTHORIZED, body, "text/html; charset=utf-8",
                   {"WWW-Authenticate": 'Composer realm="local"'})

    def _send(self, status, body=b"", content_type="application/json", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, payload, extra=None):
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json", extra)

    def _error(self, error):
        if isinstance(error, SiteError):
            self._json(error.status, {"error": {"code": error.code, "message": error.message}})
        else:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR,
                       {"error": {"code": "internal", "message": "Internal error."}})

    def _query(self):
        return {key: values[-1] for key, values in
                parse_qs(urlparse(self.path).query, keep_blank_values=True).items()}

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            raise SiteError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length.")
        if length <= 0:
            raise SiteError(HTTPStatus.BAD_REQUEST, "A JSON body is required.")
        if length > MAX_BODY:
            raise SiteError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large.")
        if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
            raise SiteError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise SiteError(HTTPStatus.BAD_REQUEST, "Body is not valid JSON.")
        if not isinstance(payload, dict):
            raise SiteError(HTTPStatus.BAD_REQUEST, "Body must be a JSON object.")
        return payload

    def _check_mutation(self, action, payload, allowed_fields):
        # Cross-site protection: a custom header plus an Origin/Host agreement. A browser cannot
        # send the header cross-origin without a preflight, and this server answers no preflight.
        if (self.headers.get("X-Composer-Action") or "") != action:
            raise SiteError(HTTPStatus.FORBIDDEN, "Missing action header.", code="forbidden")
        origin = self.headers.get("Origin")
        if origin is not None:
            host = (self.headers.get("Host") or "").strip()
            if origin not in {f"http://{host}", f"https://{host}"}:
                raise SiteError(HTTPStatus.FORBIDDEN, "Cross-origin request refused.",
                                code="forbidden")
        unknown = set(payload) - set(allowed_fields)
        if unknown:
            raise SiteError(HTTPStatus.BAD_REQUEST,
                            f"Unknown field(s): {sorted(unknown)}")

    # ------------------------------------------------------------------ routes
    def do_GET(self):                                    # noqa: N802 - stdlib name
        try:
            if not self._host_ok():
                raise SiteError(HTTPStatus.BAD_REQUEST, "Unrecognised Host header.")
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                if not self._authorised():
                    if self._token_matches():
                        cookie = (f"{self.site.session_cookie}; Path=/; HttpOnly; "
                                  "SameSite=Strict")
                        return self._send(HTTPStatus.FOUND, b"", "text/html; charset=utf-8",
                                          {"Location": "/", "Set-Cookie": cookie})
                    return self._deny()
                return self._static("index.html")
            if not self._authorised():
                raise SiteError(HTTPStatus.UNAUTHORIZED, "Access token required.",
                                code="unauthorised")
            if path in ("/app.css", "/app.js"):
                return self._static(path.lstrip("/"))
            if path == "/api/presets":
                return self._json(HTTPStatus.OK, {"presets": self.site.presets()})
            if path == "/api/editor":
                return self._json(HTTPStatus.OK, self.site.editor_document(
                    self._query().get("preset", "")))
            if path == "/api/saved":
                return self._json(HTTPStatus.OK, self.site.saved())
            if path == "/api/jobs":
                return self._json(HTTPStatus.OK, {"jobs": self.site.jobs()})
            match = re.fullmatch(r"/api/jobs/([^/]+)", path)
            if match:
                return self._json(HTTPStatus.OK, self.site.job(match.group(1)))
            match = re.fullmatch(r"/reports/([^/]+)/(.*)", path)
            if match:
                target, content_type = self.site.artifact(match.group(1), match.group(2))
                body = target.read_bytes()
                headers = {}
                if content_type.startswith("text/html"):
                    # The report is its own document with inline scripts; embed same-origin only.
                    headers["Content-Security-Policy"] = "frame-ancestors 'self'"
                return self._send(HTTPStatus.OK, body, content_type, headers)
            raise SiteError(HTTPStatus.NOT_FOUND, "Not found.")
        except SiteError as error:
            return self._error(error)
        except Exception:                                # noqa: BLE001 - no tracebacks to client
            return self._error(None)

    def do_POST(self):                                   # noqa: N802 - stdlib name
        try:
            if not self._host_ok():
                raise SiteError(HTTPStatus.BAD_REQUEST, "Unrecognised Host header.")
            if not self._authorised():
                raise SiteError(HTTPStatus.UNAUTHORIZED, "Access token required.",
                                code="unauthorised")
            path = urlparse(self.path).path
            payload = self._body()
            if path == "/api/reuse":
                self._check_mutation("reuse", payload, {"preset", "job_id"})
                return self._json(HTTPStatus.OK, self.site.confirm_reuse(
                    payload.get("preset", ""), payload.get("job_id", "")))
            if path == "/api/reset":
                self._check_mutation("reset", payload, {"preset"})
                return self._json(HTTPStatus.OK,
                                  self.site.reset_preset(payload.get("preset", "")))
            if path == "/api/edit":
                self._check_mutation("edit", payload,
                                     {"preset", "action", "instance", "value"})
                return self._json(HTTPStatus.OK, self.site.save_draft_edit(
                    payload.get("preset", ""), payload.get("action", ""),
                    payload.get("instance", ""), payload.get("value")))
            if path == "/api/generate":
                self._check_mutation("generate", payload, {"preset"})
                return self._json(HTTPStatus.ACCEPTED,
                                  self.site.submit(payload.get("preset", "")))
            raise SiteError(HTTPStatus.NOT_FOUND, "Not found.")
        except SiteError as error:
            return self._error(error)
        except Exception:                                # noqa: BLE001 - no tracebacks to client
            return self._error(None)

    def _static(self, name):
        path = (WEB_DIR / name).resolve()
        if WEB_DIR.resolve() not in path.parents or not path.is_file():
            raise SiteError(HTTPStatus.NOT_FOUND, "Not found.")
        self._send(HTTPStatus.OK, path.read_bytes(),
                   CONTENT_TYPES.get(path.suffix, "application/octet-stream"))


def build_server(site, host="127.0.0.1", port=2719):
    handler = type("BoundHandler", (Handler,), {"site": site, "allowed_hosts": set()})
    server = ThreadingHTTPServer((host, port), handler)
    actual = server.server_address[1]
    # The Host allowlist uses the port actually bound, so an ephemeral test port works too.
    handler.allowed_hosts = {f"{host}:{actual}", f"127.0.0.1:{actual}", f"localhost:{actual}"}
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("COMPOSER_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("COMPOSER_PORT", "2719")))
    parser.add_argument("--work-root", default=os.environ.get("COMPOSER_WORK_ROOT",
                                                             str(ROOT / "results" / "workbench")))
    parser.add_argument("--inputs-root", default=os.environ.get("COMPOSER_INPUTS_ROOT",
                                                               "/inputs/reports"))
    parser.add_argument("--data-root", default=os.environ.get("COMPOSER_DATA_ROOT", "/inputs"))
    parser.add_argument("--recipes-root",
                        default=os.environ.get("COMPOSER_RECIPES_ROOT",
                                               str(ROOT / "scripts" / "health_pipeline" /
                                                   "config" / "composer" / "compositions")))
    parser.add_argument("--workflow-config",
                        default=os.environ.get("COMPOSER_WORKFLOW_CONFIG",
                                               str(ROOT / "workflow" / "config.yaml")))
    args = parser.parse_args(argv)
    if args.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("This service only binds to loopback.")
    site = Site(args.work_root, args.inputs_root, args.data_root, args.recipes_root,
                args.workflow_config)
    server = build_server(site, args.host, args.port)
    # The token is written to a local file and never echoed into the service log.
    token_path = site.work_root / "access-token.txt"
    token_path.write_text(site.access_token + "\n", encoding="utf-8")
    os.chmod(token_path, 0o600)
    print(f"Composer site ready on http://{args.host}:{args.port}/", flush=True)
    print(f"Open:   http://{args.host}:{args.port}/?token=<contents of {token_path}>", flush=True)
    print(f"work root: {site.work_root}", flush=True)
    print(f"inputs:    {site.inputs_root}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
