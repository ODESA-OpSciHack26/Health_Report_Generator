"""Neutral "Your CSV" block vocabulary and composition helpers.

The neutral block vocabulary is a separate registry from the health library on purpose:
generic blocks must never inherit disease semantics, and neutral ids must never alias
health stakeholder ids. The composition recipe schema is shared (composition-recipe/2);
only the allowed block vocabulary and the audience binding differ.
"""
from __future__ import annotations

import re

import neutral_display

NEUTRAL_AUDIENCE = "neutral-overview"         # Slice B delivers one neutral Overview profile.

_INSTANCE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,39}$")

# Block type -> allowed recipe fields (in addition to block/instance_id) and repeatability.
NEUTRAL_BLOCKS = {
    "intro": {"fields": frozenset(), "repeatable": False,
              "label": "Report context",
              "repeat_reason": "One context statement per dataset; a second copy would "
                               "repeat the same passport."},
    "data-overview": {"fields": frozenset(), "repeatable": False,
                      "label": "Dataset overview",
                      "repeat_reason": "One overview per dataset; a second copy would repeat the same counts.",
                      },
    "values-by-group": {"fields": frozenset({"display"}), "repeatable": True,
                        "label": "Values by group", "repeat_reason": None},
    "values-over-time": {"fields": frozenset({"time_period", "display"}), "repeatable": True,
                         "label": "Values over time", "repeat_reason": None},
    # Availability-only view. It exists as its own named block so a package that shows only
    # "observed / missing" can never be mistaken for the promised numerical report.
    "coverage-over-time": {"fields": frozenset({"time_period", "display"}), "repeatable": True,
                           "label": "Observation coverage over time", "repeat_reason": None},
    "data-quality": {"fields": frozenset(), "repeatable": False,
                     "label": "Data quality and completeness",
                     "repeat_reason": "One quality statement per dataset; a second copy "
                                      "would repeat the same records."},
    "limitations": {"fields": frozenset(), "repeatable": False,
                    "label": "Limitations and cautions",
                    "repeat_reason": "Required and single: a second copy would repeat the "
                                     "same cautions."},
    "reproduction": {"fields": frozenset(), "repeatable": False,
                     "label": "Reproduction and evidence",
                     "repeat_reason": "Required and single: a second copy would repeat the "
                                      "same record."},
}

REQUIRED = ("limitations",)                   # every report states its limitations
TIME_PERIODS = ("year", "month", "week", "day")

# Block order in the editor and in the default recipe: reading order for a neutral report.
BLOCK_ORDER = ("intro", "data-overview", "values-by-group", "values-over-time",
               "coverage-over-time", "data-quality", "limitations", "reproduction")

# ------------------------------------------------------------------ disclosure policy
# The disclosure choice is part of the recipe, not a renderer switch: a saved request must
# replay to the same package, so the policy travels with the frozen composition.
DISCLOSURE_SCHEMA = "health-report/neutral-disclosure/1"

DISCLOSURE_POLICIES = {
    "local-audit": {
        "label": "Local audit and review output",
        "summary": "Embeds the observed numerical values, descriptive statistics, charts and "
                   "the contributing records you choose to include.",
        "detail": "This package is built for local checking by the steward. It is not private "
                  "once you share or move it: the HTML, its embedded chart images and the "
                  "downloadable records all carry the observed values. Uploaded data that "
                  "looks health-related stays generic here and is not automatically safe to "
                  "disclose, whatever it is called.",
        "permits_values": True,
        "permits_records": True,
    },
    "restricted-share": {
        "label": "Restricted shareable export",
        "summary": "Excludes observed values, descriptive statistics and contributing "
                   "records; keeps counts, labels, groups and periods.",
        "detail": "Withheld values do not make this anonymous or universally safe. Counts, "
                  "group names, period labels and dataset metadata can still disclose "
                  "information, and a small group count can imply a value. Check the package "
                  "before sharing it outside the review.",
        "permits_values": False,
        "permits_records": False,
    },
}

# Blocks whose content is the observed numbers themselves. They cannot be published under a
# policy that withholds values; the availability-only block is the explicit alternative.
VALUE_BLOCKS = ("values-by-group", "values-over-time")

DEFAULT_RECIPE = {
    "contract": "health-report/composition-recipe/2",
    "audience": NEUTRAL_AUDIENCE,
    "blocks": [
        {"block": "intro", "instance_id": "intro-0001"},
        {"block": "data-overview", "instance_id": "csv-data-overview"},
        {"block": "values-by-group", "instance_id": "csv-values-by-group"},
        {"block": "data-quality", "instance_id": "csv-data-quality"},
        {"block": "limitations", "instance_id": "limitations-0001"},
        {"block": "reproduction", "instance_id": "reproduction-0001"},
    ],
}


class NeutralLibraryError(ValueError):
    """A rejected neutral composition entry; message is reader-facing."""


def inventory():
    return [
        {"block": block, "label": spec["label"],
         "description": _DESCRIPTIONS[block],
         "requires": sorted(spec["fields"]),
         "required": block in REQUIRED,
         "repeatable": spec["repeatable"],
         "repeat_reason": (None if spec["repeatable"] else
                           "This section is a single scope statement for the dataset."),
         "options": sorted(spec["fields"])}
        for block in BLOCK_ORDER
        for spec in [NEUTRAL_BLOCKS[block]]
    ]


_DESCRIPTIONS = {
    "intro": "What dataset, question and scope this report covers.",
    "data-overview": "Record and field counts and the actual selected coverage.",
    "values-by-group": "Observed values per group, with the group's descriptive summary.",
    "values-over-time": "Observed values per selected period; gaps and duplicates stay visible.",
    "coverage-over-time": "Which groups have an observation in each period, without the values.",
    "data-quality": "Missingness, invalid handling, repeated keys and diagnostic limits.",
    "limitations": "What this report cannot support.",
    "reproduction": "How to check the published files and rerun the render.",
}


def validate_recipe(recipe) -> dict:
    """Shared neutral composition validator mirroring publish.validate_composition.

    Kept separate so health block vocabulary can never leak into neutral recipes; the
    schema (composition-recipe/2) and the instance-id rules are the same.
    """
    if not isinstance(recipe, dict):
        raise NeutralLibraryError("Composition recipe must be an object.")
    unknown = set(recipe) - {"contract", "audience", "titles", "blocks", "disclosure"}
    if unknown:
        raise NeutralLibraryError(
            "Unsupported composition fields: " + ", ".join(sorted(unknown)))
    if recipe.get("contract") != "health-report/composition-recipe/2":
        raise NeutralLibraryError("Neutral recipes require composition-recipe/2.")
    if recipe.get("audience") != NEUTRAL_AUDIENCE:
        raise NeutralLibraryError(
            f"Neutral recipes bind audience {NEUTRAL_AUDIENCE!r}; got "
            f"{recipe.get('audience')!r}.")
    blocks = recipe.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise NeutralLibraryError("Composition recipe needs a non-empty blocks list.")
    seen = set()
    for entry in blocks:
        if not isinstance(entry, dict) or "block" not in entry or "instance_id" not in entry:
            raise NeutralLibraryError("Each block needs block and instance_id.")
        block, instance = entry["block"], entry["instance_id"]
        if block not in NEUTRAL_BLOCKS:
            raise NeutralLibraryError(f"Unknown block type for a neutral report: {block!r}.")
        spec = NEUTRAL_BLOCKS[block]
        required = set(spec["fields"]) - {"display"}
        expected = {"block", "instance_id"} | required
        optional = {"display"} if "display" in spec["fields"] else set()
        if not expected <= set(entry) <= (expected | optional):
            raise NeutralLibraryError(
                f"Invalid fields for block {block!r}: expected {sorted(expected)} "
                f"with optional {sorted(optional)}.")
        if not _INSTANCE_ID.fullmatch(instance):
            raise NeutralLibraryError(f"Invalid block instance id: {instance!r}.")
        if instance in seen:
            raise NeutralLibraryError(f"Duplicate block instance id: {instance!r}.")
        seen.add(instance)
        if block in ("values-over-time", "coverage-over-time"):
            period = entry.get("time_period")
            if period not in TIME_PERIODS:
                raise NeutralLibraryError(
                    f"{block} needs time_period in {TIME_PERIODS!r}.")
    if "disclosure" in recipe:
        validate_disclosure(recipe["disclosure"])
    for entry in blocks:
        if "display" in entry:
            try:
                neutral_display.validate(entry["block"], entry["display"])
            except neutral_display.DisplayError as error:
                raise NeutralLibraryError(
                    f"Invalid display settings for {entry['instance_id']!r}: {error}") from None
    present = {entry["block"] for entry in blocks}
    missing = [block for block in REQUIRED if block not in present]
    if missing:
        raise NeutralLibraryError(
            "Every neutral report states its limitations: the "
            + ", ".join(missing) + " section cannot be removed.")
    return recipe


def validate_disclosure(disclosure) -> dict:
    """Validate the explicit disclosure choice carried by a neutral recipe.

    The policy is never repaired: a mismatched flag is rejected with a reader-facing message
    so a caller cannot ask for "restricted" output that still embeds values.
    """
    if not isinstance(disclosure, dict):
        raise NeutralLibraryError("The disclosure choice must be an object.")
    unknown = set(disclosure) - {"schema", "policy", "permit_values", "permit_records"}
    if unknown:
        raise NeutralLibraryError(
            "Unsupported disclosure fields: " + ", ".join(sorted(unknown)))
    if "schema" in disclosure and disclosure["schema"] != DISCLOSURE_SCHEMA:
        raise NeutralLibraryError(f"Unsupported disclosure schema: {disclosure['schema']!r}.")
    policy = disclosure.get("policy")
    if policy not in DISCLOSURE_POLICIES:
        raise NeutralLibraryError(
            "Choose a disclosure policy from " + ", ".join(sorted(DISCLOSURE_POLICIES))
            + f"; got {policy!r}.")
    spec = DISCLOSURE_POLICIES[policy]
    permit_values = disclosure.get("permit_values")
    permit_records = disclosure.get("permit_records")
    if not isinstance(permit_values, bool) or not isinstance(permit_records, bool):
        raise NeutralLibraryError(
            "The disclosure choice must state permit_values and permit_records as booleans.")
    if policy == "restricted-share" and (permit_values or permit_records):
        raise NeutralLibraryError(
            "The restricted shareable export cannot include observed values or contributing "
            "records. Choose the local audit policy for that output.")
    if policy == "local-audit" and not permit_values:
        raise NeutralLibraryError(
            "The local audit policy exists to show observed values. For a package that "
            "withholds them, choose the restricted shareable export instead.")
    return disclosure


def disclosure_record(policy, permit_records=False) -> dict:
    """The canonical recipe field for one explicit choice.

    A request that asks the restricted export for records is refused, not quietly trimmed:
    the caller chose a policy whose consequence they need to see.
    """
    if policy not in DISCLOSURE_POLICIES:
        raise NeutralLibraryError(
            "Choose a disclosure policy from " + ", ".join(sorted(DISCLOSURE_POLICIES))
            + f"; got {policy!r}.")
    spec = DISCLOSURE_POLICIES[policy]
    if permit_records and not spec["permits_records"]:
        raise NeutralLibraryError(
            "The restricted shareable export cannot include contributing records. "
            "Choose the local audit policy for an export that carries them.")
    return {"schema": DISCLOSURE_SCHEMA, "policy": policy,
            "permit_values": bool(spec["permits_values"]),
            "permit_records": bool(spec["permits_records"] and permit_records)}


def disclosure_conflicts(recipe) -> list[dict]:
    """Unresolved disclosure/block combinations, in reader-facing terms.

    Returned instead of raised so the site can list them before generation. Each entry names
    the affected section and the two permitted remedies; nothing is silently downgraded to an
    availability-only display.
    """
    conflicts: list[dict] = []
    disclosure = recipe.get("disclosure")
    blocks = recipe.get("blocks") or []
    if disclosure is None:
        conflicts.append({
            "code": "disclosure_required",
            "block": None,
            "message": ("Choose how observed values are handled before generating: local audit "
                        "output (values included) or a restricted shareable export (values "
                        "excluded).")})
        return conflicts
    try:
        validate_disclosure(disclosure)
    except NeutralLibraryError as error:
        return [{"code": "disclosure_invalid", "block": None, "message": str(error)}]
    if disclosure["policy"] != "restricted-share":
        return conflicts
    titles = recipe.get("titles") or {}
    for entry in blocks:
        if entry.get("block") not in VALUE_BLOCKS:
            continue
        label = titles.get(entry.get("instance_id")) or NEUTRAL_BLOCKS[entry["block"]]["label"]
        conflicts.append({
            "code": "incompatible_block",
            "block": entry["block"],
            "instance_id": entry.get("instance_id"),
            "message": (f"The section “{label}” publishes observed numerical values, which the "
                        "restricted shareable export excludes. Either choose the local audit "
                        "policy for this report, or replace that section with “Observation "
                        "coverage over time”, which is the explicitly named availability view.")})
    return conflicts


def default_recipe(has_time: bool) -> dict:
    """The editable starter composition; values-over-time only when time is eligible."""
    blocks = [{"block": "intro", "instance_id": "intro-0001"},
              {"block": "data-overview", "instance_id": "csv-data-overview"}]
    if has_time:
        blocks.append({"block": "values-over-time", "instance_id": "csv-values-over-time",
                       "time_period": _auto_period(None)})
    else:
        blocks.append({"block": "values-by-group", "instance_id": "csv-values-by-group"})
    blocks += [{"block": "data-quality", "instance_id": "csv-data-quality"},
               {"block": "limitations", "instance_id": "limitations-0001"},
               {"block": "reproduction", "instance_id": "reproduction-0001"}]
    return {"contract": "health-report/composition-recipe/2",
            "audience": NEUTRAL_AUDIENCE, "blocks": blocks}


def _auto_period(period):
    return period if period in TIME_PERIODS else "year"


def allocate(block, taken, seq=0):
    """Next stable instance id for a neutral block; never reuses an id in ``taken``."""
    slug = block.replace("_", "-")
    attempt = int(seq or 0)
    while True:
        attempt += 1
        candidate = f"c-{slug}-{attempt:04d}"
        if _INSTANCE_ID.fullmatch(candidate) and candidate not in taken:
            return candidate, attempt


def entry_problem(entry, capabilities: dict) -> str | None:
    """Why a neutral library entry cannot render yet, or None."""
    block = entry.get("block")
    if block not in NEUTRAL_BLOCKS:
        return f"Unknown block type: {block!r}"
    if block in ("values-over-time", "coverage-over-time") and not capabilities.get("has_time"):
        return ("No time column is confirmed for this dataset, so a time view is not "
                "available.")
    if block == "values-by-group" and not capabilities.get("has_group"):
        return ("No group column is confirmed for this dataset; use the dataset overview "
                "instead.")
    return None


def combination_conflict(blocks, block):
    """Singleton/combination rules for neutral blocks."""
    spec = NEUTRAL_BLOCKS.get(block)
    if spec is None:
        raise NeutralLibraryError(f"Unknown block type: {block!r}")
    same = [entry["instance_id"] for entry in blocks if entry.get("block") == block]
    if same and not spec["repeatable"]:
        return {"kind": "singleton", "block": block, "instances": same,
                "reason": spec["repeat_reason"]}
    return None
