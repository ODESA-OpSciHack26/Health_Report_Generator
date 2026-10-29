"""Same-audience composition workbench: open, copy, reorder/configure, preview, replay.

Scope of this service, deliberately narrow:

* one audience per workspace operation — the recipe must name the same audience as the
  bundle's stakeholder, and that equality is enforced by ``publish.render`` and re-checked
  here only to produce an earlier, friendlier message;
* edits are limited to reordering existing blocks and to a closed list of supported
  presentation options per block type; every recipe is validated by
  ``publish.validate_composition`` and nothing is ever silently repaired;
* a preview is a *real* render of a *saved* recipe file into a workspace directory, marked
  as not an accepted publication in its provenance, its ``preview.json`` and the page banner;
* preview and publication are different things here. Nothing in this module writes accepted
  output state, promotion pointers or catalogue entries — there is no such state in the
  project, and this service does not introduce one. ``publish.publish_evidence`` is reused
  because it only packages render-local evidence (byte copies of the saved bundle into
  ``<report>/data`` with digest checks); it does not promote anything.

Every write is confined to the workspace, refuses to overwrite, and is done with an
exclusive create or an atomic replace of a file the workspace already owns.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shlex
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import publish

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MAINTAINED_RECIPES = tuple(
    HERE / "config/composer/compositions" / f"{audience}.json"
    for audience in ("researcher", "health_institution", "public")
)
WORKSPACE_MARKER = "workspace.json"
WORKSPACE_SCHEMA = "health-report/composer-workspace/1"
PREVIEW_SCHEMA = "health-report/composer-preview/1"
PREVIEW_NOTICE = publish.PREVIEW_NOTICE
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}\.json")
# Supported presentation options, per block type. Anything else is refused rather than
# guessed; adding an option here also needs the loader to accept it.
SUPPORTED_OPTIONS = {
    "series-collection": ("presentation.style", "presentation.default_topic"),
    "series-trend": ("presentation.style",),
    "reference-comparison": ("topic",),
}
STYLE_VALUES = ("standard", "compact")


class WorkspaceError(ValueError):
    """A user-actionable workbench error; safe to show in the local UI."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _real(path):
    return Path(os.path.realpath(Path(path)))


def _inside(root, candidate):
    """Resolve symlinks and refuse anything outside the workspace root."""
    root, candidate = _real(root), _real(candidate)
    if candidate != root and root not in candidate.parents:
        raise WorkspaceError(
            f"Refusing a path outside the workspace: {candidate} is not inside {root}.")
    return candidate


def _atomic_new(path, data):
    """Create ``path`` with its exact bytes, failing if it already exists."""
    path = Path(path)
    temporary = path.parent / f".tmp-{uuid.uuid4().hex}"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise WorkspaceError(f"Refusing to overwrite an existing file: {path}") from None
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return path


def _atomic_replace(path, data):
    """Replace a file the workspace already owns, without a partial-write window."""
    path = Path(path)
    temporary = path.parent / f".tmp-{uuid.uuid4().hex}"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return path


def recipe_bytes(recipe):
    """Canonical bytes of a validated recipe: the exact content a replay renders."""
    return (json.dumps(recipe, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def recipe_digest(recipe):
    return hashlib.sha256(recipe_bytes(recipe)).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def open_recipe(path):
    """Read and validate one recipe through the shared loader validator."""
    path = Path(path)
    if not path.is_file():
        raise WorkspaceError(f"Recipe file not found: {path}")
    try:
        recipe = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkspaceError(f"Recipe is not valid JSON: {path} ({error.msg})") from None
    try:
        return publish.validate_composition(recipe)
    except ValueError as error:
        raise WorkspaceError(f"Recipe rejected by the composition loader: {error}") from None


def validate_recipe(recipe):
    try:
        return publish.validate_composition(recipe)
    except ValueError as error:
        raise WorkspaceError(f"Recipe rejected by the composition loader: {error}") from None


# --------------------------------------------------------------------------- workspace

def create_workspace(root):
    """Create a new workspace directory; never reuse or replace an existing one."""
    root = Path(root).expanduser()
    try:
        os.mkdir(root)
    except FileExistsError:
        raise WorkspaceError(
            f"Workspace already exists; choose a new directory instead of reusing {root}.") from None
    except FileNotFoundError:
        raise WorkspaceError(f"Workspace parent directory does not exist: {root.parent}") from None
    os.mkdir(root / "previews")
    marker = {"schema": WORKSPACE_SCHEMA, "created_utc": _now(),
              "notice": "Recipes and previews only. No accepted publication is created here."}
    _atomic_new(root / WORKSPACE_MARKER, (json.dumps(marker, indent=2) + "\n").encode("utf-8"))
    return _real(root)


def open_workspace(root):
    root = _real(Path(root).expanduser())
    if not (root / WORKSPACE_MARKER).is_file():
        raise WorkspaceError(f"Not a workbench workspace (no {WORKSPACE_MARKER}): {root}")
    return root


def workspace_for(recipe_path):
    """The workspace that owns a saved recipe, found through its marker file."""
    path = _real(Path(recipe_path).expanduser())
    for candidate in (path.parent, *path.parents):
        if (candidate / WORKSPACE_MARKER).is_file():
            return open_workspace(candidate)
    raise WorkspaceError(f"The recipe is not inside a workbench workspace: {path}")


def _workspace_target(workspace, name):
    name = str(name)
    if not NAME_RE.fullmatch(name):
        raise WorkspaceError(
            "Recipe file name must be a plain name such as 'trial.json' "
            f"(no directories or leading dots): {name!r}")
    return _inside(workspace, Path(workspace) / name)


def copy_recipe(workspace, source, name=None):
    """Save a workspace copy of a recipe.

    With no ``name`` change the source bytes are copied verbatim, so an untouched copy is
    byte-identical to the file it came from.
    """
    workspace = open_workspace(workspace)
    source = Path(source)
    open_recipe(source)
    target = _workspace_target(workspace, name or source.name)
    return _atomic_new(target, source.read_bytes())


def save_recipe(workspace, recipe, name):
    """Write an edited recipe as a new file (save-as) or replace this workspace's own file."""
    workspace = open_workspace(workspace)
    target = _workspace_target(workspace, name)
    data = recipe_bytes(validate_recipe(recipe))
    if target.exists():
        raise WorkspaceError(
            f"Refusing to overwrite an existing recipe: {target}. "
            "Use save-in-place for a file you already own in this workspace.")
    return _atomic_new(target, data)


def save_in_place(workspace, path, recipe):
    """Replace an existing recipe file that lives inside this workspace."""
    workspace = open_workspace(workspace)
    path = _inside(workspace, Path(path))
    if not path.is_file():
        raise WorkspaceError(f"Recipe to update does not exist: {path}")
    return _atomic_replace(path, recipe_bytes(validate_recipe(recipe)))


# --------------------------------------------------------------------------- edits

def move_block(recipe, instance_id, direction):
    """Move one existing block up or down; identity and bindings are untouched."""
    recipe = validate_recipe(recipe)
    blocks = list(recipe["blocks"])
    ids = [entry["instance_id"] for entry in blocks]
    if instance_id not in ids:
        raise WorkspaceError(
            f"Unknown block instance {instance_id!r}. This recipe contains: {', '.join(ids)}")
    if direction not in ("up", "down"):
        raise WorkspaceError("Direction must be 'up' or 'down'.")
    index = ids.index(instance_id)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(blocks):
        raise WorkspaceError(
            f"Block {instance_id!r} is already at the {'top' if direction == 'up' else 'bottom'}.")
    blocks[index], blocks[target] = blocks[target], blocks[index]
    return validate_recipe({**recipe, "blocks": blocks})


def _entry(recipe, instance_id):
    for entry in recipe["blocks"]:
        if entry["instance_id"] == instance_id:
            return entry
    ids = ", ".join(item["instance_id"] for item in recipe["blocks"])
    raise WorkspaceError(f"Unknown block instance {instance_id!r}. This recipe contains: {ids}")


def set_block_option(recipe, instance_id, option, value):
    """Set one supported presentation option; the loader decides whether it is allowed."""
    recipe = validate_recipe(recipe)
    entry = _entry(recipe, instance_id)
    options = SUPPORTED_OPTIONS.get(entry["block"], ())
    if option not in options:
        raise WorkspaceError(
            f"Block {entry['block']!r} does not support {option!r}. "
            f"Supported options: {', '.join(options) if options else 'none'}.")
    value = "" if value is None else str(value)
    if not value:
        raise WorkspaceError(f"No value supplied for {option!r}.")
    if option.endswith("style") and value not in STYLE_VALUES:
        raise WorkspaceError(f"Unsupported style {value!r}; choose one of {list(STYLE_VALUES)}.")
    blocks = []
    for item in recipe["blocks"]:
        if item["instance_id"] != instance_id:
            blocks.append(dict(item))
            continue
        changed = dict(item)
        if option.startswith("presentation."):
            field = option.split(".", 1)[1]
            presentation = dict(changed.get("presentation") or {})
            presentation[field] = value
            changed["presentation"] = presentation
        else:
            changed[option] = value
        blocks.append(changed)
    return validate_recipe({**recipe, "blocks": blocks})


def available_topics(bundle):
    """Topics offered as option values: the saved selection's included topics.

    Option discovery only — the composition loader and the collection builder remain the
    authority, and a topic offered here still has to resolve when the preview builds the block.
    """
    bundle = Path(bundle)
    selection = bundle / "selection.csv"
    if not selection.is_file():
        raise WorkspaceError(f"Bundle has no selection.csv: {bundle}")
    with selection.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return sorted({(row.get("topic") or "").strip() for row in rows
                   if (row.get("status") or "").strip().lower() == "included"} - {""})


# --------------------------------------------------------------------------- preview

@dataclass(frozen=True)
class Preview:
    directory: Path
    recipe_path: Path
    recipe_sha256: str
    report: Path
    methods: Path
    provenance: Path
    metadata: Path
    notice: str = PREVIEW_NOTICE
    accepted_output: bool = False

    @property
    def report_html(self):
        return self.report


def _bundle_audience(bundle):
    stakeholder = Path(bundle) / "stakeholder.json"
    if not stakeholder.is_file():
        raise WorkspaceError(f"Bundle has no stakeholder.json: {bundle}")
    return json.loads(stakeholder.read_text(encoding="utf-8")).get("id")


def render_preview(recipe_path, bundle, directory, *, quarto="quarto", data_root=None,
                   workflow_config=None, render=None, audience=None, origin=None):
    """Render a saved recipe into a new directory as a preview package.

    ``directory`` must not exist: a preview never reuses or overwrites an earlier one. The
    rendered recipe is a byte copy of the saved file, and the package records that it is not
    an accepted publication. A failure marks the new directory as failed, writes no report
    there, and leaves every earlier package untouched.
    """
    recipe_path = Path(recipe_path)
    if not recipe_path.is_file():
        raise WorkspaceError(f"Recipe to preview does not exist: {recipe_path}")
    recipe = open_recipe(recipe_path)
    audience = audience or _bundle_audience(bundle)
    if recipe["audience"] != audience:
        raise WorkspaceError(
            f"Recipe audience {recipe['audience']!r} does not match the bundle audience "
            f"{audience!r}; a same-audience composition is required.")
    source_bytes = recipe_path.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()

    directory = Path(directory)
    if directory.exists():
        raise WorkspaceError(
            f"Preview directory already exists; refusing to reuse it: {directory}")
    directory.mkdir(parents=True, exist_ok=False)

    snapshot = _atomic_new(directory / "composition.json", source_bytes)
    metadata = {"schema": PREVIEW_SCHEMA, "status": "rendering", "created_utc": _now(),
                "notice": PREVIEW_NOTICE, "accepted_output": False,
                "workspace": str(origin) if origin else None, "source_recipe": str(recipe_path),
                "recipe_sha256": digest, "audience": audience}
    metadata_path = directory / "preview.json"
    _atomic_new(metadata_path, (json.dumps(metadata, indent=2) + "\n").encode("utf-8"))

    render_fn = render or publish.render
    # `build_provenance` records the workflow file as {path, sha256}, which is what the CLI
    # passes; accept a path here so callers do not have to know that detail.
    workflow_record = (publish._workflow_record(workflow_config)
                       if isinstance(workflow_config, (str, Path)) else workflow_config)
    try:
        provenance = publish.build_provenance(bundle, "html", quarto, data_root,
                                              workflow_record, preview=True)
        render_fn(bundle, directory / "report.html", "html", quarto, provenance,
                  directory / "provenance.json", snapshot)
    except Exception as error:                      # noqa: BLE001 - recorded, then re-raised
        metadata.update({"status": "failed", "finished_utc": _now(),
                         "error": f"{type(error).__name__}: {error}"})
        _atomic_replace(metadata_path, (json.dumps(metadata, indent=2) + "\n").encode("utf-8"))
        raise WorkspaceError(
            f"Preview failed; earlier previews and saved recipes are unchanged. "
            f"Directory: {directory}. Error: {type(error).__name__}: {error}") from None

    metadata.update({"status": "preview", "finished_utc": _now(),
                     "report": "report.html", "methods": "methods.html",
                     "provenance": "provenance.json", "composition": "composition.json",
                     "published": False})
    _atomic_replace(metadata_path, (json.dumps(metadata, indent=2) + "\n").encode("utf-8"))
    result = Preview(directory=directory, recipe_path=snapshot, recipe_sha256=digest,
                     report=directory / "report.html", methods=directory / "methods.html",
                     provenance=directory / "provenance.json", metadata=metadata_path)
    recorded = json.loads(result.provenance.read_text(encoding="utf-8"))
    marker = recorded.get("preview") or {}
    if marker.get("status") != "preview" or marker.get("accepted_output") is not False:
        raise WorkspaceError(
            f"Preview provenance does not record preview status: {result.provenance}")
    return result


def preview(workspace, recipe_path, *, bundle, quarto="quarto", data_root=None,
            workflow_config=None, render=None):
    """Render a workspace-contained recipe as a preview in a new directory under ``previews``."""
    workspace = open_workspace(workspace)
    recipe_path = _inside(workspace, Path(recipe_path))
    previews = Path(workspace) / "previews"
    if previews.is_symlink():
        raise WorkspaceError(f"Refusing a symlinked previews directory: {previews}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = previews / f"{stamp}-{os.getpid()}-{uuid.uuid4().hex[:12]}"
    _inside(workspace, directory)
    return render_preview(recipe_path, bundle, directory, quarto=quarto, data_root=data_root,
                          workflow_config=workflow_config, render=render, origin=workspace)


# --------------------------------------------------------------------------- replay

def replay_command(*, recipe_path, bundle, output_dir, data_root=None, workflow_config=None,
                   python="python", publish_script=None):
    """The supported CLI replay of a saved recipe, as an argv list and a quoted string.

    The CLI is the same entry point the batch uses; nothing is executed here. Paths are
    quoted with ``shlex.quote`` so spaces and punctuation survive a copy-paste.
    """
    script = Path(publish_script) if publish_script else HERE / "publish.py"
    output_dir = Path(output_dir)
    argv = [str(python), str(script), "html",
            "--bundle", str(bundle),
            "--output", str(output_dir / "report.html"),
            "--provenance", str(output_dir / "provenance.json"),
            "--composition", str(recipe_path)]
    if data_root:
        argv += ["--data-root", str(data_root)]
    if workflow_config:
        argv += ["--workflow-config", str(workflow_config)]
    return argv, " ".join(shlex.quote(part) for part in argv)


# --------------------------------------------------------------------------- drafts

# A draft keeps the full validated recipe in ``recipe.json`` and the editor-only state in
# ``editor.json``. The composition schema is untouched: which sections the reader sees is a
# presentation decision held beside the recipe, and the effective recipe handed to the
# renderer is the recipe minus excluded blocks, validated again through the shared loader.
DRAFT_SCHEMA = "health-report/composer-draft/1"      # readable legacy state
DRAFT_SCHEMA_V2 = "health-report/composer-draft/2"   # current: pending selection beside the recipe
DRAFT_RECIPE = "recipe.json"
DRAFT_EDITOR = "editor.json"
# Sections the product requires in every report, with the explanation shown beside the
# disabled control. Nothing else is forced; the validator decides what a recipe may be.
REQUIRED_BLOCKS = {
    "limitations": "Required: every report states its limitations and cautions.",
    "reproduction": "Required: readers must be able to reach the evidence and reproduction record.",
}
SELECTABLE_BLOCKS = ("series-collection",)


@dataclass(frozen=True)
class Draft:
    root: Path
    recipe: dict
    editor: dict

    @property
    def audience(self):
        return self.recipe["audience"]

    @property
    def revision(self):
        return self.editor["revision"]

    @property
    def excluded(self):
        return tuple(self.editor["excluded"])

    @property
    def selection(self):
        return dict(self.editor.get("selection") or {})

    def included(self):
        excluded = set(self.editor["excluded"])
        return [entry for entry in self.recipe["blocks"]
                if entry["instance_id"] not in excluded]

    def effective(self):
        """The last accepted, renderable recipe: the saved copy minus excluded sections."""
        return publish.validate_composition({**self.recipe, "blocks": self.included()})

    def pending_blocks(self):
        """Included blocks with the editor's pending topic selection applied.

        Pending selection lives beside the recipe because a disease choice can be incomplete
        (nothing checked). The result is JSON-serialisable and may not be a valid composition;
        ``pending_problem`` says so instead of hiding it.
        """
        selection = self.selection
        blocks = []
        for entry in self.included():
            changed = dict(entry)
            chosen = selection.get(entry["instance_id"])
            if chosen and entry["block"] in SELECTABLE_BLOCKS:
                topics = chosen.get("topics")
                if topics is not None:
                    changed["topics"] = list(topics)
                    presentation = dict(changed.get("presentation") or {})
                    default_topic = chosen.get("default_topic")
                    if default_topic is None:
                        # Nothing is checked: show no expanded disease rather than a stale one.
                        presentation.pop("default_topic", None)
                    else:
                        presentation["default_topic"] = default_topic
                    changed["presentation"] = presentation
            blocks.append(changed)
        return blocks

    def pending(self):
        """The composition the editor is currently describing (not necessarily renderable)."""
        return {**self.recipe, "blocks": self.pending_blocks()}

    def pending_problem(self):
        """None when the pending composition could be rendered; otherwise a structured reason."""
        blocks = self.pending_blocks()
        for entry in blocks:
            if entry["block"] in SELECTABLE_BLOCKS and entry.get("topics") == []:
                return {"kind": "empty-selection", "block": entry["block"],
                        "instance_id": entry["instance_id"],
                        "message": "Select at least one disease."}
        try:
            publish.validate_composition({**self.recipe, "blocks": blocks})
        except ValueError as error:
            return {"kind": "invalid", "message": str(error)}
        return None

    def pending_ready(self):
        return self.pending_problem() is None

    @property
    def recipe_path(self):
        return Path(self.root) / DRAFT_RECIPE


def draft_bytes(draft):
    """Canonical bytes of the last accepted, renderable recipe."""
    return recipe_bytes(draft.effective())


def draft_digest(draft):
    return hashlib.sha256(draft_bytes(draft)).hexdigest()


def pending_ready(draft):
    """True when the editor's pending composition could be rendered as it stands."""
    return draft.pending_ready()


def pending_problem(draft):
    """None, or the structured reason the pending composition cannot be rendered."""
    return draft.pending_problem()


def pending_bytes(draft):
    """Canonical bytes of the pending composition (also for a not-yet-renderable state)."""
    return recipe_bytes(draft.pending())


def pending_digest(draft):
    return hashlib.sha256(pending_bytes(draft)).hexdigest()


def _write_editor(draft_root, editor):
    payload = (json.dumps(editor, indent=2) + "\n").encode("utf-8")
    return _atomic_replace(Path(draft_root) / DRAFT_EDITOR, payload)


def _check_editor(recipe, editor):
    if not isinstance(editor, dict):
        raise WorkspaceError("Draft editor state must be an object.")
    if editor.get("schema") not in (DRAFT_SCHEMA, DRAFT_SCHEMA_V2):
        raise WorkspaceError(f"Unsupported draft state schema: {editor.get('schema')!r}")
    if editor.get("audience") != recipe["audience"]:
        raise WorkspaceError("Draft state audience does not match the saved recipe.")
    excluded = editor.get("excluded")
    if not isinstance(excluded, list) or any(not isinstance(item, str) for item in excluded):
        raise WorkspaceError("Draft exclusions must be a list of block instance ids.")
    if len(set(excluded)) != len(excluded):
        raise WorkspaceError("Draft exclusions contain a duplicate block instance id.")
    if not isinstance(editor.get("revision"), int) or editor["revision"] < 0:
        raise WorkspaceError("Draft revision must be a non-negative integer.")
    ids = [entry["instance_id"] for entry in recipe["blocks"]]
    unknown = [item for item in excluded if item not in ids]
    if unknown:
        raise WorkspaceError(f"Draft excludes blocks it does not contain: {unknown}")
    by_id = {entry["instance_id"]: entry for entry in recipe["blocks"]}
    forced = [item for item in excluded if by_id[item]["block"] in REQUIRED_BLOCKS]
    if forced:
        reasons = "; ".join(f"{item}: {REQUIRED_BLOCKS[by_id[item]['block']]}" for item in forced)
        raise WorkspaceError(f"Required section cannot be excluded. {reasons}")
    if len(excluded) >= len(ids):
        raise WorkspaceError("A composition needs at least one included section.")
    selection = editor.get("selection") or {}
    if not isinstance(selection, dict):
        raise WorkspaceError("Draft selection must be an object.")
    for instance_id, chosen in selection.items():
        if instance_id not in ids:
            raise WorkspaceError(f"Draft selection names an unknown block: {instance_id!r}")
        if not isinstance(chosen, dict) or set(chosen) - {"topics", "default_topic"}:
            raise WorkspaceError(f"Draft selection for {instance_id!r} has unsupported fields.")
        topics = chosen.get("topics")
        if topics is not None:
            if not isinstance(topics, list) or any(
                    not isinstance(topic, str) or not publish.TOPIC_ID.fullmatch(topic)
                    for topic in topics):
                raise WorkspaceError(f"Draft selection for {instance_id!r} has invalid topics.")
            if len(set(topics)) != len(topics):
                raise WorkspaceError(f"Draft selection for {instance_id!r} repeats a topic.")
        default_topic = chosen.get("default_topic")
        if default_topic is not None and (not isinstance(default_topic, str)
                                          or not publish.TOPIC_ID.fullmatch(default_topic)):
            raise WorkspaceError(
                f"Draft selection for {instance_id!r} has an invalid default topic.")
    return editor


def open_draft(root):
    """Read and validate a draft: saved recipe plus editor state, both consistent."""
    root = _real(Path(root))
    recipe_path, editor_path = root / DRAFT_RECIPE, root / DRAFT_EDITOR
    if not recipe_path.is_file() or not editor_path.is_file():
        raise WorkspaceError(f"No saved draft here: {root}")
    try:
        recipe = publish.validate_composition(
            json.loads(recipe_path.read_text(encoding="utf-8")))
    except ValueError as error:
        raise WorkspaceError(f"Draft recipe rejected by the composition loader: {error}") from None
    try:
        editor = json.loads(editor_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkspaceError(f"Draft state is not valid JSON: {root} ({error.msg})") from None
    _check_editor(recipe, editor)
    draft = Draft(root=root, recipe=recipe, editor=editor)
    try:
        draft.effective()
    except ValueError as error:
        raise WorkspaceError(f"Draft composition is not renderable: {error}") from None
    return draft


def create_draft(root, recipe_path, *, based_on=None):
    """Create a draft as a byte copy of a maintained recipe, or resume the existing one."""
    root = Path(root)
    if (root / DRAFT_EDITOR).is_file():
        return open_draft(root)
    source = Path(recipe_path)
    recipe = open_recipe(source)
    root.mkdir(parents=True, exist_ok=False)
    _atomic_new(root / DRAFT_RECIPE, source.read_bytes())
    editor = {"schema": DRAFT_SCHEMA_V2, "audience": recipe["audience"], "excluded": [],
              "selection": {}, "revision": 0, "based_on": based_on or recipe["audience"],
              "created_utc": _now(), "updated_utc": _now()}
    _atomic_new(root / DRAFT_EDITOR, (json.dumps(editor, indent=2) + "\n").encode("utf-8"))
    return open_draft(root)


def _bump(draft, *, recipe=None, excluded=None, selection=None):
    editor = dict(draft.editor)
    editor["schema"] = DRAFT_SCHEMA_V2
    if recipe is not None:
        _atomic_replace(Path(draft.root) / DRAFT_RECIPE, recipe_bytes(recipe))
    if excluded is not None:
        editor["excluded"] = list(excluded)
    if selection is not None:
        editor["selection"] = {key: dict(value) for key, value in selection.items()}
    editor["revision"] = draft.editor["revision"] + 1
    editor["updated_utc"] = _now()
    _write_editor(draft.root, editor)
    return open_draft(draft.root)


def edit_plan(draft, action, instance, value=None, option=None):
    """Validate one editor action and return the intended (recipe, excluded) without writing.

    Validation happens here, before any file is created, so a rejected action never leaves a
    half-made copy behind. ``option`` names the concrete presentation option for style/topic
    actions; the website decides which option an action maps to.
    """
    if action in ("include", "exclude"):
        entry = _entry(draft.recipe, instance)
        without = [item for item in draft.excluded if item != instance]
        if action == "include":
            return draft.recipe, without
        if entry["block"] in REQUIRED_BLOCKS:
            raise WorkspaceError(
                f"Cannot exclude {instance!r}. {REQUIRED_BLOCKS[entry['block']]}")
        if len(draft.included()) <= 1:
            raise WorkspaceError("A composition needs at least one included section.")
        return draft.recipe, without + [instance]
    if action in ("move-up", "move-down"):
        direction = action.split("-")[1]
        blocks = list(draft.recipe["blocks"])
        excluded = set(draft.excluded)
        ids = [entry["instance_id"] for entry in blocks]
        if instance not in ids:
            raise WorkspaceError(
                f"Unknown block instance {instance!r}. This recipe contains: {', '.join(ids)}")
        if instance in excluded:
            raise WorkspaceError(f"{instance!r} is not included in this composition.")
        visible = [index for index, entry in enumerate(blocks)
                   if entry["instance_id"] not in excluded]
        position = [blocks[index]["instance_id"] for index in visible].index(instance)
        target = position - 1 if direction == "up" else position + 1
        if target < 0 or target >= len(visible):
            raise WorkspaceError(
                f"Section {instance!r} is already at the "
                f"{'top' if direction == 'up' else 'bottom'}.")
        left, right = visible[position], visible[target]
        blocks[left], blocks[right] = blocks[right], blocks[left]
        return {**draft.recipe, "blocks": blocks}, list(draft.excluded)
    if option is None:
        raise WorkspaceError(f"Unknown edit action {action!r}.")
    return set_block_option(draft.recipe, instance, option, value), list(draft.excluded)


def commit_edit(draft, recipe, excluded):
    """Persist a validated edit and bump the revision; a no-op edit changes nothing."""
    if recipe == draft.recipe and sorted(excluded) == sorted(draft.excluded):
        return draft
    return _bump(draft, recipe=recipe if recipe != draft.recipe else None, excluded=excluded)


def set_inclusion(draft, instance_id, included):
    """Include or exclude one section; the section keeps its settings either way."""
    action = "include" if included else "exclude"
    recipe, excluded = edit_plan(draft, action, instance_id)
    return commit_edit(draft, recipe, excluded)


def move_included(draft, instance_id, direction):
    """Move a section relative to the other *included* sections; identity is untouched."""
    if direction not in ("up", "down"):
        raise WorkspaceError("Direction must be 'up' or 'down'.")
    recipe, excluded = edit_plan(draft, f"move-{direction}", instance_id)
    return commit_edit(draft, recipe, excluded)


def set_draft_option(draft, instance_id, option, value):
    """Set a supported presentation option on the draft's saved recipe."""
    recipe, excluded = edit_plan(draft, "set-option", instance_id, value, option=option)
    return commit_edit(draft, recipe, excluded)


def plan_selection(draft, action, instance_id, value, eligible=None):
    """Pending disease selection, kept beside the recipe because it can be incomplete.

    Returns ``(selection, note)`` without writing. ``note`` reports a default-open disease that
    had to move because it is no longer checked, so the page can announce the replacement.
    """
    entry = _entry(draft.recipe, instance_id)
    if entry["block"] not in SELECTABLE_BLOCKS:
        raise WorkspaceError(f"Section {entry['block']!r} does not take a disease selection.")
    chosen = dict(draft.selection.get(instance_id) or {})
    topics = chosen.get("topics")
    if topics is None and isinstance(entry.get("topics"), list):
        topics = list(entry["topics"])
    note = None
    if action == "set-topics":
        if not isinstance(value, list) or any(not isinstance(topic, str) for topic in value):
            raise WorkspaceError("A disease selection must be a list of saved topic ids.")
        if len(set(value)) != len(value):
            raise WorkspaceError("A disease selection must not repeat a topic.")
        if eligible is not None:
            unknown = [topic for topic in value if topic not in eligible]
            if unknown:
                raise WorkspaceError(
                    "Not included in this saved bundle: " + ", ".join(sorted(unknown)))
        previous = chosen.get("default_topic")
        if previous is None:
            previous = (entry.get("presentation") or {}).get("default_topic")
        if previous is None and isinstance(entry.get("topics"), list) and entry["topics"]:
            previous = entry["topics"][0]
        chosen["topics"] = list(value)
        if previous not in value:
            replacement = value[0] if value else None
            chosen["default_topic"] = replacement
            if previous is not None and replacement is not None:
                note = {"kind": "default-open-moved", "from": previous, "to": replacement}
            elif previous is not None:
                note = {"kind": "default-open-cleared", "from": previous}
        else:
            chosen["default_topic"] = previous
    elif action == "set-default-open":
        if not topics:
            raise WorkspaceError(
                "Choose at least one disease before setting the expanded disease.")
        if not isinstance(value, str) or value not in topics:
            raise WorkspaceError("The expanded disease must be one of the checked diseases.")
        chosen["default_topic"] = value
    else:
        raise WorkspaceError(f"Unknown selection action {action!r}.")
    selection = dict(draft.selection)
    selection[instance_id] = chosen
    return selection, note


def commit_selection(draft, selection):
    """Persist a pending selection and bump the revision."""
    return _bump(draft, selection=selection)


def commit_pending(draft, eligible):
    """Write the pending selection into the recipe, normalising a full set back to "eligible"."""
    if not draft.selection:
        return draft
    order = list(eligible or [])
    blocks = []
    for entry in draft.recipe["blocks"]:
        chosen = draft.selection.get(entry["instance_id"])
        if not chosen or entry["block"] not in SELECTABLE_BLOCKS:
            blocks.append(dict(entry))
            continue
        changed = dict(entry)
        topics = chosen.get("topics")
        if topics is not None:
            changed["topics"] = "eligible" if (order and list(topics) == order) else list(topics)
        default_topic = chosen.get("default_topic")
        if default_topic is not None:
            presentation = dict(changed.get("presentation") or {})
            presentation["default_topic"] = default_topic
            changed["presentation"] = presentation
        blocks.append(changed)
    editor = {**draft.editor, "schema": DRAFT_SCHEMA_V2, "selection": {},
              "revision": draft.editor["revision"] + 1, "updated_utc": _now()}
    _atomic_replace(Path(draft.root) / DRAFT_RECIPE,
                    recipe_bytes({**draft.recipe, "blocks": blocks}))
    _write_editor(draft.root, editor)
    return open_draft(draft.root)


def reset_draft(draft, recipe_path, *, based_on=None):
    """Restore the copy to its maintained default in place; generated reports are untouched."""
    source = Path(recipe_path)
    recipe = open_recipe(source)
    if recipe["audience"] != draft.audience:
        raise WorkspaceError("Reset source belongs to a different audience.")
    _atomic_replace(Path(draft.root) / DRAFT_RECIPE, source.read_bytes())
    editor = {"schema": DRAFT_SCHEMA_V2, "audience": recipe["audience"], "excluded": [],
              "selection": {}, "revision": draft.editor["revision"] + 1,
              "based_on": based_on or recipe["audience"],
              "created_utc": draft.editor.get("created_utc") or _now(),
              "updated_utc": _now()}
    _write_editor(draft.root, editor)
    return open_draft(draft.root)
