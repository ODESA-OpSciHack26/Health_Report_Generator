"""Block library for the Custom composition mode.

One inventory of every block type ``publish.validate_composition`` accepts, together with the
builder that decides whether a *given retained bundle* can actually produce it, the option
domain that bundle offers, and the allocation of stable per-draft instance ids.

Nothing here validates a composition, recalculates a value or invents a block: the loader and
the block builders stay the only authorities. ``inspect`` merely calls those builders against
saved records and reports what they said, so availability is a builder prerequisite and not a
file-existence guess.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import threading
from pathlib import Path

import publish

BLOCK_ORDER = ("intro", "series-trend", "series-collection", "reference-comparison",
               "coverage-selection", "monitoring-overview", "sensitivity-comparison",
               "limitations", "reproduction",
               "data-overview", "values-by-group", "values-over-time", "coverage-over-time",
               "data-quality")

# Reader-facing library. ``options`` is the closed set of recipe fields this block accepts in
# addition to block/instance_id; ``requires`` lists the options a valid entry must carry.
# ``repeatable`` is False both where the loader refuses a second instance and where a second
# identical section would only repeat content (says which, in ``repeat_reason``).
LIBRARY = {
    "intro": {
        "label": "Introduction",
        "description": "What data, question and scope this report covers.",
        "purpose": "States the saved scope so a finding is never read without it.",
        "options": (),
        "requires": (),
        "repeatable": False,
        "repeat_reason": "This section has no per-instance settings; a second copy would "
                         "repeat the same text.",
    },
    "series-trend": {
        "composable": False,          # supported contract, not offered as a new section
        "label": "Annual trend for one disease",
        "description": "One saved annual series with its exact recorded values.",
        "purpose": "Shows what happened across the saved periods for a single disease.",
        "options": ("topic", "measure", "years", "presentation.style"),
        "requires": ("topic", "measure"),
        "repeatable": False,
        "repeat_reason": "The composition contract allows one single-disease trend per report.",
    },
    "series-collection": {
        "composable": True,
        "label": "Annual trends by disease",
        "description": "One or more checked diseases, each with its saved annual values and "
                       "an exact-value table.",
        "purpose": "Shows the saved series for several diseases side by side, each on its own.",
        "options": ("topics", "measure", "years", "presentation.style",
                    "presentation.default_topic", "presentation.layout"),
        "requires": ("measure",),
        "repeatable": True,
        "repeat_reason": None,
    },
    "reference-comparison": {
        "label": "Change from the reference period",
        "description": "One saved change against the reference year.",
        "purpose": "The primary quantitative block: saved subject, counts and percentage.",
        "options": ("topic",),
        "requires": ("topic",),
        "repeatable": False,
        "repeat_reason": "One saved reference result can be bound to one instance only; the "
                         "contract refuses repeated comparison blocks.",
    },
    "coverage-selection": {
        "label": "Data coverage and included observations",
        "description": "What the saved selection covers, and what it leaves out.",
        "purpose": "Requested, eligible and displayed records, from saved selection decisions.",
        "options": (),
        "requires": (),
        "repeatable": True,
        "repeat_reason": None,
    },
    "monitoring-overview": {
        "label": "Latest observations by disease",
        "description": "The latest saved value and comparison per disease.",
        "purpose": "A descriptive row per included disease; no score, ranking or threshold.",
        "options": (),
        "requires": (),
        "repeatable": True,
        "repeat_reason": None,
    },
    "sensitivity-comparison": {
        "label": "Comparison across analysis choices",
        "description": "Saved main versus sensitivity group results.",
        "purpose": "Shows how far the saved comparison depends on a recorded analytical choice.",
        "options": (),
        "requires": (),
        "repeatable": True,
        "repeat_reason": None,
    },
    "limitations": {
        "label": "Limitations and cautions",
        "description": "What this report cannot support.",
        "purpose": "Required reading beside any finding.",
        "options": (),
        "requires": (),
        "repeatable": False,
        "repeat_reason": "Required and single: a second copy would repeat the same cautions.",
    },
    "reproduction": {
        "label": "Reproduction and evidence",
        "description": "How to check the published files and rerun the render.",
        "purpose": "Required: readers must be able to reach the evidence and the replay.",
        "options": (),
        "requires": (),
        "repeatable": False,
        "repeat_reason": "Required and single: a second copy would repeat the same record.",
    },
    # Neutral CSV block types: registered for the shared validator and label source, but never
    # offered by the health library (composable=False); the neutral library owns them.
    "data-overview": {
        "composable": False,
        "label": "Dataset overview",
        "description": "Record and field counts and the actual selected coverage.",
        "purpose": "What the captured dataset contains and covers.",
        "options": (),
        "requires": (),
        "repeatable": False,
        "repeat_reason": "One overview per dataset; a second copy would repeat the same counts.",
    },
    "values-by-group": {
        "composable": False,
        "label": "Values by group",
        "description": "Observed values per group, with the group's descriptive summary.",
        "purpose": "Descriptive values per confirmed group; no pooling.",
        "options": (),
        "requires": (),
        "repeatable": True,
        "repeat_reason": None,
    },
    "values-over-time": {
        "composable": False,
        "label": "Values over time",
        "description": "Observed values per selected period; gaps and duplicates stay visible.",
        "purpose": "Time course from the confirmed time column.",
        "options": ("time_period",),
        "requires": (),
        "repeatable": True,
        "repeat_reason": None,
    },
    "coverage-over-time": {
        "composable": False,
        "label": "Observation coverage over time",
        "description": "Which groups have a recorded observation in each period; values not shown.",
        "purpose": "Explicitly named availability view; never a substitute for the numerical series.",
        "options": ("time_period",),
        "requires": (),
        "repeatable": True,
        "repeat_reason": None,
    },
    "data-quality": {
        "composable": False,
        "label": "Data quality and completeness",
        "description": "Missingness, invalid handling, repeated keys and diagnostic limits.",
        "purpose": "Completeness context for every displayed value.",
        "options": (),
        "requires": (),
        "repeatable": False,
        "repeat_reason": "One quality statement per dataset.",
    },
}

# Instance ids stay short, readable and unique. The numeric suffix is allocated from the draft's
# monotonic counter, never from a random value, so a reopened draft explains every id.
SLUGS = {"intro": "intro", "series-trend": "trend", "series-collection": "collection",
         "reference-comparison": "reference", "coverage-selection": "coverage",
         "monitoring-overview": "monitoring", "sensitivity-comparison": "sensitivity",
         "limitations": "limitations", "reproduction": "reproduction",
         "data-overview": "overview", "values-by-group": "values-by-group",
         "values-over-time": "values-over-time", "coverage-over-time": "coverage-over-time",
         "data-quality": "quality"}

# Sections the product requires in every report. Mirrors composer_workspace.REQUIRED_BLOCKS;
# kept here so the library can describe the floor without importing the draft service.
REQUIRED = ("limitations", "reproduction")

TOPIC_ID = publish.TOPIC_ID
MEASURE_ID = publish.MEASURE_ID
INSTANCE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{2,39}")

# Reader-facing names for saved topic ids. The canonical id stays the only analytical input;
# these are display labels only and never reach a recipe, a binding or an identity.
DISPLAY_LABELS = {
    "aids": "AIDS",
    "campylobacteriosis": "Campylobacteriosis",
    "chlamydiosis": "Chlamydia",
    "ehec": "EHEC",
    "gonorrhea": "Gonorrhoea",
    "hepatitis_a": "Hepatitis A",
    "hepatitis_b": "Hepatitis B",
    "hepatitis_c": "Hepatitis C",
    "hepatitis_e": "Hepatitis E",
    "hiv": "HIV",
    "influenza": "Influenza",
    "shigellosis": "Shigellosis",
}

LABEL_FILE = Path(__file__).resolve().parent / "config" / "composer" / "block-labels.json"

_CACHE: dict = {}
_LOCK = threading.RLock()


class LibraryError(ValueError):
    """A user-actionable library error; safe to show in the local UI."""


# --------------------------------------------------------------------------- labels

def load_block_labels(path=None):
    """The single reader-facing name/description source for every registered block type.

    Both the composer (here) and the R renderer read this file, so a block is called the same
    thing in the library, the editor, the report heading and the report navigation. Canonical
    block ids, recipe fields and analytical inputs are never derived from it.
    """
    target = Path(path or LABEL_FILE)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LibraryError(f"Block labels are unavailable ({target}): {error}") from None
    blocks = payload.get("blocks") if isinstance(payload, dict) else None
    if not isinstance(blocks, dict):
        raise LibraryError(f"Block labels are malformed: {target}")
    missing = [block for block in BLOCK_ORDER if block not in blocks]
    if missing:
        raise LibraryError(f"Block labels are missing entries for {missing}: {target}")
    labels = {}
    for block, entry in blocks.items():
        if block not in LIBRARY:
            raise LibraryError(f"Block labels name an unregistered block {block!r}: {target}")
        name = (entry or {}).get("name")
        description = (entry or {}).get("description")
        if not isinstance(name, str) or not name.strip():
            raise LibraryError(f"Block label for {block!r} has no name: {target}")
        labels[block] = {"name": name.strip(),
                         "description": (description or "").strip()}
    return labels


def apply_block_labels(labels=None):
    """Overwrite every library label/description from the shared file (idempotent)."""
    resolved = labels or load_block_labels()
    for block, entry in resolved.items():
        LIBRARY[block]["label"] = entry["name"]
        LIBRARY[block]["description"] = entry["description"]
    return resolved


BLOCK_LABELS = apply_block_labels()


# --------------------------------------------------------------------------- inventory

def entry_for(block):
    if block not in LIBRARY:
        raise LibraryError(f"Unknown block type: {block!r}")
    return LIBRARY[block]


def display_label(topic):
    """Reader-facing label for a saved topic id; the id itself when nothing is curated."""
    return DISPLAY_LABELS.get(topic, topic)


def bundle_topic_labels(bundle):
    """Labels recorded in the saved bundle's own series rows (they are the report's labels)."""
    labels = {}
    path = Path(bundle) / "series.csv"
    if path.is_file():
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    topic = (row.get("topic") or "").strip()
                    label = (row.get("label") or "").strip()
                    if topic and label and topic not in labels:
                        labels[topic] = label
        except OSError:
            return {}
    return labels


def topic_labels(topics, bundle=None):
    """Ordered ``{id: label}`` map: the bundle's recorded label first, then the shared map."""
    recorded = bundle_topic_labels(bundle) if bundle else {}
    return {topic: recorded.get(topic) or display_label(topic) for topic in topics}


def summary_topics(labels, limit=3):
    """Compact disease list for a summary: 'A, B and C' or 'A, B, C and 9 more'."""
    labels = [label for label in labels if label]
    if not labels:
        return None
    if len(labels) == 1:
        return labels[0]
    if len(labels) <= limit:
        return ", ".join(labels[:-1]) + " and " + labels[-1]
    return ", ".join(labels[:limit]) + f" and {len(labels) - limit} more"


def composable_blocks():
    """Block types the composer offers as a new section, in reading order."""
    return tuple(block for block in BLOCK_ORDER if LIBRARY[block].get("composable", True))


def inventory():
    """The library the editor offers: composable types only, in reading order.

    ``series-trend`` remains a registered, validated contract (historical recipes, evidence and
    CLI replay keep working) but is no longer offered as a new section; ``LIBRARY`` still describes
    it so an existing instance renders and can be edited.
    """
    items = []
    for block in composable_blocks():
        spec = LIBRARY[block]
        items.append({"block": block, "label": spec["label"],
                      "description": spec["description"], "purpose": spec["purpose"],
                      "options": list(spec["options"]), "requires": list(spec["requires"]),
                      "required": block in REQUIRED,
                      "repeatable": spec["repeatable"],
                      "repeat_reason": spec["repeat_reason"]})
    return items


def coerce_option(block, option, value):
    """Validate and normalise one option value for ``block``. Types only; no bundle access."""
    spec = entry_for(block)
    if option not in spec["options"]:
        raise LibraryError(f"{spec['label']} does not take {option!r}. "
                           f"Supported options: {', '.join(spec['options']) or 'none'}.")
    if option == "years":
        if value is None or value == "":
            return None
        if (not isinstance(value, list) or len(value) != 2
                or any(isinstance(item, bool) or not isinstance(item, int) for item in value)):
            raise LibraryError("A year range must be two whole years, start then end.")
        if value[0] > value[1]:
            raise LibraryError("The year range starts after it ends.")
        return [int(value[0]), int(value[1])]
    if option == "topics":
        if value == "eligible":
            return "eligible"
        if (not isinstance(value, list) or not value
                or any(not isinstance(item, str) or not TOPIC_ID.fullmatch(item)
                       for item in value)):
            raise LibraryError("Choose at least one saved disease, or use all eligible ones.")
        if len(set(value)) != len(value):
            raise LibraryError("A disease selection must not repeat a disease.")
        return list(value)
    if option in ("topic", "measure"):
        pattern = TOPIC_ID if option == "topic" else MEASURE_ID
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise LibraryError(f"Invalid {option}: {value!r}")
        return value
    if option == "presentation.layout":
        if value not in publish.COLLECTION_LAYOUTS:
            raise LibraryError(f"Unsupported chart layout {value!r}; choose one of "
                               f"{list(publish.COLLECTION_LAYOUTS)}.")
        return value
    if option == "presentation.style":
        if value not in publish.SERIES_STYLES:
            raise LibraryError(f"Unsupported style {value!r}; choose one of "
                               f"{list(publish.SERIES_STYLES)}.")
        return value
    if option == "presentation.default_topic":
        if not isinstance(value, str) or not TOPIC_ID.fullmatch(value):
            raise LibraryError(f"Invalid expanded disease: {value!r}")
        return value
    raise LibraryError(f"Unsupported option {option!r}.")


def build_entry(block, options=None):
    """A recipe entry (without instance id) from option values, typed and checked."""
    entry = {"block": block}
    for option, value in (options or {}).items():
        coerced = coerce_option(block, option, value)
        if coerced is None:
            continue
        if option.startswith("presentation."):
            presentation = dict(entry.get("presentation") or {})
            presentation[option.split(".", 1)[1]] = coerced
            entry["presentation"] = presentation
        else:
            entry[option] = coerced
    if block == "series-collection":
        # The contract requires an explicit topics value; "all eligible saved diseases" is the
        # bundle-backed default and is stated as such in the editor.
        entry.setdefault("topics", "eligible")
        # A collection created in this workbench starts in the combined layout. Historical
        # recipes and records without a layout keep the panels behaviour.
        if "presentation.layout" not in (options or {}):
            presentation = dict(entry.get("presentation") or {})
            presentation["layout"] = "combined"
            entry["presentation"] = presentation
    return entry


def entry_problem(entry):
    """Why a library entry cannot be part of a composition yet, or None when it can."""
    block = entry.get("block")
    if block not in LIBRARY:
        return f"Unknown block type: {block!r}"
    spec = LIBRARY[block]
    missing = [name for name in spec["requires"] if name not in entry]
    if missing:
        words = {"topic": "a disease", "measure": "a measure"}
        return ("Choose " + " and ".join(words.get(name) or name for name in missing)
                + f" before adding {spec['label'].lower()}.")
    if block == "series-collection":
        topics = entry.get("topics", "eligible")
        if topics == []:
            return "Choose at least one disease for the trends collection."
        if isinstance(topics, list) and not topics:
            return "Choose at least one disease for the trends collection."
    return None


def combination_conflict(blocks, block):
    """Why ``block`` cannot join ``blocks`` without an explicit replacement, or None.

    Two different restrictions are reported the same way on purpose: the reader sees the
    reason and an explicit choice, never a silent removal.
    """
    spec = LIBRARY.get(block)
    if spec is None:
        raise LibraryError(f"Unknown block type: {block!r}")
    same = [entry["instance_id"] for entry in blocks if entry["block"] == block]
    if same and not spec["repeatable"]:
        return {"kind": "singleton", "block": block, "instances": same,
                "reason": spec["repeat_reason"]}
    if block == "series-trend":
        collections = [entry["instance_id"] for entry in blocks
                       if entry["block"] == "series-collection"]
        if collections:
            return {"kind": "combination", "block": block, "instances": collections,
                    "reason": "A report cannot combine a single-disease trend with the "
                              "multi-disease trends collection."}
    if block == "series-collection":
        trends = [entry["instance_id"] for entry in blocks if entry["block"] == "series-trend"]
        if trends:
            return {"kind": "combination", "block": block, "instances": trends,
                    "reason": "A report cannot combine the multi-disease trends collection "
                              "with a single-disease trend."}
    return None


def allocate(block, taken, seq):
    """Next stable instance id for ``block``; never reuses an id in ``taken``."""
    slug = SLUGS[block]
    attempt = int(seq or 0)
    while True:
        attempt += 1
        candidate = f"c-{slug}-{attempt:04d}"
        if not INSTANCE_ID.fullmatch(candidate):
            raise LibraryError(f"Could not allocate a valid instance id for {block!r}.")
        if candidate not in taken:
            return candidate, attempt


def last_seq(*recipes):
    """Highest numeric suffix already used by any instance id in these recipes."""
    highest = 0
    for recipe in recipes:
        for entry in (recipe or {}).get("blocks") or []:
            match = re.search(r"-(\d{4})$", entry.get("instance_id") or "")
            if match:
                highest = max(highest, int(match.group(1)))
    return highest


def initial_recipe(audience, start=0, taken=()):
    """The minimal valid Custom composition: the evidence floor, and nothing else.

    ``intro`` + ``limitations`` + ``reproduction`` is valid for every retained bundle (they are
    presentational and read only saved scope/provenance), keeps the mandatory limitations and
    reproduction sections, and deliberately differs from every maintained audience preset, so a
    Custom report is never a copy of an audience's preset.
    """
    blocks = []
    seq = int(start or 0)
    used = set(taken)
    for block in ("intro", "limitations", "reproduction"):
        instance, seq = allocate(block, used, seq)
        used.add(instance)
        blocks.append({"block": block, "instance_id": instance})
    return {"contract": publish.COMPOSITION_CONTRACT_V2, "audience": audience,
            "blocks": blocks}


# --------------------------------------------------------------------------- capability

_CONTEXT_CACHE: dict = {}


def bundle_context(bundle):
    """Cheap, cached facts used for display summaries (no builder probes)."""
    bundle = Path(bundle)
    key = (str(bundle.resolve()), _signature(bundle))
    with _LOCK:
        cached = _CONTEXT_CACHE.get(key)
    if cached is not None:
        return cached
    stakeholder = json.loads((bundle / "stakeholder.json").read_text(encoding="utf-8"))
    selection = _rows(bundle / "selection.csv")
    included = []
    for row in selection:
        if (row.get("status") or "").strip().lower() != "included":
            continue
        topic = (row.get("topic") or "").strip()
        if topic and topic not in included:
            included.append(topic)
    document = {"included_topics": included,
                "years_window": list(stakeholder.get("years") or []),
                "reference_year": stakeholder.get("reference_year"),
                "geography": stakeholder.get("geography"),
                "topic_labels": topic_labels(included, bundle),
                "datasets": {"total": len(selection),
                             "included": sum(1 for row in selection
                                             if (row.get("status") or "").strip().lower()
                                             == "included"),
                             "excluded": sum(1 for row in selection
                                             if (row.get("status") or "").strip().lower()
                                             == "excluded")}}
    with _LOCK:
        _CONTEXT_CACHE[key] = document
    return document


def inspect(bundle, data_root, project_root=None):
    """What this saved bundle can actually build. Cached per bundle content, read-only."""
    bundle = Path(bundle)
    data_root = Path(data_root)
    key = (str(bundle.resolve()), _signature(bundle))
    with _LOCK:
        cached = _CACHE.get(key)
    if cached is not None:
        return cached
    document = _inspect(bundle, data_root, project_root or publish.PROJECT)
    with _LOCK:
        _CACHE[key] = document
    return document


def clear_cache():
    with _LOCK:
        _CACHE.clear()


def _signature(bundle):
    parts = []
    for name in ("bundle.json", "stakeholder.json", "selection.csv", "series.csv",
                 "metrics.csv", "sources.csv", "checks.csv"):
        path = Path(bundle) / name
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            digest = "-"
        parts.append(f"{name}:{digest}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _rows(path):
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _trim(text, limit=240):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _probe(builder):
    """Run one real builder; return (record or None, reason or None)."""
    try:
        record = builder()
    except Exception as error:                      # noqa: BLE001 - reported, never raised
        return None, _trim(f"{type(error).__name__}: {error}")
    if record.get("status") == "verified":
        return record, None
    detail = record.get("detail") or record.get("code") or "the saved records did not verify"
    return record, _trim(detail)


# Short, honest reasons for the builder failures a reader can act on. Anything else falls back
# to the builder's own message instead of a generic apology.
FRIENDLY = {
    "coverage-selection": {
        "artifact": "The saved bundle is missing its selection, source or series records.",
        "selection": "The saved selection record lists no included dataset.",
        "digest_disagreement": "A saved record no longer matches the bundle manifest.",
    },
    "monitoring-overview": {
        "selection": "The saved selection lists no included disease.",
        "measure_ambiguous": "A disease has more than one saved measure; no row is invented.",
    },
    "sensitivity-comparison": {
        "selection": "The saved bundle records no main/sensitivity specification pair.",
        "measure_ambiguous": "The saved sensitivity specifications are ambiguous.",
    },
}


def _reason(block, record, detail):
    code = (record or {}).get("code")
    friendly = (FRIENDLY.get(block) or {}).get(code) if isinstance(code, str) else None
    return friendly or detail or "The saved records do not support this section."


def _inspect(bundle, data_root, project_root):
    stakeholder_path = bundle / "stakeholder.json"
    manifest_path = bundle / "bundle.json"
    if not stakeholder_path.is_file() or not manifest_path.is_file():
        raise LibraryError(f"No saved bundle here: {bundle}")
    stakeholder = json.loads(stakeholder_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files") or {}
    missing = sorted(name for name in files if not (bundle / name).is_file())

    selection = _rows(bundle / "selection.csv")
    datasets = {"total": len(selection),
                "included": sum(1 for row in selection
                                if (row.get("status") or "").strip().lower() == "included"),
                "excluded": sum(1 for row in selection
                                if (row.get("status") or "").strip().lower() == "excluded")}
    included = []
    for row in selection:
        if (row.get("status") or "").strip().lower() != "included":
            continue
        topic = (row.get("topic") or "").strip()
        if topic and topic not in included:
            included.append(topic)

    series = _rows(bundle / "series.csv")
    measures = []
    present = {}
    for row in series:
        measure = (row.get("measure") or "").strip()
        topic = (row.get("topic") or "").strip()
        if not measure or not topic:
            continue
        if measure not in measures:
            measures.append(measure)
        bucket = present.setdefault(measure, [])
        if topic not in bucket:
            bucket.append(topic)

    document = {"audience": stakeholder.get("id"),
                "snapshot_id": manifest.get("snapshot_id"),
                "title": stakeholder.get("title"),
                "included_topics": included,
                "datasets": datasets,
                "measures": measures,
                "years_window": list(stakeholder.get("years") or []),
                "missing_artifacts": missing,
                "topics_by_measure": {},
                "reference_topics": [],
                "blocks": {}}

    def record(name, available, reason=None, **extra):
        document["blocks"][name] = {"available": bool(available), "reason": reason, **extra}

    incomplete = (f"The saved bundle is missing {', '.join(missing)}."
                  if missing else None)
    for name in ("intro", "limitations", "reproduction"):
        record(name, incomplete is None, incomplete)

    if incomplete:
        for name in ("series-trend", "series-collection", "reference-comparison",
                     "coverage-selection", "monitoring-overview",
                     "sensitivity-comparison"):
            record(name, False, incomplete)
        return document

    # Annual series: verify every included disease the saved rows mention, per measure.
    first_reason = None
    for measure in measures:
        verified = []
        for topic in [item for item in present.get(measure, []) if item in included]:
            _record, problem = _probe(lambda t=topic, m=measure: publish.build_series_block(
                bundle, project_root, "probe-series", t, m))
            if problem is None:
                verified.append(topic)
            elif first_reason is None:
                first_reason = problem
        if verified:
            document["topics_by_measure"][measure] = verified
    series_reason = (None if document["topics_by_measure"] else
                     _reason("series-trend", None,
                             first_reason or "The saved bundle has no annual series rows "
                                             "for an included disease."))
    record("series-trend", bool(document["topics_by_measure"]), series_reason,
           measures=[m for m in measures if document["topics_by_measure"].get(m)])

    collection = None
    for measure in measures:
        verified = document["topics_by_measure"].get(measure) or []
        for topics_mode in ("eligible", verified):
            if not topics_mode:
                continue
            _record, problem = _probe(lambda m=measure, t=topics_mode:
                                      publish.build_series_collection(
                                          bundle, project_root, "probe-collection", t, m))
            if problem is None:
                collection = {"measure": measure,
                              "topics": topics_mode if topics_mode != verified else verified}
                break
        if collection:
            break
    record("series-collection", collection is not None,
           None if collection else _reason(
               "series-collection", None,
               first_reason or "The saved bundle has no annual series rows to collect."),
           measure=(collection or {}).get("measure"), topics=(collection or {}).get("topics"))

    reference_reason = None
    for topic in included:
        _record, problem = _probe(lambda t=topic: publish.build_block(
            bundle, data_root, project_root, "probe-reference", t))
        if problem is None:
            document["reference_topics"].append(topic)
        elif reference_reason is None:
            reference_reason = problem
    record("reference-comparison", bool(document["reference_topics"]),
           None if document["reference_topics"] else _reason(
               "reference-comparison", None,
               reference_reason or "The saved bundle records no reference change for an "
                                   "included disease."),
           topics=list(document["reference_topics"]))

    for name, builder in (
            ("coverage-selection",
             lambda group: publish.build_coverage_block(bundle, project_root,
                                                        "probe-coverage", included, group)),
            ("monitoring-overview",
             lambda group: publish.build_monitoring_block(bundle, project_root,
                                                          "probe-monitoring")),
            ("sensitivity-comparison",
             lambda group: publish.build_sensitivity_block(bundle, project_root,
                                                           "probe-sensitivity"))):
        record_value, problem = _probe(lambda b=builder: b(False))
        if problem is not None and name == "coverage-selection":
            # The coverage block states whether a sensitivity block is present; accept either.
            record_value, problem = _probe(lambda: builder(True))
        record(name, problem is None, None if problem is None else _reason(name, record_value,
                                                                           problem))
    return document
