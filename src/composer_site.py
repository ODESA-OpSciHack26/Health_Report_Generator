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
import composer_library as library  # noqa: E402
import neutral_describe as neutral
import neutral_library as neutral_lib
import neutral_identity as neutral_identity
import neutral_display as neutral_display

WEB_DIR = HERE / "composer_web"
CUSTOM = "custom"
# The three maintained audiences are the standard choices; ``custom`` is an editing mode over
# the selected standard, never a fourth audience or a new stakeholder id.
AUDIENCES = (("researcher", "Researcher"),
             ("health_institution", "Health institution"),
             ("public", "Public"))
PRESET_IDS = tuple(preset for preset, _ in AUDIENCES) + (CUSTOM,)
NEUTRAL_AUDIENCE = neutral_lib.NEUTRAL_AUDIENCE
JOB_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{10}$")
MAX_BODY = 64 * 1024
NEUTRAL_MAX_BODY = neutral.LIMITS["max_upload_bytes"] + 64 * 1024
COLLECTION_EMPTY_MESSAGE = ("Select at least one disease, or turn off "
                            "‘Annual trends by disease’.")
# Identity of the renderer for reuse matching. Bump only when the inputs of this identity
# change meaning; records written with another version are not reused.
REUSE_VERSION = 1
REUSE_FILES = ("scripts/health_pipeline/publish.py",
               "scripts/health_pipeline/source_identity.py",
               "scripts/health_pipeline/report_shared.qmd",
               "scripts/health_pipeline/templates/report_helpers.R",
               "scripts/health_pipeline/templates/audience_reports.R",
               "scripts/health_pipeline/templates/methods.qmd",
               "scripts/health_pipeline/templates/dashboard.css")
# Only these composition options are exposed on the website. reference-comparison.topic is
# deliberately absent: it selects a different saved result and changes analytical identities.
SITE_OPTIONS = {
    "series-collection": {"style": "presentation.style",
                          "default_topic": "presentation.default_topic",
                          "layout": "presentation.layout"},
    "series-trend": {"style": "presentation.style"},
}
EDIT_ACTIONS = ("move-up", "move-down", "set-style", "set-layout", "set-topics",
                "set-default-open", "set-title", "include", "exclude")
# Custom composition mode: the same draft machinery over the registered block library, plus
# explicit replacement/discard for singleton and mutually exclusive sections.
CUSTOM_ACTIONS = ("add-block", "remove", "restore", "move-up", "move-down", "duplicate",
                  "delete-instance", "repair-draft", "set-option", "set-topics",
                  "set-default-open", "set-title", "replace-pending", "discard-pending")
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
    context: str | None = None
    origin: str = "preset"
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
                "context": self.context, "origin": self.origin,
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
        self._analysis_cache: dict = {}
        self._csv_environment_cache = None
        self._environment = None
        self._environment_lock = threading.Lock()
        self._active: str | None = None
        self._threads: dict[str, threading.Thread] = {}
        self._recover_interrupted()

    # Fields a browser may see. Paths, snapshots and preview directories stay internal.
    PUBLIC_FIELDS = ("job_id", "preset", "mode", "classification", "status", "created_utc",
                     "started_utc", "finished_utc", "recipe_sha256", "error",
                     "replay_command", "report_url", "open_url", "origin", "context")

    @classmethod
    def public_job(cls, payload):
        public = {key: payload.get(key) for key in cls.PUBLIC_FIELDS}
        # Records written before this revision carry bundle_id and no preset. The audience is
        # recorded evidence; the render mode is not, so it stays blank instead of being guessed.
        public["preset"] = public["preset"] or payload.get("bundle_id")
        # Records written before composition modes existed are preset work; a custom job is only
        # called custom when it recorded both the mode and its data context.
        if not public.get("origin"):
            public["origin"] = ("custom" if (payload.get("preset") == CUSTOM
                                             and payload.get("context")) else "preset")
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
            key["layout"] = presentation.get("layout") or "panels"
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
        layout = [key for key in draft_order
                  if by_draft[key].get("layout") != by_default[key].get("layout")]
        return {"excluded": excluded, "reordered": draft_order != default_order,
                "style": style, "selection": selection, "layout": layout}

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

    def _best_reuse(self, key):
        """Newest eligible successful job for a reuse key, or None."""
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
        return best[1] if best else None

    def reuse_candidate(self, preset):
        """Newest eligible successful job for the current pending settings, or None."""
        try:
            recipe, bundle, eligible = self._pending_recipe(preset)
        except SiteError:
            return None
        key = self.reuse_key(self.reuse_components(recipe, bundle, eligible))
        found = self._best_reuse(key)
        return self._reuse_payload(found) if found else None

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

    def confirm_reuse_custom(self, context, job_id):
        """Revalidate one retained job against the current custom composition."""
        context = self._custom_context(context)
        _recipe_path, bundle = self.preset(context)
        eligible = list(self.topics(context))
        draft = self.custom_draft(context)
        if draft is None:
            recipe = library.initial_recipe(context)
        else:
            problem = draft.pending_problem()
            if problem is not None:
                raise SiteError(HTTPStatus.BAD_REQUEST, problem["message"],
                                code="draft_not_ready")
            recipe = draft.pending()
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
        # Custom is a composition mode over one saved data context, not a fourth stakeholder and
        # not another audience preset. It is offered whenever at least one context can be read.
        usable = [entry["id"] for entry in entries if entry["available"]]
        entries.append({"id": CUSTOM, "label": "Custom", "available": bool(usable),
                        "draft": False, "customized": False, "draft_error": None,
                        "source": None, "recipe_sha256": None, "mode": "composition",
                        "detail": "Compose a report from the block library over one saved data "
                                  "context.",
                        "reason": (None if usable else
                                   "No saved data context is installed, so nothing can be "
                                   "composed.")})
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
        """Every saved section, included or not, with the values the editor should show.

        The shape here is shared with the Custom editor: the same keys drive the same
        frontend controls. Only ``editable`` differs by mode, which is what keeps the
        accepted audience surface unchanged while Custom exposes the options its blocks
        already support.
        """
        document = []
        for entry in recipe["blocks"]:
            instance_id = entry["instance_id"]
            pending = pending_by_id.get(instance_id) or entry
            presentation = pending.get("presentation") or {}
            spec = library.LIBRARY.get(entry["block"]) or {}
            item = {"instance_id": instance_id, "block": entry["block"],
                    "label": spec.get("label") or entry["block"],
                    "description": spec.get("description") or "",
                    "included": instance_id not in excluded,
                    "repeatable": spec.get("repeatable", False),
                    "repeat_reason": spec.get("repeat_reason"),
                    "options": {}, "topic_choices": list(eligible),
                    "reference_choices": []}
            reason = workbench.REQUIRED_BLOCKS.get(entry["block"])
            item["required"] = reason is not None
            item["required_reason"] = reason
            editable = []
            if "style" in SITE_OPTIONS.get(entry["block"], {}):
                item["style"] = presentation.get("style") or "standard"
                item["options"]["style"] = item["style"]
                editable.append("style")
            if entry["block"] == "series-collection":
                item["options"]["layout"] = presentation.get("layout") or "panels"
                editable.append("layout")
            if entry["block"] in workbench.SELECTABLE_BLOCKS:
                topics = pending.get("topics")
                selected = list(eligible) if topics == "eligible" else list(topics or [])
                default_topic = presentation.get("default_topic")
                item.update({"selected_topics": selected,
                             "default_topic": default_topic or (selected[0] if selected else None),
                             "topic_choices": list(eligible)})
                item["options"].update({"topics": selected,
                                        "default_topic": item["default_topic"]})
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
                "topic_labels": library.topic_labels(eligible, bundle),
                "source_recipe_sha256": workbench.file_digest(recipe_path),
                "default_recipe_sha256": hashlib.sha256(
                    workbench.recipe_bytes(maintained)).hexdigest(),
                "renderable_sha256": hashlib.sha256(
                    workbench.recipe_bytes(renderable)).hexdigest(),
                "pending_sha256": hashlib.sha256(workbench.recipe_bytes(pending)).hexdigest(),
                "excluded": excluded,
                "reuse": self.reuse_candidate(preset),
                "blocks": self._annotate_sections(
                    self._block_document(draft.recipe if draft else maintained,
                                         excluded, eligible, pending_by_id),
                    draft.recipe if draft else maintained,
                    library.bundle_context(bundle),
                    selection={instance: {"topics": (chosen or {}).get("topics")}
                               for instance, chosen in (draft.selection.items()
                                                        if draft is not None else [])}),
                "required_blocks": dict(workbench.REQUIRED_BLOCKS)}

    def _plan_edit(self, draft, action, instance, value):
        """Map a website action onto the workspace service and validate it; writes nothing."""
        if action in ("move-up", "move-down", "include", "exclude"):
            return workbench.edit_plan(draft, action, instance)
        if action == "set-title":
            return workbench.plan_title(draft, instance, value)
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

    # ------------------------------------------------------------------ section identification
    def _section_summary(self, entry, context):
        """Factual summary of a section's effective content, from the recipe entry and bundle."""
        block = entry["block"]
        window = context.get("years_window") or []
        span = f"{window[0]}–{window[-1]}" if len(window) >= 2 else None
        labels = context.get("topic_labels") or {}
        if block == "series-collection":
            topics = entry.get("topics")
            resolved = (list(context["included_topics"]) if topics == "eligible"
                        else list(topics or []))
            presentation = entry.get("presentation") or {}
            layout = presentation.get("layout") or "panels"
            years = entry.get("years") or window
            names = [labels.get(topic, topic) for topic in resolved]
            parts = [library.summary_topics(names) if names else "no diseases selected",
                     "combined chart" if layout == "combined" else "separate charts",
                     (f"{years[0]}–{years[-1]}" if len(years) >= 2 else None),
                     entry.get("measure")]
            return " · ".join(part for part in parts if part)
        if block == "series-trend":
            years = entry.get("years") or window
            parts = [labels.get(entry.get("topic"), entry.get("topic")),
                     (f"{years[0]}–{years[-1]}" if len(years) >= 2 else None),
                     entry.get("measure")]
            return " · ".join(part for part in parts if part)
        if block == "reference-comparison":
            latest = window[-1] if window else None
            return (f"{latest} reporting year vs {context.get('reference_year')} reference year "
                    "· saved percent change")
        if block == "monitoring-overview":
            count = len(context.get("included_topics") or [])
            return (f"Latest saved observation per disease · window {span} · {count} diseases")
        if block == "coverage-selection":
            datasets = context.get("datasets") or {}
            return (f"{datasets.get('included')} datasets included, "
                    f"{datasets.get('excluded')} excluded · "
                    f"{len(context.get('included_topics') or [])} topics")
        if block == "sensitivity-comparison":
            return "Saved main and sensitivity specifications"
        return None

    @staticmethod
    def _copy_labels(blocks):
        """Editor-only 'Copy N' ordinal per block type, ordered by instance id (not by position)."""
        counts = {}
        labels = {}
        for entry in sorted(blocks, key=lambda item: (item["block"], item["instance_id"])):
            counts[entry["block"]] = counts.get(entry["block"], 0) + 1
            labels[entry["instance_id"]] = counts[entry["block"]]
        return labels

    def _annotate_sections(self, blocks, recipe, context, selection=None):
        """Titles, summaries and editor-only copy labels for the saved sections.

        A summary describes the composition the editor would generate: the saved entry with the
        pending (validated) disease choice applied, never the free-text title and never a raw form
        value that has not been accepted.
        """
        titles = recipe.get("titles") or {}
        copies = self._copy_labels(recipe["blocks"])
        selection = selection or {}
        for item in blocks:
            instance = item["instance_id"]
            title = titles.get(instance)
            item["title"] = title
            entry = dict(next(entry for entry in recipe["blocks"]
                              if entry["instance_id"] == instance))
            chosen = (selection.get(instance) or {}).get("topics")
            if chosen is not None:
                entry["topics"] = list(chosen)
            item["summary"] = self._section_summary(entry, context)
            ordinal = copies.get(instance, 1)
            item["copy_label"] = f"Copy {ordinal}" if ordinal > 1 else None
        return blocks

    # ------------------------------------------------------------------ custom mode
    def _custom_draft_contexts(self):
        """Contexts that already own a Custom draft, in the fixed audience order."""
        parent = self.drafts_root / CUSTOM
        if not parent.is_dir():
            return []
        return [audience for audience, _label in AUDIENCES
                if (parent / audience / workbench.DRAFT_EDITOR).is_file()]

    def resolve_custom_context(self, requested=None, selected=None):
        """Which saved data context a Custom report is bound to.

        The context selector is gone from the editor, so the binding must be deterministic:
        an explicit request wins; otherwise an existing draft keeps its own context (preferring
        the audience the reader is on when several drafts exist); with no draft at all the
        currently selected audience is used. Opening the editor never writes anything.
        """
        if requested:
            return self._custom_context(requested)
        drafts = self._custom_draft_contexts()
        if drafts:
            return self._custom_context(selected if selected in drafts else drafts[0])
        if selected:
            return self._custom_context(selected)
        for audience, _label in AUDIENCES:
            try:
                return self._custom_context(audience)
            except SiteError:
                continue
        raise SiteError(HTTPStatus.NOT_FOUND,
                        "No saved data context is installed, so nothing can be composed.",
                        code="no_context")

    def _custom_context(self, context):
        """A Custom report names exactly one saved data context, never a new stakeholder."""
        if context not in dict(AUDIENCES):
            raise SiteError(HTTPStatus.BAD_REQUEST,
                            "Choose a saved data context for this custom report.",
                            code="context_required")
        self.preset(context)                    # the bundle must exist and identify itself
        return context

    def _custom_root(self, context):
        parent = Path(os.path.realpath(self.drafts_root / CUSTOM))
        target = Path(os.path.realpath(parent / context))
        if target != parent and parent not in target.parents:
            raise SiteError(HTTPStatus.BAD_REQUEST, "Custom draft escapes the work root.")
        return target

    def custom_draft(self, context):
        """The saved Custom draft for this context, or None. Read-only."""
        root = self._custom_root(context)
        if not (root / workbench.DRAFT_EDITOR).is_file():
            return None
        try:
            draft = workbench.open_draft(root)
        except workbench.WorkspaceError as error:
            raise SiteError(HTTPStatus.CONFLICT, str(error), code="draft_invalid") from None
        if draft.origin != workbench.CUSTOM_ORIGIN:
            raise SiteError(HTTPStatus.CONFLICT,
                            "This saved copy is an audience draft, not a custom composition.",
                            code="draft_invalid")
        return draft

    def _create_custom(self, context):
        try:
            return workbench.create_custom_draft(self._custom_root(context), context)
        except workbench.WorkspaceError as error:
            raise SiteError(HTTPStatus.CONFLICT, str(error), code="draft_refused") from None

    def _probe_custom(self, context):
        """A transient draft over the initial composition: validation without any write."""
        recipe = library.initial_recipe(context)
        return workbench.Draft(root=self._custom_root(context), recipe=recipe,
                               editor={"schema": workbench.CUSTOM_DRAFT_SCHEMA,
                                       "audience": context,
                                       "origin": workbench.CUSTOM_ORIGIN,
                                       "excluded": [], "selection": {}, "pending": [],
                                       "next_seq": library.last_seq(recipe), "retired": [],
                                       "revision": 0})

    def capabilities(self, context):
        """What the selected saved bundle can actually build, from real builder probes."""
        bundle = self._bundle_path(context)
        try:
            return library.inspect(bundle, self.data_root)
        except (library.LibraryError, OSError, ValueError) as error:
            raise SiteError(HTTPStatus.CONFLICT,
                            f"This data context cannot be inspected: {error}",
                            code="context_unavailable") from None

    def _check_available(self, capabilities, block):
        info = (capabilities.get("blocks") or {}).get(block)
        if info is None:
            raise SiteError(HTTPStatus.BAD_REQUEST, f"Unknown block type: {block!r}")
        if not info["available"]:
            spec = library.LIBRARY.get(block) or {}
            raise SiteError(HTTPStatus.CONFLICT,
                            f"{spec.get('label', block)} cannot be built from this data "
                            f"context. {info['reason']}", code="block_unavailable")

    def _check_domain(self, capabilities, block, options):
        """Refuse a saved-result binding the selected context does not actually contain."""
        if not isinstance(options, dict):
            raise SiteError(HTTPStatus.BAD_REQUEST, "Section options must be an object.")
        if block == "reference-comparison":
            topic = options.get("topic")
            if topic and capabilities["reference_topics"] \
                    and topic not in capabilities["reference_topics"]:
                raise SiteError(HTTPStatus.CONFLICT,
                                f"The saved data context records no reference change for "
                                f"{topic!r}.", code="saved_result_unavailable")
        if block in ("series-trend", "series-collection"):
            available = capabilities.get("topics_by_measure") or {}
            measure = options.get("measure")
            if measure and available and measure not in available:
                raise SiteError(HTTPStatus.CONFLICT,
                                f"The saved data context has no annual series with measure "
                                f"{measure!r}.", code="saved_result_unavailable")
            fallback = capabilities["measures"][0] if capabilities.get("measures") else ""
            topics = available.get(measure or fallback, [])
            if block == "series-trend":
                topic = options.get("topic")
                if topic and topics and topic not in topics:
                    raise SiteError(HTTPStatus.CONFLICT,
                                    f"The saved data context has no annual series for "
                                    f"{topic!r}.", code="saved_result_unavailable")
            if block == "series-collection" and isinstance(options.get("topics"), list):
                missing = [topic for topic in options["topics"] if topic not in topics]
                if missing:
                    raise SiteError(HTTPStatus.CONFLICT,
                                    "Not in this saved data context: " + ", ".join(missing),
                                    code="saved_result_unavailable")
        years = options.get("years")
        window = capabilities.get("years_window") or []
        if years and len(window) >= 2 and not (window[0] <= years[0] and years[1] <= window[-1]):
            raise SiteError(HTTPStatus.BAD_REQUEST,
                            f"Choose years inside the saved reporting window "
                            f"{window[0]}–{window[-1]}.", code="invalid_years")

    def _custom_blocks(self, recipe, excluded, selection, eligible, capabilities=None):
        excluded = set(excluded)
        document = []
        for entry in recipe["blocks"]:
            block = entry["block"]
            spec = library.LIBRARY[block]
            pending = selection.get(entry["instance_id"]) or {}
            presentation = entry.get("presentation") or {}
            item = {"instance_id": entry["instance_id"], "block": block,
                    "label": spec["label"], "description": spec["description"],
                    "included": entry["instance_id"] not in excluded,
                    "required": block in workbench.REQUIRED_BLOCKS,
                    "required_reason": workbench.REQUIRED_BLOCKS.get(block),
                    "repeatable": spec["repeatable"],
                    "repeat_reason": spec["repeat_reason"],
                    "editable": [], "options": {},
                    "topic_choices": list(eligible), "reference_choices": [],
                    "measures": [], "years_window": []}
            if "presentation.style" in spec["options"]:
                item["options"]["style"] = presentation.get("style") or "standard"
                item["editable"].append("style")
            for name in ("topic", "measure", "years"):
                if name in spec["options"]:
                    item["options"][name] = entry.get(name)
                    item["editable"].append(name)
            series_topics = ((capabilities or {}).get("topics_by_measure") or {}).get(
                entry.get("measure")) or list(eligible)
            if block in ("series-trend", "series-collection"):
                item["topic_choices"] = list(series_topics)
                item["measures"] = [measure for measure in
                                    ((capabilities or {}).get("measures") or [])
                                    if ((capabilities or {}).get("topics_by_measure") or {})
                                    .get(measure)]
                item["years_window"] = (capabilities or {}).get("years_window") or []
            if block == "reference-comparison":
                item["reference_choices"] = list(
                    (capabilities or {}).get("reference_topics") or [])
            if block == "series-collection":
                item["options"]["layout"] = presentation.get("layout") or "panels"
                item["editable"].insert(0, "layout")
                chosen = pending.get("topics")
                if chosen is None:
                    chosen = entry.get("topics")
                chosen = list(eligible) if chosen in (None, "eligible") else list(chosen)
                default_topic = pending.get("default_topic") or presentation.get("default_topic")
                item["options"]["topics"] = chosen
                item["options"]["default_topic"] = default_topic or (chosen[0] if chosen else None)
                item["editable"].extend(["topics", "default_topic"])
            document.append(item)
        return document

    def _custom_contexts(self):
        contexts = []
        for audience, label in AUDIENCES:
            entry = {"id": audience, "label": label, "available": False, "reason": None,
                     "source": None, "draft": False, "block_count": 0, "draft_error": None}
            try:
                _recipe_path, bundle = self.preset(audience)
                entry.update({"available": True, "source": self._bundle_source(bundle)})
            except SiteError as error:
                entry["reason"] = error.message
                contexts.append(entry)
                continue
            try:
                draft = self.custom_draft(audience)
            except SiteError as error:
                entry["draft_error"] = error.message
                contexts.append(entry)
                continue
            entry["draft"] = draft is not None
            entry["block_count"] = (len(draft.included()) if draft is not None
                                    else len(library.initial_recipe(audience)["blocks"]))
            contexts.append(entry)
        return contexts

    def _custom_differs(self, context, recipe, eligible):
        """True when the composition differs in content from that context's maintained preset."""
        maintained = workbench.open_recipe(self._recipe_path(context))

        def content(composition):
            items = []
            for entry in composition["blocks"]:
                item = self._block_key(entry, eligible)
                item.pop("instance_id", None)
                items.append(item)
            return items

        return content(recipe) != content(maintained)

    def reuse_candidate_custom(self, context, recipe, bundle, eligible):
        """Newest eligible successful job whose inputs equal this custom composition."""
        key = self.reuse_key(self.reuse_components(recipe, bundle, eligible))
        found = self._best_reuse(key)
        return self._reuse_payload(found) if found else None

    def custom_document(self, context=None, selected=None):
        context = self.resolve_custom_context(context, selected)
        recipe_path, bundle = self.preset(context)
        eligible = list(self.topics(context))
        capabilities = self.capabilities(context)
        draft = self.custom_draft(context)
        if draft is None:
            recipe = library.initial_recipe(context)
            excluded, selection, revision = [], {}, 0
            pending_entries, problem = [], None
            renderable = recipe
        else:
            recipe = draft.recipe
            excluded, selection, revision = list(draft.excluded), draft.selection, draft.revision
            pending_entries = [dict(item) for item in draft.pending_additions]
            problem = draft.pending_problem()
            renderable = draft.effective()
        pending = []
        for item in pending_entries:
            entry = item["entry"]
            block = entry["block"]
            spec = library.LIBRARY[block]
            reason = library.entry_problem(entry)
            conflict = library.combination_conflict(recipe["blocks"], block)
            if reason is None and conflict is not None:
                reason = conflict["reason"]
            pending.append({"instance_id": item["instance_id"], "block": block,
                            "label": spec["label"], "description": spec["description"],
                            "options": {key: value for key, value in entry.items()
                                        if key not in ("block", "instance_id")},
                            "problem": reason or "This section is not part of the saved "
                                                 "composition yet.",
                            "replace": (conflict or {}).get("instances") or []})
        blocks = self._annotate_sections(
            self._custom_blocks(recipe, excluded, selection, eligible, capabilities),
            recipe, library.bundle_context(bundle), selection)
        removed = [{"instance_id": item["instance_id"], "block": item["block"],
                    "label": item["label"]} for item in blocks if not item["included"]]
        # Reuse and the default comparison follow the composition that would actually render
        # (exclusions and the pending disease choice applied), never the saved file alone.
        current = draft.pending() if draft is not None else recipe
        blocking = None
        if problem is not None:
            blocking = (COLLECTION_EMPTY_MESSAGE if problem["kind"] == "empty-selection"
                        else problem["message"])
        library_entries = []
        for spec in library.inventory():
            info = (capabilities.get("blocks") or {}).get(spec["block"]) or {}
            library_entries.append({**spec,
                                    "available": bool(info.get("available")),
                                    "reason": info.get("reason")})
        return {"mode": "custom", "context": context, "label": "Custom report",
                "audience": recipe["audience"],
                "contexts": self._custom_contexts(),
                "draft": draft is not None, "revision": revision,
                "source": self._bundle_source(bundle),
                "library": library_entries,
                "blocks": blocks, "removed": removed, "pending": pending,
                "required_blocks": dict(workbench.REQUIRED_BLOCKS),
                "ready": problem is None, "blocking_reason": blocking,
                "details": (None if problem is None else problem),
                "recipe_sha256": hashlib.sha256(workbench.recipe_bytes(recipe)).hexdigest(),
                "renderable_sha256": hashlib.sha256(
                    workbench.recipe_bytes(renderable)).hexdigest(),
                "pending_sha256": hashlib.sha256(
                    workbench.pending_bytes(draft)).hexdigest() if draft is not None else
                    hashlib.sha256(workbench.recipe_bytes(recipe)).hexdigest(),
                "initial_sha256": hashlib.sha256(
                    workbench.recipe_bytes(library.initial_recipe(context))).hexdigest(),
                "different_from_preset": self._custom_differs(context, current, eligible),
                "reuse": self.reuse_candidate_custom(context, current, bundle, eligible),
                "excluded": excluded,
                "needs_repair": draft.orphans() if draft is not None else [],
                "topic_labels": library.topic_labels(eligible, bundle),
                "eligible_topics": eligible,
                "measures": capabilities["measures"],
                "topics_by_measure": capabilities["topics_by_measure"],
                "reference_topics": capabilities["reference_topics"],
                "years_window": capabilities["years_window"],
                "missing_artifacts": capabilities["missing_artifacts"]}

    def custom_edit(self, context, action, instance, value):
        """Apply one Custom editor action and return the rebuilt document."""
        context = self._custom_context(context)
        if action not in CUSTOM_ACTIONS:
            raise SiteError(HTTPStatus.BAD_REQUEST, f"Unknown custom action {action!r}.")
        eligible = list(self.topics(context))
        capabilities = self.capabilities(context)
        draft = self.custom_draft(context)
        note = None
        try:
            if action == "add-block":
                payload = value if isinstance(value, dict) else {}
                block = payload.get("block")
                options = payload.get("options") or {}
                replace = payload.get("replace") or None
                if isinstance(replace, list):
                    if len(replace) != 1:
                        raise SiteError(HTTPStatus.BAD_REQUEST,
                                        "Confirm exactly one section to replace.")
                    replace = replace[0]
                if replace is not None and not isinstance(replace, str):
                    raise SiteError(HTTPStatus.BAD_REQUEST, "Invalid replacement section.")
                if not isinstance(block, str):
                    raise SiteError(HTTPStatus.BAD_REQUEST, "Choose a section to add.")
                self._check_available(capabilities, block)
                self._check_domain(capabilities, block, options)
                if draft is None:
                    # Validate first, so a refused addition never leaves a draft behind.
                    workbench.plan_add(self._probe_custom(context), block, options, replace)
                    draft = self._create_custom(context)
                draft = workbench.commit_addition(
                    draft, workbench.plan_add(draft, block, options, replace))
            elif action == "duplicate":
                draft = self._require_draft(draft)
                draft = workbench.commit_addition(
                    draft, workbench.plan_duplicate(draft, instance))
            elif action == "repair-draft":
                draft = self._require_draft(draft)
                draft = workbench.repair_custom_draft(draft)
            elif action == "delete-instance":
                draft = self._require_draft(draft)
                draft = workbench.commit_deletion(
                    draft, workbench.plan_delete_instance(draft, instance))
            elif action == "replace-pending":
                draft = self._require_draft(draft)
                payload = value if isinstance(value, dict) else {}
                draft = workbench.commit_addition(draft, workbench.plan_replace(
                    draft, payload.get("pending") or instance, payload.get("existing") or ""))
            elif action == "discard-pending":
                draft = self._require_draft(draft)
                draft = workbench.commit_addition(
                    draft, workbench.discard_pending(draft, instance))
            elif action in ("remove", "restore", "move-up", "move-down"):
                draft = self._require_draft(draft)
                plan_action = {"remove": "exclude", "restore": "include"}.get(action, action)
                recipe, excluded = workbench.edit_plan(draft, plan_action, instance)
                draft = workbench.commit_edit(draft, recipe, excluded)
            elif action == "set-title":
                draft = self._require_draft(draft)
                recipe, excluded = workbench.plan_title(draft, instance, value)
                draft = workbench.commit_edit(draft, recipe, excluded)
            elif action == "set-option":
                draft = self._require_draft(draft)
                payload = value if isinstance(value, dict) else {}
                option, option_value = payload.get("option"), payload.get("value")
                entry = next((item for item in draft.recipe["blocks"]
                              if item["instance_id"] == instance), None)
                if entry is None:
                    raise SiteError(HTTPStatus.BAD_REQUEST, f"Unknown section {instance!r}.")
                self._check_domain(capabilities, entry["block"], {str(option): option_value})
                recipe, excluded = workbench.edit_plan(draft, "set-option", instance,
                                                       option_value, option=option)
                draft = workbench.commit_edit(draft, recipe, excluded)
            else:                                    # set-topics / set-default-open
                if draft is None:
                    workbench.plan_selection(self._probe_custom(context), action, instance,
                                             value, eligible)
                    draft = self._create_custom(context)
                selection, note = workbench.plan_selection(draft, action, instance, value,
                                                           eligible)
                draft = workbench.commit_selection(draft, selection)
        except workbench.LibraryConflict as conflict:
            raise SiteError(HTTPStatus.CONFLICT, str(conflict),
                            code="combination_conflict") from None
        except workbench.WorkspaceError as error:
            raise SiteError(HTTPStatus.BAD_REQUEST, str(error), code="edit_rejected") from None
        document = self.custom_document(context)
        if note:
            document["notes"] = [note]
        return document

    def _require_draft(self, draft):
        """Return the draft, or refuse: this action needs a saved custom composition."""
        if draft is None:
            raise SiteError(HTTPStatus.CONFLICT,
                            "This data context has no custom composition yet.",
                            code="no_draft")
        return draft

    def custom_reset(self, context):
        """Reset only this context's custom composition; audience drafts and reports are kept."""
        context = self._custom_context(context)
        draft = self.custom_draft(context)
        self._require_draft(draft)
        try:
            workbench.reset_custom(draft, context)
        except workbench.WorkspaceError as error:
            raise SiteError(HTTPStatus.CONFLICT, str(error), code="reset_refused") from None
        return self.custom_document(context)

    # ---------------------------------------------------------- neutral CSV mode
    def _csv_root(self):
        root = self.work_root / "csv-datasets"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _csv_dataset_dir(self, digest):
        target = Path(os.path.realpath(self._csv_root() / digest))
        if self._csv_root() not in target.parents:
            raise SiteError(HTTPStatus.BAD_REQUEST, "Unsafe dataset path.", code="unsafe")
        return target

    def csv_datasets(self):
        """Immutable captured datasets, newest capture first, with confirmation state."""
        items = []
        for directory in self._csv_root().glob("*"):
            dataset_file = directory / "dataset.json"
            if not dataset_file.is_file():
                continue
            dataset = _read_json(dataset_file)
            items.append({
                "digest": directory.name,
                "source_filename": dataset.get("source_filename"),
                "captured_at_utc": dataset.get("captured_at_utc"),
                "confirmed": (directory / "interpretation.json").is_file(),
                # dataset.json records row_count; the API contract calls it record_count. Both
                # spellings are accepted so an older dataset file still lists its count.
                "record_count": dataset.get("record_count", dataset.get("row_count")),
            })
        # Directory names are content digests, so ordering them is not chronological.
        items.sort(key=lambda item: (item.get("captured_at_utc") or "", item["digest"]),
                   reverse=True)
        return items

    def csv_capture(self, payload: bytes, source_filename: str):
        """Bound and inspect one upload; promote to immutable storage on success.

        Unsuccessful captures never become accepted datasets; a later identical upload is a
        new capture event, and changed bytes always create a new content version.
        """
        try:
            capture = neutral.capture_payload(payload, source_filename=source_filename)
        except neutral.NeutralError as error:
            raise SiteError(HTTPStatus.BAD_REQUEST, str(error), code="csv_rejected") from None
        directory = self._csv_dataset_dir(capture.input_sha256)
        dataset_file = directory / "dataset.json"
        if not dataset_file.is_file():
            directory.mkdir(parents=True, exist_ok=False)
            try:
                _write_json_atomic(dataset_file, {
                    "schema": neutral.NEUTRAL_INTERPRETATION_SCHEMA.replace(
                        "neutral-interpretation", "neutral-dataset"),
                    "source_filename": capture.source_filename,
                    "input_sha256": capture.input_sha256,
                    "byte_count": capture.byte_count,
                    "captured_at_utc": _now(),
                    "columns": list(capture.columns),
                    "row_count": capture.logical_records,
                    "limits_family": "csv-slice-b",
                })
                (directory / "original.bin").write_bytes(payload)
            except OSError:
                raise SiteError(HTTPStatus.INTERNAL_SERVER_ERROR,
                                "The capture could not be stored.", code="capture_failed")
        return capture

    def csv_confirmation(self, digest):
        """The dataset passport, section interpretation suggestion and current draft."""
        directory = self._csv_dataset_dir(digest)
        dataset_file = directory / "dataset.json"
        if not dataset_file.is_file():
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown dataset.", code="no_dataset")
        dataset = _read_json(dataset_file)
        payload = (directory / "original.bin").read_bytes()
        capture = neutral.capture_payload(payload, source_filename=dataset["source_filename"])
        suggestion = neutral.suggest_interpretation(capture)
        confirmation = None
        if (directory / "interpretation.json").is_file():
            confirmation = _read_json(directory / "interpretation.json")
        return {
            "dataset": {**dataset, "record_count":
                        dataset.get("record_count", dataset.get("row_count"))},
            "preview": capture.as_public(),
            "suggestion": suggestion,
            "confirmation": confirmation,
            "limits": {key: neutral.LIMITS[key]
                       for key in ("max_upload_bytes", "max_records", "max_columns",
                                   "max_cells", "max_field_bytes")},
        }

    def csv_confirm(self, digest, interpretation):
        """Confirm the interpretation; preparation and description happen once and stay
        immutable. A failed confirmation blocks and changes nothing."""
        directory = self._csv_dataset_dir(digest)
        dataset_file = directory / "dataset.json"
        if not dataset_file.is_file():
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown dataset.", code="no_dataset")
        dataset = _read_json(dataset_file)
        try:
            confirmed = neutral.validate_interpretation(interpretation)
            payload = (directory / "original.bin").read_bytes()
            capture = neutral.capture_payload(payload,
                                              source_filename=dataset["source_filename"])
            prepared = neutral.prepare_payload_under(capture, payload, confirmed)
            analysis = neutral.describe(
                prepared["rows"], confirmed,
                dataset={"source_filename": dataset["source_filename"],
                         "input_sha256": capture.input_sha256})
            issues = neutral.verify_repeatable(prepared, analysis)
            if issues:
                raise SiteError(HTTPStatus.INTERNAL_SERVER_ERROR,
                                "The analysis could not be verified: " + "; ".join(issues),
                                code="csv_verify")
        except neutral.NeutralError as error:
            raise SiteError(HTTPStatus.BAD_REQUEST, str(error), code="csv_conflict") from None
        try:
            _write_json_atomic(directory / "interpretation.json", confirmed)
            _write_json_atomic(directory / "prepared.json", prepared)
            _write_json_atomic(directory / "neutral-analysis.json", analysis)
        except OSError:
            raise SiteError(HTTPStatus.INTERNAL_SERVER_ERROR,
                            "The confirmation could not be stored.", code="capture_failed")
        analysis_public = dict(analysis)
        analysis_public.pop("interpretation", None)
        return {"digest": digest, "confirmed": confirmed, "analysis": analysis_public}

    def csv_bundle_path(self, digest):
        directory = self._csv_dataset_dir(digest)
        if not (directory / "neutral-analysis.json").is_file():
            raise SiteError(HTTPStatus.CONFLICT,
                            "Confirm the interpretation before generating the report.",
                            code="csv_not_confirmed")
        _analysis, _prepared, stale = self._csv_analysis_state(digest)
        if stale:
            # Numbers computed under older definitions are never relabelled as current.
            raise SiteError(HTTPStatus.CONFLICT, stale, code="csv_analysis_stale")
        return directory

    def _csv_analysis_state(self, digest):
        """(analysis, prepared, stale_reason) for a confirmed dataset.

        The compatibility verdict is cached under a CONTENT key: sha256 over the captured
        dataset record, the confirmed interpretation, the prepared rows, the saved analysis and
        the calculation version. A timestamp is not an identity — rewriting a file and restoring
        its mtime still produces a different key, so the result is re-verified.
        """
        directory = self._csv_dataset_dir(digest)
        paths = {"dataset": directory / "dataset.json",
                 "interpretation": directory / "interpretation.json",
                 "prepared": directory / "prepared.json",
                 "analysis": directory / "neutral-analysis.json"}
        if not (paths["analysis"].is_file() and paths["prepared"].is_file()):
            return None, None, "The dataset has not been confirmed yet."
        payloads = {}
        signature = hashlib.sha256()
        signature.update(b"calc=" + str(neutral.CALC_VERSION).encode() + b"\0")
        for name in sorted(paths):
            path = paths[name]
            if not path.is_file():
                return None, None, "The dataset has not been confirmed yet."
            data = path.read_bytes()
            payloads[name] = data
            signature.update(name.encode() + b"\0")
            signature.update(hashlib.sha256(data).digest())
        key = signature.hexdigest()
        cached = self._analysis_cache.get(digest)
        if cached and cached.get("key") == key:
            return cached["analysis"], cached["prepared"], cached["stale"]
        try:
            analysis = json.loads(payloads["analysis"])
            prepared = json.loads(payloads["prepared"])
            confirmed = json.loads(payloads["interpretation"])
        except (UnicodeDecodeError, ValueError):
            return None, None, ("The saved analysis is not readable. Update the analysis to "
                                "recompute it from the captured records.")
        ok, reason = neutral.analysis_compatible(prepared, analysis, confirmed)
        if ok and (analysis.get("source") or {}).get("input_sha256") != digest:
            ok, reason = False, ("The saved analysis belongs to a different capture. "
                                 "Update the analysis for this dataset.")
        stale = None if ok else reason
        self._analysis_cache[digest] = {"key": key, "analysis": analysis,
                                       "prepared": prepared, "stale": stale}
        return analysis, prepared, stale

    # ------------------------------------------------------------------ neutral reuse identity
    def _csv_environment(self):
        """Renderer identity for neutral packages: content hashes plus the process's toolchain.

        Computed once per process, like the stakeholder identity: it must describe the code that
        is actually running, not whatever happens to be on disk later.
        """
        with self._environment_lock:
            if self._csv_environment_cache is not None:
                return self._csv_environment_cache
            software = {"python": platform.python_version(),
                        "quarto": self._tool_version([self.quarto, "--version"]),
                        "R": self._tool_version(["Rscript", "--version"])}
            workflow = (workbench.file_digest(self.workflow_config)
                        if self.workflow_config and Path(self.workflow_config).is_file()
                        else None)
            self._csv_environment_cache = neutral_identity.environment(
                ROOT, software=software, workflow_config_sha256=workflow)
            return self._csv_environment_cache

    def _csv_identity(self, digest, recipe, analysis):
        """(record, key) for one effective neutral request."""
        directory = self._csv_dataset_dir(digest)
        dataset = _read_json(directory / "dataset.json")
        interpretation = _read_json(directory / "interpretation.json")
        record = neutral_identity.request_identity(
            recipe=recipe, analysis=analysis, interpretation=interpretation,
            dataset=dataset, environment_record=self._csv_environment())
        return record, neutral_identity.reuse_key(record)

    def _csv_current_identity(self, digest):
        """(record, key) for the saved draft, or (None, None) when it is not ready."""
        try:
            analysis, _prepared, stale = self._csv_analysis_state(digest)
        except SiteError:
            return None, None
        if analysis is None or stale:
            return None, None
        recipe = self.csv_recipe_for(digest)
        if self._draft_reuse_problem(recipe, analysis) is not None:
            return None, None
        try:
            return self._csv_identity(digest, recipe, analysis)
        except (SiteError, OSError, ValueError):
            return None, None

    @staticmethod
    def _draft_reuse_problem(recipe, analysis):
        """Why the saved draft cannot be advertised as reusable, if it cannot."""
        try:
            neutral_lib.validate_recipe(recipe)
        except neutral_lib.NeutralLibraryError as error:
            return str(error)
        conflicts = neutral_lib.disclosure_conflicts(recipe)
        if conflicts:
            return " ".join(item["message"] for item in conflicts)
        for entry in recipe.get("blocks") or []:
            if "display" in entry:
                problem = neutral_display.selection_problem(
                    neutral_display.resolve(entry["block"], entry["display"]), analysis)
                if problem:
                    return problem
        return None

    def _neutral_reuse_candidate(self, digest, identity, key):
        """The newest successful job whose recorded identity matches, after validation."""
        candidates = []
        for directory in self.jobs_root.glob("*"):
            record_file = directory / "job.json"
            if not record_file.is_file():
                continue
            try:
                record = _read_json(record_file)
            except (OSError, ValueError):
                continue
            if (record.get("mode") != "csv" or record.get("context") != digest
                    or record.get("status") != "succeeded"
                    or record.get("reuse_key") != key):
                continue
            candidates.append(record)
        candidates.sort(key=lambda item: (item.get("created_utc") or "", item.get("job_id") or ""),
                        reverse=True)
        reasons = []
        for record in candidates:
            ok, reason = self._neutral_reuse_eligible(record, digest, identity, key)
            if ok:
                return record, reasons
            reasons.append({"job_id": record.get("job_id"), "reason": reason})
        return None, reasons

    def _neutral_reuse_eligible(self, record, digest, identity, key):
        """A matching key is a candidate, not a hit: verify the recorded artifacts too."""
        if not record.get("package_sha256") or not record.get("preview_dir"):
            return False, "the recorded package digest is missing"
        snapshot_relative = record.get("snapshot")
        if not snapshot_relative:
            return False, "the frozen request is missing"
        snapshot = Path(os.path.realpath(self.work_root / snapshot_relative))
        if self.work_root not in snapshot.parents or not snapshot.is_file():
            return False, "the frozen request is missing"
        if workbench.file_digest(snapshot) != record.get("recipe_sha256"):
            return False, "the frozen request does not match its recorded digest"
        try:
            recorded_recipe = json.loads(snapshot.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False, "the frozen request is not readable"
        if neutral_identity.normalised_recipe(recorded_recipe) != identity["composition"]:
            return False, "the frozen request differs from this identity"
        package = Path(os.path.realpath(self.work_root / record["preview_dir"]))
        if self.work_root not in package.parents or not package.is_dir():
            return False, "the published package is missing"
        if not (package / "report.html").is_file():
            return False, "the report file is missing"
        package_digest, package_files = self._package_digest(package)
        if package_digest is None:
            return False, "the package contains a symlink"
        if package_digest != record["package_sha256"]:
            return False, "the published files have changed"
        provenance, status = self._package_json(package, "provenance.json")
        if status != "recorded":
            return False, "the package has no readable provenance"
        if (provenance.get("dataset") or {}).get("input_sha256") != digest:
            return False, "the package belongs to a different capture"
        recorded_analysis = self._recorded_analysis_digest(provenance)
        if recorded_analysis != identity["analysis"]["digest"]:
            return False, "the package used a different analysis"
        recorded_disclosure = provenance.get("disclosure") or {}
        if (recorded_disclosure.get("policy") != identity["disclosure"]["policy"]
                or bool(recorded_disclosure.get("permit_values")) != identity["disclosure"]["permit_values"]
                or bool(recorded_disclosure.get("permit_records")) != identity["disclosure"]["permit_records"]):
            return False, "the package was published under a different disclosure policy"
        return True, None

    def csv_history(self, digest):
        """Bounded, dataset-scoped history of retained neutral reports."""
        try:
            _analysis, _prepared, _stale = self._csv_analysis_state(digest)
        except SiteError:
            _analysis = None
        _identity, current_key = self._csv_current_identity(digest)
        directory_name = (self._csv_dataset_dir(digest) / "dataset.json")
        filename = _read_json(directory_name).get("source_filename") if directory_name.is_file() else None
        records = []
        for directory in self.jobs_root.glob("*"):
            record_file = directory / "job.json"
            if not record_file.is_file():
                continue
            try:
                record = _read_json(record_file)
            except (OSError, ValueError):
                continue
            if record.get("mode") != "csv" or record.get("context") != digest:
                continue
            records.append(record)
        records.sort(key=lambda item: (item.get("created_utc") or "", item.get("job_id") or ""),
                     reverse=True)
        total = len(records)
        items = []
        for record in records[:20]:
            package = self._package_dir(record)
            provenance, _status = self._package_json(package, "provenance.json")
            composition, _cstatus = self._package_json(package, "composition.json")
            disclosure = (provenance or {}).get("disclosure") or {}
            titles = ((composition or {}).get("titles")
                      or ((provenance or {}).get("composition") or {}).get("section_titles") or {})
            blocks = ((composition or {}).get("blocks")
                      or ((provenance or {}).get("composition") or {}).get("effective_recipe") or [])
            reuse = {"state": "unknown", "reason": "Older report: no reuse identity was recorded."}
            if record.get("status") != "succeeded":
                reuse = {"state": "unavailable", "reason": "This report did not complete."}
            elif record.get("reuse_key") and current_key:
                if record["reuse_key"] != current_key:
                    reuse = {"state": "different",
                             "reason": "Different settings, input, analysis or renderer."}
                else:
                    ok, reason = self._neutral_reuse_eligible(
                        record, digest, _identity, current_key)
                    reuse = ({"state": "match", "reason": "Matches the current settings."}
                             if ok else {"state": "unavailable",
                                         "reason": f"Not reusable: {reason}."})
            elif not record.get("reuse_key"):
                reuse = {"state": "unknown",
                         "reason": "Older report: reuse identity was not recorded; it can still be "
                                   "opened."}
            items.append({
                "job_id": record.get("job_id"),
                "created_utc": record.get("created_utc"),
                "finished_utc": record.get("finished_utc"),
                "status": record.get("status"),
                "dataset": {"filename": filename, "digest": digest},
                "titles": list(titles.values())[:4],
                "blocks": [entry.get("block") for entry in blocks][:8],
                "policy": {"policy": disclosure.get("policy"),
                           "label": disclosure.get("label"),
                           "permit_values": disclosure.get("permit_values"),
                           "permit_records": disclosure.get("permit_records")},
                "preview": bool((provenance or {}).get("preview")),
                "reuse": reuse,
                "links": ({"report": f"/reports/{record['job_id']}/report.html"}
                          if record.get("status") == "succeeded" else {}),
            })
        return {"items": items, "total": total, "truncated": total > len(items),
                "limit": 20}

    def csv_document(self, digest=None):
        """The CSV mode document: datasets, selected confirmation and the neutral composition."""
        datasets = self.csv_datasets()
        selected = None
        if digest:
            for item in datasets:
                if item["digest"] == digest:
                    selected = item
                    break
            if selected is None:
                raise SiteError(HTTPStatus.NOT_FOUND, "Unknown dataset.", code="no_dataset")
        payload = {
            "mode": "csv",
            "audience": NEUTRAL_AUDIENCE,
            "datasets": datasets,
            "selected_digest": digest or None,
            "blocks": neutral_lib.inventory(),
            "disclosure_options": [
                {"policy": key, **{field: spec[field] for field in
                                   ("label", "summary", "detail", "permits_values",
                                    "permits_records")}}
                for key, spec in neutral_lib.DISCLOSURE_POLICIES.items()],
        }
        if selected is not None:
            payload["confirmation"] = self.csv_confirmation(digest)
            analysis, _prepared, stale = self._csv_analysis_state(digest)
            if analysis is not None:
                payload["analysis"] = {
                    "row_count": analysis["row_count"],
                    "group_count": analysis["group_count"],
                    "measure": analysis["measure"],
                    "time": analysis["time"],
                    "summary": analysis["summary"],
                    "quality": analysis["quality"],
                    "missing": analysis["missing"],
                    "method": analysis.get("method"),
                }
                # What the display controls may choose from: the analysed selection, never more.
                payload["available"] = {
                    "groups": [label for _key, label in
                               neutral_display.group_labels(analysis)],
                    "periods": [item for item in analysis["time"].get("periods") or []],
                    "statistics": [{"key": key, "label": neutral_display.STATISTIC_LABELS[key]}
                                   for key in neutral_display.STATISTIC_ORDER],
                    "resolution": (analysis["time"].get("column") or None),
                }
                payload["analysis_stale"] = stale
                payload["history"] = self.csv_history(digest)
                recipe = self.csv_recipe_for(digest)
                payload["recipe"] = recipe
                payload["disclosure"] = recipe.get("disclosure")
                payload["disclosure_conflicts"] = neutral_lib.disclosure_conflicts(recipe)
                payload["composer"] = self._csv_composer_blocks(recipe, digest)
        return payload

    def _csv_composer_blocks(self, recipe, digest):
        """Editor rows for the saved CSV composition (same shape the health editor uses)."""
        analysis = _read_json(self._csv_dataset_dir(digest) / "neutral-analysis.json")
        capabilities = {"has_time": bool(analysis["time"]["column"]),
                        "has_group": bool(analysis["interpretation"].get("category"))}
        titles = recipe.get("titles") or {}
        rows = []
        for entry in recipe["blocks"]:
            spec = neutral_lib.NEUTRAL_BLOCKS[entry["block"]]
            label = neutral_lib.NEUTRAL_BLOCKS[entry["block"]]["label"]
            rows.append({
                "instance_id": entry["instance_id"],
                "block": entry["block"],
                "label": label,
                "description": neutral_lib._DESCRIPTIONS[entry["block"]],
                "included": True,
                "required": entry["block"] in neutral_lib.REQUIRED,
                "required_reason": ("Required: every report states its limitations and cautions."
                                    if entry["block"] == "limitations" else None),
                "repeatable": spec["repeatable"],
                "repeat_reason": spec["repeat_reason"],
                "editable": [],
                "options": {},
                "display": neutral_display.resolve(entry["block"], entry.get("display")),
                "display_supported": entry["block"] in neutral_display.CAPABILITIES,
                "display_ui": (self._csv_display_ui(entry["block"], analysis)
                               if entry["block"] in neutral_display.CAPABILITIES else None),
                "display_summary": (neutral_display.summary(
                    neutral_display.resolve(entry["block"], entry.get("display")), analysis)
                    if entry["block"] in neutral_display.CAPABILITIES else None),
                "title": titles.get(entry["instance_id"]),
                "summary": neutral_lib.entry_problem(entry, capabilities),
            })
        return rows

    @staticmethod
    def _csv_display_ui(block, analysis):
        """What the editor may offer for one block, derived from the saved analysis."""
        return {
            "capabilities": sorted(neutral_display.CAPABILITIES.get(block, ())),
            "layouts": list(neutral_display.LAYOUTS_FOR.get(block, ("table",))),
            "statistics": [{"key": key, "label": neutral_display.STATISTIC_LABELS[key]}
                           for key in neutral_display.STATISTIC_ORDER],
            "groups": [label for _key, label in neutral_display.group_labels(analysis)],
            "periods": list(analysis["time"].get("periods") or []),
            "has_time": bool(analysis["time"].get("has_time")),
        }

    def _csv_draft(self, digest):
        """(recipe, excluded) for this dataset's saved draft; the editable starter if none.

        ``excluded`` keeps the settings of removed sections so restoring one brings back its
        title and display choices. The effective composition is ``recipe`` alone.
        """
        draft_path = self.work_root / "drafts" / "csv" / digest / "editor.json"
        try:
            if draft_path.is_file():
                saved = _read_json(draft_path)
                recipe = saved.get("recipe")
                if recipe and neutral_lib.validate_recipe(recipe):
                    excluded = [entry for entry in (saved.get("excluded") or [])
                                if isinstance(entry, dict) and "instance_id" in entry
                                and entry.get("block") in neutral_lib.NEUTRAL_BLOCKS]
                    return recipe, excluded
        except (OSError, ValueError, neutral_lib.NeutralLibraryError):
            pass
        analysis = _read_json(self._csv_dataset_dir(digest) / "neutral-analysis.json")
        return neutral_lib.default_recipe(bool(analysis["time"]["column"])), []

    def csv_recipe_for(self, digest):
        """The saved CSV draft composition for this dataset, or the default starter."""
        return self._csv_draft(digest)[0]

    def csv_draft_edit(self, digest, action, instance, value):
        """Apply one neutral composition edit to the saved CSV draft (creates on demand)."""
        directory = self._csv_dataset_dir(digest)
        if not (directory / "neutral-analysis.json").is_file():
            raise SiteError(HTTPStatus.CONFLICT,
                            "Confirm the interpretation before composing a report.",
                            code="csv_not_confirmed")
        recipe, excluded = self._csv_draft(digest)
        if action == "restore-composition":
            payload = value if isinstance(value, dict) else {}
            unknown = set(payload) - {"job_id", "confirm"}
            if unknown:
                raise SiteError(HTTPStatus.BAD_REQUEST,
                                "Unknown fields: " + ", ".join(sorted(unknown)),
                                code="edit_rejected")
            try:
                recipe = self.csv_restore_composition(
                    digest, str(payload.get("job_id") or ""), bool(payload.get("confirm")))
            except neutral_lib.NeutralLibraryError as error:
                raise SiteError(HTTPStatus.BAD_REQUEST, str(error),
                                code="csv_recipe") from None
            excluded = []
        elif action in ("move-up", "move-down", "include", "exclude", "set-title",
                        "duplicate", "delete-instance", "set-disclosure", "set-display"):
            try:
                if action == "include":
                    restored = next((entry for entry in excluded
                                     if entry["instance_id"] == instance), None)
                    if restored is not None:
                        recipe = dict(recipe)
                        recipe["blocks"] = list(recipe["blocks"]) + [restored]
                        recipe = neutral_lib.validate_recipe(recipe)
                        excluded = [entry for entry in excluded
                                    if entry["instance_id"] != instance]
                    else:
                        recipe = self._csv_apply(digest, recipe, action, instance, value)
                elif action in ("exclude", "delete-instance"):
                    removed = next((entry for entry in recipe["blocks"]
                                    if entry["instance_id"] == instance), None)
                    recipe = self._csv_apply(digest, recipe, action, instance, value)
                    excluded = [entry for entry in excluded
                                if entry["instance_id"] != instance]
                    if action == "exclude" and removed is not None:
                        excluded = excluded + [removed]
                else:
                    recipe = self._csv_apply(digest, recipe, action, instance, value)
            except neutral_lib.NeutralLibraryError as error:
                raise SiteError(HTTPStatus.BAD_REQUEST, str(error),
                                code="csv_recipe") from None
        else:
            raise SiteError(HTTPStatus.BAD_REQUEST, f"Unknown csv edit action {action!r}.",
                            code="edit_rejected")
        draft_dir = self.work_root / "drafts" / "csv" / digest
        draft_dir.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(draft_dir / "editor.json",
                           {"schema": "health-report/csv-draft/1", "digest": digest,
                            "recipe": recipe, "excluded": excluded,
                            "updated_utc": _now()})
        return recipe

    def _csv_apply(self, digest, recipe, action, instance, value):
        blocks = [dict(entry) for entry in recipe["blocks"]]
        if action == "move-up":
            i = next((k for k, e in enumerate(blocks) if e["instance_id"] == instance), None)
            if i is None:
                raise neutral_lib.NeutralLibraryError(f"Unknown section {instance!r}.")
            if i > 0:
                blocks[i], blocks[i - 1] = blocks[i - 1], blocks[i]
        elif action == "move-down":
            i = next((k for k, e in enumerate(blocks) if e["instance_id"] == instance), None)
            if i is None:
                raise neutral_lib.NeutralLibraryError(f"Unknown section {instance!r}.")
            if i < len(blocks) - 1:
                blocks[i], blocks[i + 1] = blocks[i + 1], blocks[i]
        elif action == "exclude":
            blocks = [e for e in blocks if e["instance_id"] != instance]
        elif action == "include":
            block = instance
            if block not in neutral_lib.NEUTRAL_BLOCKS:
                raise neutral_lib.NeutralLibraryError(f"Unknown section type {instance!r}.")
            if any(e["block"] == block and e["instance_id"] == instance
                   for e in blocks):
                return recipe
            entry = {"block": block, "instance_id": instance}
            if block in ("values-over-time", "coverage-over-time"):
                entry["time_period"] = "year"
            blocks.append(entry)
        elif action == "set-title":
            titles = dict(recipe.get("titles") or {})
            if value is None:
                titles.pop(instance, None)
            else:
                value = str(value).strip()
                if not value:
                    titles.pop(instance, None)
                elif len(value) > 80:
                    raise neutral_lib.NeutralLibraryError(
                        "Section titles are limited to 80 characters.")
                else:
                    titles[instance] = value
            recipe["titles"] = titles
            return neutral_lib.validate_recipe(recipe)
        elif action == "duplicate":
            entry = next((e for e in blocks if e["instance_id"] == instance), None)
            if entry is None:
                raise neutral_lib.NeutralLibraryError(f"Unknown section {instance!r}.")
            taken = {e["instance_id"] for e in blocks}
            seq = 0
            for e in blocks:
                m = re.search(r"-(\d{4})$", e["instance_id"])
                if m:
                    seq = max(seq, int(m.group(1)))
            new_id, seq = neutral_lib.allocate(entry["block"], taken, seq)
            dup = dict(entry)
            dup["instance_id"] = new_id
            blocks.append(dup)
        elif action == "delete-instance":
            blocks = [e for e in blocks if e["instance_id"] != instance]
        elif action == "set-display":
            entry = next((e for e in blocks if e["instance_id"] == instance), None)
            if entry is None:
                raise neutral_lib.NeutralLibraryError(f"Unknown section {instance!r}.")
            if entry["block"] not in neutral_display.CAPABILITIES:
                raise neutral_lib.NeutralLibraryError(
                    f"Section {entry['block']!r} has no display settings.")
            try:
                display = neutral_display.resolve(entry["block"], value or {})
            except neutral_display.DisplayError as error:
                raise neutral_lib.NeutralLibraryError(str(error)) from None
            analysis = _read_json(self._csv_dataset_dir(digest) / "neutral-analysis.json")
            problem = neutral_display.selection_problem(display, analysis)
            if problem:
                raise neutral_lib.NeutralLibraryError(problem)
            entry["display"] = display
            recipe["blocks"] = blocks
            return neutral_lib.validate_recipe(recipe)
        elif action == "set-disclosure":
            payload = value if isinstance(value, dict) else {}
            unknown = set(payload) - {"policy", "permit_records"}
            if unknown:
                raise neutral_lib.NeutralLibraryError(
                    "Unknown disclosure fields: " + ", ".join(sorted(unknown)))
            policy = payload.get("policy")
            if policy not in neutral_lib.DISCLOSURE_POLICIES:
                raise neutral_lib.NeutralLibraryError(
                    "Choose one of: " + ", ".join(sorted(neutral_lib.DISCLOSURE_POLICIES))
                    + ".")
            recipe["disclosure"] = neutral_lib.disclosure_record(
                policy, bool(payload.get("permit_records")))
            recipe["blocks"] = blocks
            return neutral_lib.validate_recipe(recipe)
        recipe["blocks"] = blocks
        return neutral_lib.validate_recipe(recipe)

    def csv_restore_composition(self, digest, job_id, confirm=False):
        """Load a retained report's frozen composition into the current draft.

        An explicit action: it never touches the historical package, it refuses to bind a
        composition to a different confirmed interpretation without confirmation, and it refuses
        to overwrite an edited draft without confirmation.
        """
        record = self._job_record(job_id)
        if record.get("mode") != "csv" or record.get("status") != "succeeded":
            raise SiteError(HTTPStatus.CONFLICT,
                            "That report is not a completed CSV report.",
                            code="reuse_unavailable")
        if record.get("context") != digest:
            raise SiteError(HTTPStatus.CONFLICT,
                            "That report belongs to a different captured dataset.",
                            code="dataset_mismatch")
        relative = record.get("snapshot")
        snapshot = Path(os.path.realpath(self.work_root / relative)) if relative else None
        if snapshot is None or self.work_root not in snapshot.parents or not snapshot.is_file():
            raise SiteError(HTTPStatus.CONFLICT,
                            "This report's frozen request is missing.",
                            code="reuse_unavailable")
        try:
            recipe = json.loads(snapshot.read_text(encoding="utf-8"))
            neutral_lib.validate_recipe(recipe)
        except (OSError, ValueError, neutral_lib.NeutralLibraryError) as error:
            raise SiteError(HTTPStatus.CONFLICT,
                            f"This report's frozen request cannot be used: {error}",
                            code="reuse_unavailable") from None
        if recipe.get("audience") != NEUTRAL_AUDIENCE:
            raise SiteError(HTTPStatus.CONFLICT,
                            "This report's frozen request is not a neutral composition.",
                            code="reuse_unavailable")
        analysis, _prepared, stale = self._csv_analysis_state(digest)
        if analysis is None:
            raise SiteError(HTTPStatus.CONFLICT,
                            "Confirm the interpretation before copying a report's settings.",
                            code="csv_not_confirmed")
        if stale:
            raise SiteError(HTTPStatus.CONFLICT, stale, code="csv_analysis_stale")

        package = self._package_dir(record)
        provenance, _status = self._package_json(package, "provenance.json")
        historical = (provenance or {}).get("interpretation") or {}
        current = _read_json(self._csv_dataset_dir(digest) / "interpretation.json")
        roles = ("category", "measure", "time")
        changed = [key for key in roles
                   if (historical.get(key) or None) != (current.get(key) or None)]
        if changed:
            message = (
                "This report was built with a different confirmed interpretation "
                f"(group {historical.get('category')!r}, measure {historical.get('measure')!r}, "
                f"time {historical.get('time')!r}) than the current one "
                f"(group {current.get('category')!r}, measure {current.get('measure')!r}, "
                f"time {current.get('time')!r}). Its composition can still be copied, but the "
                "result would be analysed under the current interpretation. Update the analysis "
                "first if that is not what you intend, or confirm to copy anyway.")
            if not confirm:
                raise SiteError(HTTPStatus.CONFLICT, message, code="context_changed")

        for entry in recipe.get("blocks") or []:
            if "display" in entry:
                problem = neutral_display.selection_problem(
                    neutral_display.resolve(entry["block"], entry["display"]), analysis)
                if problem:
                    raise SiteError(HTTPStatus.CONFLICT, problem, code="display_mismatch")

        draft_path = self.work_root / "drafts" / "csv" / digest / "editor.json"
        if draft_path.is_file() and not confirm:
            try:
                existing = _read_json(draft_path).get("recipe")
            except (OSError, ValueError):
                existing = None
            if existing != recipe:
                raise SiteError(HTTPStatus.CONFLICT,
                                "There is one editable draft per dataset. This action replaces "
                                "the current draft with this report's saved configuration; the "
                                "historical report is not changed. Confirm to replace it.",
                                code="draft_has_edits")
        return recipe

    def csv_submit(self, digest, recipe):
        """Render the confirmed dataset with the supplied neutral composition recipe."""
        bundle = self.csv_bundle_path(digest)
        try:
            recipe = neutral_lib.validate_recipe(recipe)
        except neutral_lib.NeutralLibraryError as error:
            raise SiteError(HTTPStatus.BAD_REQUEST, str(error), code="csv_recipe") from None
        # Disclosure compatibility is decided before any job exists: a recipe whose sections
        # cannot be published under the chosen policy is refused, never downgraded.
        conflicts = neutral_lib.disclosure_conflicts(recipe)
        if conflicts:
            raise SiteError(HTTPStatus.BAD_REQUEST,
                            " ".join(item["message"] for item in conflicts),
                            code="csv_disclosure")
        analysis, _prepared, stale = self._csv_analysis_state(digest)
        if stale:
            raise SiteError(HTTPStatus.CONFLICT, stale, code="csv_analysis_stale")
        capabilities = {"has_time": bool(analysis["time"]["column"]),
                        "has_group": bool(analysis["interpretation"].get("category"))}
        for entry in recipe["blocks"]:
            problem = neutral_lib.entry_problem(entry, capabilities)
            if problem:
                raise SiteError(HTTPStatus.BAD_REQUEST, problem, code="csv_capability")
            if entry["block"] in neutral_display.CAPABILITIES:
                # Resolve the effective settings now and freeze them into the request, so a later
                # change to the code defaults cannot silently reinterpret this saved report.
                display = neutral_display.resolve(entry["block"], entry.get("display"))
                problem = neutral_display.selection_problem(display, analysis)
                if problem:
                    raise SiteError(HTTPStatus.BAD_REQUEST, problem, code="csv_display")
                entry["display"] = display
        identity, key = self._csv_identity(digest, recipe, analysis)
        candidate, skipped = self._neutral_reuse_candidate(digest, identity, key)
        if candidate is not None:
            payload = self.public_job(candidate)
            payload["reused"] = True
            payload["reuse_message"] = (
                "Opened an existing report matching these settings. Originally generated "
                f"{candidate.get('created_utc')}. No new render was performed.")
            payload["reuse_skipped"] = skipped
            return payload
        return self._launch_csv(bundle, recipe, digest, identity=identity, key=key)

    def _launch_csv(self, bundle, recipe, digest, identity=None, key=None):
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
            snapshot = job_directory / "composition.json"
            with open(snapshot, "xb") as handle:
                handle.write(workbench.recipe_bytes(recipe))
                handle.flush()
                os.fsync(handle.fileno())
            recorded = workbench.open_recipe(snapshot)
            if recorded.get("audience") != NEUTRAL_AUDIENCE:
                raise SiteError(HTTPStatus.BAD_REQUEST,
                                "The csv composition binds the wrong audience.",
                                code="csv_recipe")
            package = job_directory / "package"
            job = Job(job_id=job_id, preset="csv", mode="csv",
                      recipe_sha256=workbench.file_digest(snapshot),
                      classification="custom", classification_basis=None,
                      context=digest, origin="csv",
                      reuse_key=key, reuse_components=identity or {},
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
        return self._launch(preset=preset, recipe=recipe, bundle=bundle, eligible=eligible,
                            audience=audience, mode=mode, classification=classification,
                            classification_basis=classification_basis, origin="preset",
                            context=None)

    def _launch(self, *, preset, recipe, bundle, eligible, audience, mode, classification,
                classification_basis, origin, context):
        """Reserve the single render slot, freeze the recipe bytes and start the worker.

        The caller has already decided *which* composition is rendered. Everything here is
        shared by the audience and Custom modes so their job records, snapshots and replay
        commands cannot drift apart.
        """
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
            if context is not None and recorded["audience"] != context:
                raise SiteError(HTTPStatus.BAD_REQUEST,
                                "A custom composition must keep the selected data context.")
            package = job_directory / "package"
            job = Job(job_id=job_id, preset=preset, mode=mode,
                      recipe_sha256=workbench.file_digest(snapshot),
                      classification=classification,
                      classification_basis=classification_basis,
                      context=context, origin=origin,
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

    def submit_custom(self, context):
        """Render one Custom composition; the job records its origin and its data context."""
        context = self._custom_context(context)
        _recipe_path, bundle = self.preset(context)
        eligible = list(self.topics(context))
        draft = self.custom_draft(context)
        if draft is None:
            recipe = library.initial_recipe(context)
            mode = "custom-initial"
        else:
            problem = draft.pending_problem()
            if problem is not None:
                if problem["kind"] == "empty-selection":
                    raise SiteError(HTTPStatus.BAD_REQUEST, COLLECTION_EMPTY_MESSAGE,
                                    code="collection_empty")
                raise SiteError(HTTPStatus.BAD_REQUEST,
                                f"The custom composition cannot be generated yet: "
                                f"{problem['message']}", code="draft_not_ready")
            # Generation commits the pending disease choice, exactly as the audience editor does.
            draft = workbench.commit_pending(draft, eligible)
            recipe = draft.effective()
            mode = "custom"
        if recipe["audience"] != context:
            raise SiteError(HTTPStatus.CONFLICT,
                            "The custom composition does not belong to the selected data context.",
                            code="context_mismatch")
        return self._launch(preset=CUSTOM, recipe=recipe, bundle=bundle, eligible=eligible,
                            audience=context, mode=mode, classification="custom",
                            classification_basis=None, origin="custom", context=context)

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

    def _custom_reuse_context(self, context):
        """The key and composition digest this context's current custom draft would render."""
        if context not in dict(AUDIENCES):
            return None, None
        try:
            _recipe_path, bundle = self.preset(context)
            eligible = list(self.topics(context))
            draft = self.custom_draft(context)
            if draft is None:
                recipe = library.initial_recipe(context)
            else:
                if draft.pending_problem() is not None:
                    return None, None
                recipe = draft.pending()
            components = self.reuse_components(recipe, bundle, eligible)
            return self.reuse_key(components), components["composition_sha256"]
        except (SiteError, workbench.WorkspaceError):
            return None, None

    def _composition_match(self, record, current_composition):
        """Composition-only comparison (sections, order, diseases) for history display."""
        if current_composition is None:
            return "unknown"
        snapshot = self.work_root / (record.get("snapshot") or "")
        if not record.get("snapshot") or not snapshot.is_file():
            return "unknown"
        audience = (record.get("context") if record.get("origin") == "custom"
                    else (record.get("preset") or record.get("bundle_id") or ""))
        try:
            recipe = _read_json(snapshot)
            bundle = self._bundle_path(audience)
            eligible = self.topics(audience)
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
            if item.get("origin") == "custom" and item.get("context"):
                audience = item["context"]
                key, composition = self._custom_reuse_context(audience)
            else:
                audience = payload.get("preset") or payload.get("bundle_id")
                key, composition = context(audience)
            item["reuse"] = self._history_reuse_view(payload, key, composition)
            item["composition_match"] = self._composition_match(payload, composition)
            item["context_label"] = dict(AUDIENCES).get(audience)
            entries.append(item)
        custom_drafts = sorted(path.name for path in (self.drafts_root / CUSTOM).glob("*")
                               if (path / workbench.DRAFT_EDITOR).is_file()) \
            if (self.drafts_root / CUSTOM).is_dir() else []
        return {"work_root": self.work_root.as_posix(),
                "inputs_root": self.inputs_root.as_posix(),
                "drafts": sorted(path.name for path in self.drafts_root.glob("*")
                                 if (path / workbench.DRAFT_EDITOR).is_file()),
                "custom_drafts": custom_drafts,
                "jobs": entries[:20]}

    # ------------------------------------------------------------------ artifacts
    # ------------------------------------------------------------------ report-bound sources
    # Everything below is resolved from the saved job and its frozen package. Nothing reads the
    # editor, the current interpretation, a live analysis or the working branch.

    _SOURCES_NOTE = ("This information describes this saved report. The current editable draft "
                     "may differ.")

    def _package_dir(self, record):
        """The report package directory, or None when it is missing or escapes the work root."""
        relative = record.get("preview_dir")
        if not relative:
            return None
        base = Path(os.path.realpath(self.work_root / relative))
        if self.work_root not in base.parents or not base.is_dir():
            return None
        return base

    @staticmethod
    def _package_json(package, name):
        """(value, status) for a package-side JSON file; never raises."""
        if package is None:
            return None, "unavailable"
        path = package / name
        if not path.is_file() or path.is_symlink():
            return None, "unavailable"
        try:
            return json.loads(path.read_text(encoding="utf-8")), "recorded"
        except (OSError, ValueError):
            return None, "unreadable"

    def _package_artifact(self, job_id, package, relative, detail=None):
        """One manifest-backed package artifact, offered only when it really exists."""
        if package is None:
            return None
        target = Path(os.path.realpath(package / relative))
        if package not in target.parents or target.is_symlink():
            return None
        if not target.is_file():
            return None
        return {"id": relative, "href": f"/reports/{job_id}/{relative}",
                "label": detail or relative, "bytes": target.stat().st_size}

    @staticmethod
    def _canonical_digest(payload):
        """The digest form the neutral provenance records as analysis_digest."""
        return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _recorded_analysis_digest(provenance):
        for block in (provenance or {}).get("blocks") or []:
            digest = (block or {}).get("analysis_digest")
            if digest:
                return digest
        return None

    def _retained_material(self, record, job_id, provenance, disclosure):
        """Steward-only retained material, bound to what THIS report recorded.

        The capture is offered only when its bytes still hash to the reported digest. Prepared
        rows and the saved analysis are offered only when they reproduce the analysis digest the
        report recorded; newer workspace revisions are shown separately and are never presented
        as the report's inputs. The raw captured file is not offered at all: the saved contract
        records permission for findings and (optionally) contributing records, not for the file,
        which may also contain columns this report never analysed.
        """
        policy = (disclosure or {}).get("policy")
        permit_values = bool((disclosure or {}).get("permit_values"))
        permit_records = bool((disclosure or {}).get("permit_records"))
        dataset = (provenance or {}).get("dataset") or {}
        digest = dataset.get("input_sha256")
        original_withheld = {
            "id": "original.bin", "label": "Original captured file", "status": "withheld",
            "detail": ("Not offered: the saved disclosure contract records permission for "
                       "numerical findings and, separately, contributing records — not for the "
                       "raw captured file. The file can also contain columns this report never "
                       "analysed.")}
        if record.get("mode") != "csv" or not digest:
            return {"available": False, "reason": "not_applicable",
                    "detail": "No retained neutral capture is associated with this report."}
        if policy != "local-audit":
            return {"available": False, "reason": "withheld",
                    "detail": ("Withheld by this report's disclosure policy. The retained "
                               "capture, prepared rows and saved analysis are not offered for a "
                               "restricted export.")}
        directory = Path(os.path.realpath(self._csv_root() / digest))
        if self._csv_root() not in directory.parents or not directory.is_dir():
            return {"available": False, "reason": "missing",
                    "detail": "The retained capture is no longer on disk."}

        recorded_digest = self._recorded_analysis_digest(provenance)
        items, current, withheld = [], [], [original_withheld]
        original = directory / "original.bin"
        if original.is_file() and not original.is_symlink():
            actual = hashlib.sha256(original.read_bytes()).hexdigest()
            if actual != digest:
                withheld.append({
                    "id": "original.bin", "label": "Original captured file",
                    "status": "integrity_failed",
                    "detail": ("The retained file no longer matches the digest recorded in this "
                               "report; it is not offered as the original input.")})

        analysis_path = directory / "neutral-analysis.json"
        analysis = None
        analysis_matches = False
        if analysis_path.is_file() and not analysis_path.is_symlink():
            try:
                analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
                analysis_matches = bool(recorded_digest) and \
                    self._canonical_digest(analysis) == recorded_digest
            except (OSError, ValueError):
                analysis = None
        if not permit_values:
            withheld.append({"id": "neutral-analysis.json",
                             "label": "Saved analysis (full precision)",
                             "status": "withheld",
                             "detail": ("Not permitted: this report's disclosure choice does "
                                        "not permit publishing numerical results.")})
        elif analysis_matches:
            items.append({"id": "neutral-analysis.json",
                          "label": "Saved analysis used by this report",
                          "href": f"/api/jobs/{job_id}/retained/neutral-analysis.json",
                          "status": "verified_now",
                          "detail": ("Identical to the analysis digest recorded in this report "
                                     "(checked now).")})
        elif analysis is not None:
            current.append({"id": "neutral-analysis.json",
                            "label": "Saved analysis",
                            "detail": ("Current retained workspace material; differs from this "
                                       "report.")})

        prepared_path = directory / "prepared.json"
        if prepared_path.is_file() and not prepared_path.is_symlink():
            if not permit_records:
                withheld.append({"id": "prepared.json", "label": "Prepared records",
                                 "status": "withheld",
                                 "detail": ("Not permitted: this report's disclosure choice does "
                                            "not include contributing records.")})
            elif analysis is None or not recorded_digest:
                current.append({"id": "prepared.json", "label": "Prepared records",
                                "detail": ("The report did not record an analysis identity to "
                                           "bind these rows to; they are current workspace "
                                           "material.")})
            else:
                try:
                    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
                    # The recorded digest covers the whole descriptor, including its source
                    # identity, so the re-derivation must carry the same context.
                    reproduced = neutral.describe(
                        list(prepared["rows"]), analysis["interpretation"],
                        dataset={"source_filename": dataset.get("source_filename"),
                                 "input_sha256": dataset.get("input_sha256")})
                    if self._canonical_digest(reproduced) == recorded_digest:
                        items.append({"id": "prepared.json",
                                      "label": "Prepared records used by this report",
                                      "href": f"/api/jobs/{job_id}/retained/prepared.json",
                                      "status": "verified_now",
                                      "detail": ("These rows reproduce the analysis digest "
                                                 "recorded in this report (checked now).")})
                    else:
                        current.append({"id": "prepared.json", "label": "Prepared records",
                                        "detail": ("Current retained workspace material; differs "
                                                   "from this report.")})
                except (OSError, ValueError, KeyError, TypeError):
                    withheld.append({"id": "prepared.json", "label": "Prepared records",
                                     "status": "unreadable",
                                     "detail": "The retained prepared rows are not readable."})

        return {"available": True, "reason": "permitted",
                "detail": ("Retained locally; not included in this report package. Only material "
                           "that still matches this report's recorded identities is offered."),
                "items": items, "current": current, "withheld": withheld}

    def retained_artifact(self, job_id, name):
        """One steward-only retained file, resolved from the job's recorded capture digest."""
        # The raw captured file is deliberately not downloadable: the saved contract records
        # permission for findings and contributing records, not for the file itself.
        allowed = {"prepared.json", "neutral-analysis.json"}
        if name not in allowed:
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        record = self._job_record(job_id)
        if record.get("status") != "succeeded" or record.get("mode") != "csv":
            raise SiteError(HTTPStatus.NOT_FOUND, "No retained capture for this job.")
        package = self._package_dir(record)
        provenance, status = self._package_json(package, "provenance.json")
        if status != "recorded":
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        disclosure = (provenance or {}).get("disclosure") or {}
        if disclosure.get("policy") != "local-audit":
            # Policy is enforced here, not in the browser.
            raise SiteError(HTTPStatus.FORBIDDEN,
                            "This report's disclosure policy does not permit retained files.",
                            code="withheld")
        if name == "neutral-analysis.json" and not disclosure.get("permit_values"):
            raise SiteError(HTTPStatus.FORBIDDEN,
                            "This report does not permit publishing numerical results.",
                            code="withheld")
        if name == "prepared.json" and not disclosure.get("permit_records"):
            raise SiteError(HTTPStatus.FORBIDDEN,
                            "This report does not include contributing records.",
                            code="withheld")
        digest = ((provenance or {}).get("dataset") or {}).get("input_sha256")
        if not digest:
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        directory = Path(os.path.realpath(self._csv_root() / digest))
        if self._csv_root() not in directory.parents or not directory.is_dir():
            raise SiteError(HTTPStatus.NOT_FOUND, "The retained capture is no longer on disk.")
        target = Path(os.path.realpath(directory / name))
        if target != directory and directory not in target.parents:
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        if target.is_symlink() or directory.is_symlink() or not target.is_file():
            raise SiteError(HTTPStatus.NOT_FOUND, "Unknown artifact.")
        recorded = self._recorded_analysis_digest(provenance)
        if not recorded:
            raise SiteError(HTTPStatus.CONFLICT,
                            "This report did not record an analysis identity to serve against.",
                            code="integrity_failed")
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise SiteError(HTTPStatus.CONFLICT, "The retained file is not readable.",
                            code="integrity_failed") from None
        if name == "neutral-analysis.json":
            matches = self._canonical_digest(current) == recorded
        else:
            try:
                stored = json.loads((directory / "neutral-analysis.json")
                                    .read_text(encoding="utf-8"))
                dataset = (provenance or {}).get("dataset") or {}
                matches = self._canonical_digest(
                    neutral.describe(list(current["rows"]), stored["interpretation"],
                                     dataset={"source_filename": dataset.get("source_filename"),
                                              "input_sha256": dataset.get("input_sha256")})
                ) == recorded
            except (OSError, ValueError, KeyError, TypeError):
                matches = False
        if not matches:
            raise SiteError(HTTPStatus.CONFLICT,
                            "The retained file differs from this report's recorded analysis; "
                            "it is current workspace material, not this report's result.",
                            code="integrity_failed")
        return target, "application/json"

    def report_sources(self, job_id):
        """Read-only, report-bound metadata for one saved report."""
        record = self._job_record(job_id)
        job = self.public_job(record)
        package = self._package_dir(record)
        provenance, provenance_status = self._package_json(package, "provenance.json")
        composition, composition_status = self._package_json(package, "composition.json")
        if composition is None and package is not None:
            composition, composition_status = self._package_json(
                package, "reproduction/composition.json")

        neutral = bool((provenance or {}).get("neutral")) or \
            record.get("mode") == "csv" or (provenance or {}).get("input_kind") == "neutral"
        disclosure = (provenance or {}).get("disclosure") or {}
        dataset_record = (provenance or {}).get("dataset") or {}

        report = {
            "job_id": job.get("job_id"),
            "created_utc": job.get("created_utc"),
            "finished_utc": job.get("finished_utc"),
            "status": job.get("status"),
            "mode": job.get("mode") or ("neutral" if neutral else None),
            "profile": ((composition or {}).get("audience")
                        or ((provenance or {}).get("composition") or {}).get("audience")
                        or job.get("preset")),
            "origin": job.get("origin"),
            "package_sha256": record.get("package_sha256"),
            "package_files": record.get("package_files"),
            "recipe_sha256": job.get("recipe_sha256"),
            "preview": bool((provenance or {}).get("preview")),
            "preview_notice": ((provenance or {}).get("preview") or {}).get("notice"),
            "note": self._SOURCES_NOTE,
            "links": {},
            "provenance_status": provenance_status,
            "composition_status": composition_status,
        }
        if job.get("status") == "succeeded":
            for key, relative, label in (
                    ("report", "report.html", "Open report"),
                    ("methods", "methods.html", "Methods"),
                    ("provenance", "provenance.json", "Provenance JSON"),
                    ("composition", "reproduction/composition.json", "Frozen request")):
                artifact = self._package_artifact(job_id, package, relative, label)
                if artifact:
                    report["links"][key] = artifact["href"]

        # ---- Data ---------------------------------------------------------------------------
        analysis, analysis_status = (None, "unavailable")
        if package is not None:
            analysis, analysis_status = self._package_json(package, "data/neutral-analysis.json")
            if analysis is None:
                analysis, analysis_status = self._package_json(
                    package, "data/neutral-summary.json")
        interpretation, interpretation_status = self._package_json(
            package, "data/interpretation.json")

        data = {"kind": "neutral" if neutral else "health"}
        if neutral:
            data.update({
                "filename": dataset_record.get("source_filename"),
                "digest": dataset_record.get("input_sha256"),
                "captured_at_utc": dataset_record.get("captured_at_utc"),
                "measured_at": None,
                "user_version": None,
                "roles": ({key: (interpretation or {}).get(key) for key in
                           ("category", "measure", "time", "missing_tokens")}
                          if interpretation_status == "recorded" else None),
                "measure": {"label": dataset_record.get("measure_label"),
                            "unit": dataset_record.get("unit"),
                            "meaning": dataset_record.get("row_meaning")},
                "filters": "None recorded: the report analyses the confirmed selection.",
                "counts": None,
                "coverage": None,
                "status": analysis_status if analysis_status == "recorded" else "unavailable",
            })
            if isinstance(analysis, dict):
                data["counts"] = {"analysed_records": analysis.get("row_count"),
                                  "analysed_groups": analysis.get("group_count"),
                                  "analysed_periods": (analysis.get("time") or {}).get(
                                      "period_count")}
                data["coverage"] = {
                    "from": ((analysis.get("time") or {}).get("periods") or [None])[0],
                    "to": ((analysis.get("time") or {}).get("periods") or [None])[-1],
                    "missing": analysis.get("missing"),
                    "repeated_group_period_keys": (analysis.get("quality") or {}).get(
                        "repeated_group_period_keys"),
                }
                method = analysis.get("method") or {}
                data["method"] = {"calc_version": method.get("calc_version"),
                                  "definitions": method.get("definitions")}
        else:
            source = (provenance or {}).get("data") or {}
            data.update({
                "filename": ((composition or {}).get("audience") or "health") + " analysis bundle",
                "digest": source.get("snapshot_id"),
                "captured_at_utc": (source.get("retrieved_at_utc_range") or [None])[-1],
                "measured_at": {"publishing_date_range": source.get("publishing_date_range")},
                "user_version": None,
                "roles": None,      # health bundles are not a user interpretation; omitted
                "measure": None,    # never print synthetic measure labels
                "filters": (provenance or {}).get("filters"),
                "counts": {"datasets_in_snapshot": source.get("datasets_in_snapshot"),
                           "datasets_used": source.get("datasets_used")},
                "coverage": None,
                "status": "recorded" if source else "unavailable",
            })

        # ---- sections: per-section display scope, never one report-wide number ---------------
        sections = []
        if neutral and isinstance(composition, dict) and isinstance(analysis, dict):
            total_groups = analysis.get("group_count")
            periods = (analysis.get("time") or {}).get("periods") or []
            titles = composition.get("titles") or {}
            for entry in composition.get("blocks") or []:
                display = entry.get("display")
                if not isinstance(display, dict):
                    continue
                groups = display.get("groups")
                shown_groups = len(groups) if isinstance(groups, list) else total_groups
                settings = display.get("periods") or {"mode": "all"}
                if settings.get("mode") == "all":
                    shown_periods = len(periods)
                elif settings.get("mode") == "list":
                    shown_periods = len([item for item in settings.get("values") or []
                                         if item in periods])
                else:
                    shown_periods = len([item for item in periods
                                         if settings.get("from", "") <= item <=
                                         str(settings.get("to", "")) + "T23:59:59"])
                sections.append({
                    "instance_id": entry.get("instance_id"),
                    "block": entry.get("block"),
                    "title": titles.get(entry.get("instance_id")),
                    "layout": display.get("layout"),
                    "groups": {"shown": shown_groups, "analysed": total_groups},
                    "periods": ({"shown": shown_periods, "analysed": len(periods)}
                                if periods else None),
                    "statistics": display.get("statistics"),
                    "precision": display.get("precision"),
                })
        elif not neutral:
            # Health packages may carry only the frozen provenance; its composition record is
            # the same render-time snapshot, so it is the documented fallback.
            recorded = composition if isinstance(composition, dict) else {}
            if not recorded:
                recorded = (provenance or {}).get("composition") or {}
            scope = recorded.get("display_scope") or {}
            sections = [{"block": "display_scope",
                         "displayed_topics": len(scope.get("displayed_topics") or []),
                         "group_summaries": len(scope.get("group_summaries") or []),
                         "monitoring_topics": len(scope.get("monitoring_topics") or [])}]

        # ---- Attribution ----------------------------------------------------------------------
        attribution = {"recorded": False, "kind": "user-supplied" if neutral else "health"}
        if neutral:
            attribution.update({
                "detail": ("No publisher, source URL, licence or dataset version is recorded for "
                           "this report. Uploaded files are user-supplied and not independently "
                           "authenticated; a filename or column name does not establish a source."),
            })
        else:
            source = (provenance or {}).get("data") or {}
            attribution.update({
                "recorded": bool(source.get("publisher") or source.get("api")),
                "publisher": source.get("publisher"),
                "url": source.get("api"),
                "version": {"snapshot_id": source.get("snapshot_id"),
                            "publishing_date_range": source.get("publishing_date_range")},
                "licence": "Not recorded for this report.",
                "detail": ("Recorded at render time from the saved source manifest. Source "
                           "eligibility is not re-derived here."),
            })

        # ---- Methods and reproduction ---------------------------------------------------------
        methods = {
            "methods_href": report["links"].get("methods"),
            "provenance_href": report["links"].get("provenance"),
            "composition_href": report["links"].get("composition"),
            "method": data.get("method"),
            "code": None,
            "environment": None,
            "replay": None,
        }
        if neutral:
            implementations = {}
            for block in (provenance or {}).get("blocks") or []:
                for item in ((block or {}).get("implementation") or {}).values():
                    if isinstance(item, dict) and item.get("file"):
                        implementations[item["file"]] = item.get("sha256")
            methods["code"] = ({"kind": "retained implementation at render time",
                                "files": implementations}
                               if implementations else {"kind": "not recorded"})
            methods["environment"] = {"kind": "not recorded in this package"}
        else:
            code = (provenance or {}).get("code") or {}
            methods["code"] = {"kind": "recorded revision",
                               "git_commit": code.get("git_commit"),
                               "worktree": code.get("git_worktree_clean"),
                               "source_state": (code.get("source_state") or {}).get("label"),
                               "workflow_config_sha256": ((code.get("workflow_config") or {})
                                                          .get("sha256"))}
            helpers = ((provenance or {}).get("output") or {}).get("presentation_helpers_sha256")
            methods["environment"] = {"kind": "recorded render helpers",
                                      "files": helpers} if helpers else {"kind": "not recorded"}

        replay = {"command": job.get("replay_command"), "state": "unavailable", "detail": None}
        if job.get("status") != "succeeded":
            replay["detail"] = "This job did not produce a report; there is nothing to replay."
        elif not job.get("replay_command"):
            replay["detail"] = "No replay command was recorded for this report."
        elif neutral:
            if data.get("digest"):
                directory = Path(os.path.realpath(self._csv_root() / data["digest"]))
                if (self._csv_root() in directory.parents and directory.is_dir()
                        and (directory / "neutral-analysis.json").is_file()):
                    replay.update({"state": "complete_local",
                                   "detail": ("Complete local replay is possible: the captured "
                                              "dataset and frozen request are retained here. "
                                              "The command is recorded, not proof it was run.")})
                else:
                    replay.update({"state": "requires_private_inputs",
                                   "detail": ("Replay requires the retained private capture, "
                                              "which is not present in this workspace.")})
        else:
            replay.update({"state": "requires_private_inputs",
                           "detail": ("Health replay needs the retained analysis bundle and the "
                                      "pinned environment; this package does not contain them.")})
        methods["replay"] = replay

        # ---- Artifacts -------------------------------------------------------------------------
        notices = []
        artifacts = []
        package_ok = True
        if package is not None and record.get("package_sha256"):
            digest_now, count_now = self._package_digest(package)
            package_ok = (digest_now == record.get("package_sha256")
                          and record.get("package_files") in (None, count_now))
        if not package_ok:
            notices.append("The report package no longer matches the digest recorded at "
                           "generation; its file links are withheld.")
        else:
            # A file is offered only when the recorded policy permits that class of content,
            # not merely because it happens to exist in the package directory.
            permitted = {
                "data/neutral-analysis.json": bool(disclosure.get("permit_values")),
                "data/neutral-summary.json": True,
                "data/selected-records.csv": bool(disclosure.get("permit_records")),
            }
            for relative, label, kind in (
                    ("report.html", "Report (HTML)", "report"),
                    ("methods.html", "Methods and sources (HTML)", "report"),
                    ("provenance.json", "Machine-readable provenance", "metadata"),
                    ("composition.json", "Frozen effective request", "metadata"),
                    ("reproduction/composition.json", "Frozen request (reproduction copy)",
                     "metadata"),
                    ("data/dataset.json", "Dataset passport", "data"),
                    ("data/interpretation.json", "Confirmed interpretation", "data"),
                    ("data/neutral-analysis.json", "Saved analysis (full precision)", "data"),
                    ("data/neutral-summary.json", "Restricted analysis summary", "data"),
                    ("data/selected-records.csv", "Contributing records (permitted)", "data")):
                if not permitted.get(relative, True):
                    continue
                artifact = self._package_artifact(job_id, package, relative, label)
                if artifact:
                    artifact["kind"] = kind
                    artifacts.append(artifact)

        retained = self._retained_material(record, job_id, provenance, disclosure)

        if package is None:
            notices.append("The report package is no longer on disk; only the job record is "
                           "available.")
        if provenance_status != "recorded":
            notices.append("This report has no readable provenance; its metadata is limited to "
                           "the job record.")
        if composition_status != "recorded":
            notices.append("The frozen request is missing or unreadable for this report.")
        if neutral and not disclosure:
            notices.append("No disclosure policy is recorded for this report; the package is "
                           "shown as published.")

        return {
            "report": report,
            "disclosure": {
                "recorded": bool(disclosure),
                "policy": disclosure.get("policy"),
                "label": disclosure.get("label"),
                "summary": disclosure.get("summary"),
                "consequence": disclosure.get("consequence"),
                "evidence": disclosure.get("evidence"),
            },
            "data": data,
            "sections": sections,
            "attribution": attribution,
            "methods": methods,
            "artifacts": artifacts,
            "retained": retained,
            "notices": notices,
        }

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
            if path == "/api/custom":
                return self._json(HTTPStatus.OK, self.site.custom_document(
                    self._query().get("context") or None,
                    selected=self._query().get("audience") or None))
            if path == "/api/csv":
                return self._json(HTTPStatus.OK, self.site.csv_document(
                    self._query().get("digest") or None))
            if path == "/api/saved":
                return self._json(HTTPStatus.OK, self.site.saved())
            if path == "/api/jobs":
                return self._json(HTTPStatus.OK, {"jobs": self.site.jobs()})
            match = re.fullmatch(r"/api/jobs/([^/]+)/sources", path)
            if match:
                return self._json(HTTPStatus.OK, self.site.report_sources(match.group(1)))
            match = re.fullmatch(r"/api/jobs/([^/]+)/retained/([a-z0-9._-]+)", path)
            if match:
                target, content_type = self.site.retained_artifact(match.group(1),
                                                                   match.group(2))
                body = target.read_bytes()
                filename = target.name
                headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
                return self._send(HTTPStatus.OK, body, content_type, headers)
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
            if path == "/api/csv/upload":
                body, filename = self._multipart_file()
                capture = self.site.csv_capture(body, filename)
                return self._json(HTTPStatus.OK, {"capture": capture.as_public()})
            payload = self._body()
            if path == "/api/reuse":
                self._check_mutation("reuse", payload, {"preset", "job_id", "context"})
                if payload.get("preset") == CUSTOM:
                    return self._json(HTTPStatus.OK, self.site.confirm_reuse_custom(
                        payload.get("context", ""), payload.get("job_id", "")))
                return self._json(HTTPStatus.OK, self.site.confirm_reuse(
                    payload.get("preset", ""), payload.get("job_id", "")))
            if path == "/api/custom/edit":
                self._check_mutation("custom-edit", payload,
                                     {"context", "action", "instance", "value"})
                return self._json(HTTPStatus.OK, self.site.custom_edit(
                    payload.get("context", ""), payload.get("action", ""),
                    payload.get("instance", ""), payload.get("value")))
            if path == "/api/custom/reset":
                self._check_mutation("custom-reset", payload, {"context"})
                return self._json(HTTPStatus.OK,
                                  self.site.custom_reset(payload.get("context", "")))
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
                self._check_mutation("generate", payload, {"preset", "context"})
                preset = payload.get("preset", "")
                if preset == CUSTOM:
                    return self._json(HTTPStatus.ACCEPTED,
                                      self.site.submit_custom(payload.get("context", "")))
                return self._json(HTTPStatus.ACCEPTED, self.site.submit(preset))
            if path == "/api/csv/confirm":
                self._check_mutation("csv-confirm", payload,
                                     {"digest", "interpretation"})
                return self._json(HTTPStatus.OK, self.site.csv_confirm(
                    payload.get("digest", ""), payload.get("interpretation") or {}))
            if path == "/api/csv/generate":
                self._check_mutation("csv-generate", payload,
                                     {"digest", "recipe"})
                result = self.site.csv_submit(payload.get("digest", ""),
                                              payload.get("recipe") or {})
                return self._json(HTTPStatus.OK if result.get("reused")
                                  else HTTPStatus.ACCEPTED, result)
            if path == "/api/csv/edit":
                self._check_mutation("csv-edit", payload,
                                     {"digest", "action", "instance", "value"})
                recipe = self.site.csv_draft_edit(
                    payload.get("digest", ""), payload.get("action", ""),
                    payload.get("instance", ""), payload.get("value"))
                return self._json(HTTPStatus.OK,
                                  {"recipe": recipe,
                                   "document": self.site.csv_document(
                                       payload.get("digest", ""))})
            raise SiteError(HTTPStatus.NOT_FOUND, "Not found.")
        except SiteError as error:
            return self._error(error)
        except Exception:                                # noqa: BLE001 - no tracebacks to client
            return self._error(None)

    def _multipart_file(self):
        """Bound multipart/form-data file capture: one file part, streamed and hashed.

        The whole request body is size-limited before parsing; the file payload itself is
        bounded again by the neutral limits. Overlong or malformed requests are rejected
        before any partial capture is promoted.
        """
        content_type = self.headers.get("Content-Type") or ""
        match = re.fullmatch(r"multipart/form-data; boundary=(.+)", content_type,
                             re.IGNORECASE)
        if not match:
            raise SiteError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                            "CSV uploads use multipart/form-data.")
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            raise SiteError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length.")
        if length <= 0:
            raise SiteError(HTTPStatus.BAD_REQUEST, "An upload body is required.")
        if length > NEUTRAL_MAX_BODY:
            raise SiteError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                            "The upload is too large.")
        boundary = ("--" + match.group(1)).encode("utf-8")
        closing = ("\r\n--" + match.group(1)).encode("utf-8")
        raw = self.rfile.read(length)
        if len(raw) != length or not raw.startswith(boundary):
            raise SiteError(HTTPStatus.BAD_REQUEST, "Malformed multipart body.")
        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            raise SiteError(HTTPStatus.BAD_REQUEST, "Malformed multipart body.")
        head = raw[len(boundary) + 2:header_end].decode("utf-8", "replace")
        disposition = re.search(r'name="([^"]+)"', head)
        filename = re.search(r'filename="([^"]*)"', head)
        if not disposition or not filename:
            raise SiteError(HTTPStatus.BAD_REQUEST,
                            "The upload needs a file field with a file name.")
        body_end = raw.find(closing, header_end + 4)
        if body_end == -1:
            raise SiteError(HTTPStatus.BAD_REQUEST, "Malformed multipart body.")
        body = raw[header_end + 4:body_end]
        if not body:
            raise SiteError(HTTPStatus.BAD_REQUEST, "The upload contains no data.")
        return body, filename.group(1)

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
