"""Strict composer contract and resolver for the existing reference comparison (G1).

Experimental: nothing in the reporting route imports this module yet. It reads saved
bundle artifacts and never calculates scientific metrics.

Layer boundaries are deliberate:

* ``validate_*`` -- structural only, no caller I/O. The single read is the bundled JSON
  Schema next to this module, cached and never caller-controlled.
* ``resolve_instance`` / ``resolve_composition`` -- pure. No clock, network, environment
  lookup or writes. Defaults are explicit and traced, never environment-derived.
* ``load_document`` / ``load_bundle`` -- read-only filesystem loaders.
* ``verify_references`` / ``check_block`` -- read-only cross-checks against a loaded
  bundle with two trusted roots: ``bundle_root`` for saved artifacts and ``project_root``
  for retained implementation code. An optional ``results_root`` resolves archived source
  files named by lineage.

Consistency is not truth. Matching digests, references and lineage only show that the
documents agree with the bundle they name. A party that rewrites ``metrics.csv`` and
recomputes ``bundle.json`` plus every recorded digest satisfies this contract; rejecting
that requires independent recomputation from captured inputs, which is separate work and
is not implemented here. No protection is claimed against hostile concurrent filesystem
mutation during a check.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import jsonschema
from jsonschema.exceptions import best_match

INSTANCE_CONTRACT = "health-report/composer-component/1"
EVIDENCE_CONTRACT = "health-report/composer-evidence/1"
COMPOSITION_CONTRACT = "health-report/composer-composition/1"

SCHEMA_PATH = (
    Path(__file__).resolve().parent
    / "config"
    / "composer"
    / "component-contract"
    / "1.json"
)

# Every analytical setting of the saved stakeholder.json that can change these numbers.
# Presentation-bearing fields (id, title, question, outputs, presentation) are excluded so
# that an audience swap cannot silently alter numerical identity.
SCOPE_FIELDS = (
    "period_type",
    "years",
    "reference_year",
    "index_base_year",
    "geography",
    "measures_preferred",
    "compare_by",
    "classes_in_main_comparison",
    "exclude_from_group_totals",
    "sensitivity_exclude",
    "source_priority",
    "group_source_systems",
    "dimension_filters",
)

# Optional report-scope fields. They are hashed only when present so historical bundles
# keep their original analytical identity. Topic-list order is not significant.
TOPIC_SCOPE_FIELDS = ("include_topics", "exclude_topics")


def canonical_scope(field, value):
    if field in TOPIC_SCOPE_FIELDS and isinstance(value, list):
        return sorted(value)
    return value


def scope_of(stakeholder: dict) -> dict:
    """Mandatory historical scope plus any explicitly recorded topic scope."""
    scope = {field: stakeholder[field] for field in SCOPE_FIELDS}
    for field in TOPIC_SCOPE_FIELDS:
        if field in stakeholder:
            scope[field] = stakeholder[field]
    return scope

COMPONENT_DEFAULTS = {
    "presentation": {"digits": 0},
    "disclosure": {"initial": "collapsed"},
}

# A profile may only contribute cosmetic defaults; it can never move a number.
PROFILE_DEFAULT_FIELDS = (("presentation", "digits"), ("disclosure", "initial"))

BUNDLE_ARTIFACTS = (
    "bundle.json",
    "stakeholder.json",
    "snapshot.json",
    "metrics.csv",
    "series.csv",
    "selection.csv",
    "lineage.csv",
)

METRIC_ID = re.compile(r"^[a-z][a-z0-9_]*(?::[a-z0-9_]+)+$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{2,39}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
UNAVAILABLE_REASON = "non_positive_baseline"

# This first component renders only the two bound endpoint rows of series.csv. That is a
# restriction of *this* component version, not a rule for later trend/chart components,
# which will declare their own plotted subsets against their own contracts.
PLOTTED_ARTIFACT = "series.csv"


class ContractError(ValueError):
    """Deterministic contract failure with a stable machine-readable ``code``."""

    def __init__(self, code: str, detail: str, subject: str = "", findings=()) -> None:
        self.code = code
        self.detail = detail
        self.subject = subject
        self.findings = tuple(findings)
        message = f"{code}: {detail}" if not subject else f"{code} [{subject}]: {detail}"
        super().__init__(message)


@dataclass(frozen=True)
class Finding:
    """One consistency finding from reference resolution."""

    code: str
    subject: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code} [{self.subject}]: {self.detail}"


@dataclass(frozen=True)
class ResolvedInstance:
    instance_id: str
    original_instance: dict
    original_evidence: dict
    effective: dict
    trace: tuple
    identities: dict


@dataclass(frozen=True)
class ResolvedComposition:
    composition_id: str
    ordered: tuple
    identities: dict
    original: dict


@dataclass(frozen=True)
class BlockRecord:
    instance_id: str
    effective: dict
    trace: tuple
    identities: dict
    available: bool
    findings: tuple = ()

    def ok(self) -> bool:
        return not self.findings


@dataclass(frozen=True)
class BundleEvidence:
    """Read-only view of the saved analysis bundle that a block refers to."""

    root: Path
    stakeholder: dict
    manifest: dict
    snapshot: dict
    metrics: dict
    series: tuple
    selection: tuple
    lineage: tuple
    artifact_findings: tuple = ()


# ---------------------------------------------------------------------------
# Strict JSON parsing
# ---------------------------------------------------------------------------

def _reject_constant(name: str):
    raise ContractError("nonfinite", f"JSON constant {name!r} is not allowed")


def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ContractError("duplicate_key", f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def _loads(text):
    if not isinstance(text, str):
        raise ContractError("invalid_json", "expected JSON text")
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise ContractError("invalid_json", str(exc)) from exc


# ---------------------------------------------------------------------------
# Structural validation (no caller I/O)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def contract_schema() -> dict:
    """The bundled schema. The only filesystem read inside structural validation."""
    return _loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator(name: str):
    schema = contract_schema()
    return jsonschema.Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": schema["$defs"]})


def _check_finite(value, where: str) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("nonfinite", f"{where}: non-finite number")
    if isinstance(value, dict):
        for key, item in value.items():
            _check_finite(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_finite(item, f"{where}[{index}]")


def _require_valid(document, name: str) -> None:
    if not isinstance(document, dict):
        raise ContractError("schema", f"{name} must be a JSON object")
    error = best_match(_validator(name).iter_errors(document))
    if error is not None:
        raise ContractError("schema", f"{error.json_path}: {error.message}")
    _check_finite(document, "$")


def _check_reference_path(value, field: str) -> None:
    """Path syntax only. Resolution against a trusted root is a separate layer."""
    if not isinstance(value, str) or not value.strip():
        raise ContractError("unsafe_reference", f"{field}: empty path")
    if "\x00" in value:
        raise ContractError("unsafe_reference", f"{field}: NUL byte in path")
    if "\\" in value:
        raise ContractError("unsafe_reference", f"{field}: backslash separators are not accepted")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ContractError("unsafe_reference", f"{field}: absolute paths are not accepted")
    if value.endswith("/"):
        raise ContractError("unsafe_reference", f"{field}: expected a file, not a directory")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ContractError("unsafe_reference", f"{field}: traversal or empty path segments are not accepted")


def _check_metric_id(value, field: str) -> None:
    if not isinstance(value, str) or not METRIC_ID.match(value):
        raise ContractError("invalid_metric_id", f"{field}: {value!r} is not a metric id")


def validate_instance(instance: dict) -> dict:
    _require_valid(instance, "instance")
    _check_reference_path(instance["plotted"]["file"], "plotted.file")
    bindings = instance["bindings"]
    for role in ("reference_count", "latest_count", "result"):
        _check_metric_id(bindings[role], f"bindings.{role}")
    if len(set(bindings.values())) != 3:
        raise ContractError("bindings", "the three bindings must name distinct metric ids")
    return instance


def validate_evidence(evidence: dict) -> dict:
    _require_valid(evidence, "evidence")
    for role in ("analysis", "presentation"):
        _check_reference_path(evidence["implementation"][role]["file"], f"implementation.{role}.file")
    if len(set(evidence["inputs"]["metric_ids"])) != 2:
        raise ContractError("bindings", "inputs.metric_ids must be two distinct metrics")
    results = evidence["results"]
    if results["availability"] == "available":
        if results["value"] is None:
            raise ContractError("availability", "an available result must record a numeric value")
        if results.get("unavailable_reason") is not None:
            raise ContractError("availability", "an available result must not record an unavailable reason")
    else:
        if results.get("unavailable_reason") is None:
            raise ContractError("availability", "an unavailable result must record a reason")
        if results["value"] is not None:
            raise ContractError("availability", "an unavailable result must not record a value")
    return evidence


def validate_composition(composition: dict) -> dict:
    _require_valid(composition, "composition")
    ids = composition["instances"]
    if len(set(ids)) != len(ids):
        raise ContractError("duplicate_instance", "the composition lists an instance id twice")
    return composition


# ---------------------------------------------------------------------------
# Identities (pure)
# ---------------------------------------------------------------------------

def _canonical(value) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    except ValueError as exc:  # pragma: no cover - guarded by finite checks
        raise ContractError("nonfinite", "identity input contains a non-finite number") from exc


def _identity(*parts) -> str:
    return hashlib.sha256(_canonical(list(parts))).hexdigest()


def _value_token(value):
    if value is None:
        return {"kind": "unavailable"}
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError("results", "results.value must be a number or null")
    number = float(value)
    if not math.isfinite(number):
        raise ContractError("nonfinite", "results.value is not finite")
    return {"kind": "number", "value": repr(number)}


def analytical_identity(instance: dict, evidence: dict) -> str:
    """Snapshot + validated analytical scope + method/version + resolved parameters."""
    scope = instance["analysis"]["scope"]
    fields = [field for field in SCOPE_FIELDS if field in scope]
    fields += [field for field in TOPIC_SCOPE_FIELDS if field in scope]
    return _identity(
        "analytical/1",
        {
            "snapshot_id": instance["analysis"]["snapshot_id"],
            "scope": {field: canonical_scope(field, scope[field]) for field in fields},
            "method": {
                "id": evidence["calculation"]["method_id"],
                "version": evidence["calculation"]["method_version"],
            },
            "parameters": evidence["calculation"]["parameters"],
        },
    )


def result_identity(instance: dict, evidence: dict, analytical: str | None = None) -> str:
    """Analytical identity + the saved result token, unit, formula and inputs."""
    analytical = analytical or analytical_identity(instance, evidence)
    return _identity(
        "result/1",
        {
            "analytical": analytical,
            "metric_id": evidence["results"]["metric_id"],
            "value": _value_token(evidence["results"]["value"]),
            "unit": evidence["results"]["unit"],
            "formula": evidence["calculation"]["formula"],
            "inputs": list(evidence["inputs"]["metric_ids"]),
        },
    )


def instance_identity(instance: dict, result: str, effective: dict) -> str:
    """Display identity: instance id, plotted subset, effective cosmetic settings."""
    rows = sorted(
        ([row["topic"], row["year"]] for row in instance["plotted"]["rows"]),
        key=lambda item: (item[0], item[1]),
    )
    return _identity(
        "instance/1",
        {
            "component": instance["component"],
            "instance_id": instance["instance_id"],
            "result": result,
            "plotted": {
                "file": instance["plotted"]["file"],
                "rows": rows,
                "digest": instance["plotted"]["digest"],
            },
            "settings": effective,
        },
    )


def composition_identity(entries) -> str:
    """Ordered (instance id, instance identity) pairs; reordering changes this hash."""
    return _identity(
        "composition/1",
        [{"instance_id": iid, "identity": ident} for iid, ident in entries],
    )


# ---------------------------------------------------------------------------
# Default resolution (pure)
# ---------------------------------------------------------------------------

DEFAULT_FIELDS = {("presentation", "digits"), ("disclosure", "initial")}
EFFECTIVE_FIELDS = {
    ("presentation", "unit"),
    ("presentation", "digits"),
    ("disclosure", "initial"),
    ("disclosure", "distribution"),
}


def _check_profile_default(section: str, key: str, value, code: str = "profile") -> None:
    if (section, key) == ("presentation", "digits"):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 6:
            raise ContractError(code, "presentation.digits must be an integer 0-6")
    if (section, key) == ("disclosure", "initial") and value not in ("collapsed", "expanded"):
        raise ContractError(code, "disclosure.initial must be collapsed or expanded")


def _validate_defaults_layer(layer, code: str = "defaults") -> None:
    """Only the two cosmetic defaults exist; a default can never widen the contract."""
    if not isinstance(layer, dict):
        raise ContractError(code, "default settings must be a mapping")
    unknown = set(layer) - {"presentation", "disclosure"}
    if unknown:
        raise ContractError(code, f"unsupported default section(s): {sorted(unknown)}")
    for section, block in layer.items():
        if not isinstance(block, dict):
            raise ContractError(code, f"{section} defaults must be a mapping")
        for key, value in block.items():
            if (section, key) not in DEFAULT_FIELDS:
                raise ContractError(code, f"unsupported default {section}.{key}")
            _check_profile_default(section, key, value, code)


def _validate_effective(effective: dict) -> None:
    for section, block in effective.items():
        if not isinstance(block, dict):
            raise ContractError("effective", f"{section} settings must be a mapping")
        for key, value in block.items():
            if (section, key) not in EFFECTIVE_FIELDS:
                raise ContractError("effective", f"unsupported effective setting {section}.{key}")
            if (section, key) in DEFAULT_FIELDS:
                _check_profile_default(section, key, value, "effective")


def _profile_defaults(profile) -> dict:
    layer: dict = {}
    if profile is None:
        return layer
    if not isinstance(profile, dict):
        raise ContractError("profile", "profile defaults must be a mapping")
    unknown_sections = set(profile) - {"presentation", "disclosure"}
    if unknown_sections:
        raise ContractError("profile", f"unsupported profile default section(s): {sorted(unknown_sections)}")
    for section, key in PROFILE_DEFAULT_FIELDS:
        block = profile.get(section)
        if block is None:
            continue
        if not isinstance(block, dict):
            raise ContractError("profile", f"{section} defaults must be a mapping")
        unknown = set(block) - {key}
        if unknown:
            raise ContractError("profile", f"unsupported profile default(s) for {section}: {sorted(unknown)}")
        if key in block:
            _check_profile_default(section, key, block[key])
            layer.setdefault(section, {})[key] = block[key]
    return layer


def resolve_instance(instance: dict, evidence: dict, *, profile=None, component_defaults=None) -> ResolvedInstance:
    """Pure structural + default resolution. The caller's objects are never mutated."""
    validate_instance(instance)
    validate_evidence(evidence)
    if instance["instance_id"] != evidence["instance_id"]:
        raise ContractError(
            "instance_mismatch",
            "instance and evidence name different instance ids",
            subject=instance["instance_id"],
        )

    original_instance = copy.deepcopy(instance)
    original_evidence = copy.deepcopy(evidence)
    defaults = copy.deepcopy(COMPONENT_DEFAULTS if component_defaults is None else component_defaults)
    _validate_defaults_layer(defaults)
    profile_layer = _profile_defaults(profile)

    effective: dict = {}
    trace = []
    for section, authored in (("presentation", instance["presentation"]), ("disclosure", instance["disclosure"])):
        resolved = {}
        keys = sorted(set(authored) | set(defaults.get(section) or {}) | set(profile_layer.get(section, {})))
        for key in keys:
            if key in authored:
                value, source = authored[key], "author"
            elif key in profile_layer.get(section, {}):
                value, source = profile_layer[section][key], "profile"
            else:
                value, source = (defaults.get(section) or {})[key], "component"
            resolved[key] = value
            trace.append({"field": f"{section}.{key}", "source": source, "value": value})
        effective[section] = resolved

    _validate_effective(effective)

    analytical = analytical_identity(original_instance, original_evidence)
    result = result_identity(original_instance, original_evidence, analytical)
    return ResolvedInstance(
        instance_id=instance["instance_id"],
        original_instance=original_instance,
        original_evidence=original_evidence,
        effective=effective,
        trace=tuple(trace),
        identities={"analytical": analytical, "result": result, "instance": instance_identity(original_instance, result, effective)},
    )


def resolve_composition(composition: dict, instances) -> ResolvedComposition:
    """Pure. Composition references must resolve against the supplied collection."""
    validate_composition(composition)
    collection = {}
    for resolved in instances:
        if resolved.instance_id in collection:
            raise ContractError("duplicate_instance", "the supplied instance collection repeats an id", subject=resolved.instance_id)
        collection[resolved.instance_id] = resolved
    ordered = tuple(composition["instances"])
    missing = [iid for iid in ordered if iid not in collection]
    if missing:
        raise ContractError("dangling_reference", f"composition references unresolved instance(s): {missing}", subject=composition["composition_id"])
    entries = [(iid, collection[iid].identities["instance"]) for iid in ordered]
    return ResolvedComposition(
        composition_id=composition["composition_id"],
        ordered=ordered,
        identities={"per_instance": dict(entries), "composition": composition_identity(entries)},
        original=copy.deepcopy(composition),
    )


# ---------------------------------------------------------------------------
# Read-only loaders
# ---------------------------------------------------------------------------

_VALIDATORS = {
    "instance": validate_instance,
    "evidence": validate_evidence,
    "composition": validate_composition,
}


def load_document(path, kind: str) -> dict:
    if kind not in _VALIDATORS:
        raise ContractError("kind", f"unknown document kind {kind!r}")
    document = _loads(Path(path).read_text(encoding="utf-8"))
    _VALIDATORS[kind](document)
    return document


def _read_csv(path: Path) -> tuple:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def load_bundle(bundle_root) -> BundleEvidence:
    """Read the saved analysis bundle. No writes, no recalculation.

    Every manifest entry is re-hashed and every consumed artifact must be listed, so a
    stale or edited artifact is reported instead of silently consumed. Artifacts that are
    not regular files inside the bundle root are not read at all.
    """
    root = Path(bundle_root)
    if not root.is_dir():
        raise ContractError("bundle", f"bundle root is not a directory: {root}")
    bundle_file = root / "bundle.json"
    if not _safe_regular_file(bundle_file, root):
        raise ContractError("artifact_unsafe",
                            "bundle.json must be a regular file inside the bundle root",
                            subject="bundle.json")
    missing = [name for name in BUNDLE_ARTIFACTS if name != "bundle.json" and not (root / name).exists()]
    if missing:
        raise ContractError("bundle", f"bundle is missing {missing}", subject=str(root))

    manifest = _loads(bundle_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise ContractError("manifest", "bundle.json must contain a files object")
    files = manifest["files"]
    for name, digest in files.items():
        if not isinstance(name, str) or not isinstance(digest, str) or not SHA256.match(digest):
            raise ContractError("manifest", f"invalid bundle.json entry {name!r}")

    artifact_findings = []
    for name in BUNDLE_ARTIFACTS:
        if name == "bundle.json":
            continue
        candidate = root / name
        try:
            _check_reference_path(name, f"artifact.{name}")
        except ContractError as exc:
            artifact_findings.append(Finding("artifact_unsafe", name, exc.detail))
            continue
        if not _safe_regular_file(candidate, root):
            artifact_findings.append(Finding("artifact_unsafe", name, "artifact is not a regular file inside the bundle"))
            if name not in files:
                artifact_findings.append(Finding("artifact_unlisted", name, "consumed artifact is not listed in bundle.json"))
            continue
        if name not in files:
            artifact_findings.append(Finding("artifact_unlisted", name, "consumed artifact is not listed in bundle.json"))
        elif _sha256_file(candidate) != files[name]:
            artifact_findings.append(Finding("digest_disagreement", name, "bundle.json digest differs from the saved artifact bytes"))

    for name in sorted(files):
        if name == "bundle.json" or name in BUNDLE_ARTIFACTS:
            continue
        try:
            _check_reference_path(name, f"manifest.{name}")
        except ContractError as exc:
            artifact_findings.append(Finding("artifact_unsafe", name, exc.detail))
            continue
        candidate = root / name
        if not _safe_regular_file(candidate, root):
            artifact_findings.append(Finding("artifact_unsafe", name, "declared artifact is not a regular file inside the bundle"))
            continue
        if _sha256_file(candidate) != files[name]:
            artifact_findings.append(Finding("digest_disagreement", name, "bundle.json digest differs from the saved artifact bytes"))

    unsafe = {item.subject for item in artifact_findings if item.code == "artifact_unsafe"}

    def read_json(name):
        if name in unsafe:
            return {}
        return _loads((root / name).read_text(encoding="utf-8"))

    def read_rows(name):
        if name in unsafe:
            return ()
        return _read_csv(root / name)

    metrics = {}
    for row in read_rows("metrics.csv"):
        metric_id = row.get("metric_id", "")
        if metric_id in metrics:
            raise ContractError("duplicate_metric", f"metrics.csv repeats {metric_id!r}")
        metrics[metric_id] = row

    return BundleEvidence(
        root=root,
        stakeholder=read_json("stakeholder.json"),
        manifest=manifest,
        snapshot=read_json("snapshot.json"),
        metrics=metrics,
        series=read_rows("series.csv"),
        selection=read_rows("selection.csv"),
        lineage=read_rows("lineage.csv"),
        artifact_findings=tuple(artifact_findings),
    )


# ---------------------------------------------------------------------------
# Reference resolution against the saved bundle (read-only)
# ---------------------------------------------------------------------------

def _cell_number(text):
    if text is None:
        return None
    raw = str(text).strip()
    if raw in ("", "nan", "NaN", "None"):
        return None
    try:
        number = float(raw)
    except ValueError as exc:
        raise ContractError("invalid_value", f"unparsable saved number {text!r}") from exc
    if not math.isfinite(number):
        raise ContractError("nonfinite", f"saved number {text!r} is not finite")
    return number


def _record_number(text):
    """Exact positive CSV data-record number: ASCII integer or integer with zero fraction.

    Accepted forms are ``"521"``, ``"521.0"`` and ``"521.00"``. The header is record 1 and
    data starts at record 2, so any value below 2 is not a data-record number. Fractions,
    signs, empty values, non-finite names, exponent notation and booleans are rejected.
    The digits are parsed as an integer; the original stored text is never rewritten.
    """
    if not isinstance(text, str):
        return None
    match = re.fullmatch(r"([0-9]+)(?:\.(0+))?", text)
    if match is None:
        return None
    value = int(match.group(1))
    return value if value >= 2 else None


def _json_list(text):
    if text is None:
        return None
    try:
        value = _loads(text)
    except ContractError:
        return None
    return value if isinstance(value, list) else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_regular_file(path: Path, root: Path) -> bool:
    """Regular file lexically under ``root``, with no symlinked path component.

    The lexical walk runs before resolution, so a symlinked *parent* directory is
    rejected even when it resolves back inside the root.
    """
    root = Path(root)
    candidate = Path(path)
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return False
    if not relative.parts:
        return False
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return False
    if not candidate.is_file():
        return False
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    return resolved == resolved_root or resolved_root in resolved.parents


def verify_references(resolved: ResolvedInstance, bundle: BundleEvidence, *, project_root, results_root=None) -> tuple:
    """Cross-check a resolved block against the saved bundle. Returns findings."""
    findings = list(bundle.artifact_findings)

    def add(code: str, subject: str, detail: str) -> None:
        findings.append(Finding(code, subject, detail))

    instance = resolved.original_instance
    evidence = resolved.original_evidence
    scope = instance["analysis"]["scope"]
    bindings = instance["bindings"]
    parameters = evidence["calculation"]["parameters"]

    if parameters["reference_year"] != scope["reference_year"]:
        add("parameter_disagreement", "parameters.reference_year",
            f"recorded reference year {parameters['reference_year']!r} differs from the saved scope {scope['reference_year']!r}")
    if parameters["latest_year"] != scope["years"][1]:
        add("parameter_disagreement", "parameters.latest_year",
            f"recorded latest year {parameters['latest_year']!r} differs from the saved scope {scope['years'][1]!r}")

    for field in SCOPE_FIELDS:
        if field not in bundle.stakeholder:
            add("scope_missing", f"scope.{field}", "saved stakeholder settings omit this field")
        elif scope[field] != bundle.stakeholder[field]:
            add(
                "scope_disagreement",
                f"scope.{field}",
                f"contract value {scope[field]!r} differs from saved setting {bundle.stakeholder[field]!r}",
            )

    # Optional topic scope must agree in both directions: absence on one side must not
    # bypass an explicit restriction on the other.
    for field in TOPIC_SCOPE_FIELDS:
        in_scope, in_bundle = field in scope, field in bundle.stakeholder
        if in_scope != in_bundle:
            add("scope_disagreement", f"scope.{field}",
                "topic scope is recorded in only one of the instance and the saved settings")
        elif in_scope and canonical_scope(field, scope[field]) != canonical_scope(field, bundle.stakeholder[field]):
            add("scope_disagreement", f"scope.{field}",
                "recorded topic scope differs from the saved settings")

    if instance["analysis"]["snapshot_id"] != bundle.snapshot.get("snapshot_id"):
        add("snapshot_disagreement", "analysis.snapshot_id", "contract snapshot id differs from the saved snapshot")
    declared_snapshot = evidence["reproduction"].get("snapshot_id")
    if declared_snapshot is not None and declared_snapshot != instance["analysis"]["snapshot_id"]:
        add("snapshot_disagreement", "reproduction.snapshot_id", "reproduction snapshot id differs from the analysis snapshot")

    rows = {}
    for role in ("reference_count", "latest_count", "result"):
        metric_id = bindings[role]
        row = bundle.metrics.get(metric_id)
        if row is None:
            add("metric_missing", metric_id, f"bindings.{role} is absent from the saved metrics")
        else:
            rows[role] = row

    for role in ("reference_count", "latest_count"):
        if role not in rows:
            continue
        saved_count = _cell_number(rows[role].get("value"))
        if saved_count is None:
            add("count_value", bindings[role], "bound count has no saved numeric value")
        elif saved_count < 0:
            add("count_value", bindings[role], "bound count is negative, contradicting save-time eligibility")

    if "reference_count" in rows and "latest_count" in rows:
        reference, latest = rows["reference_count"], rows["latest_count"]
        for role, row, year in (
            ("reference_count", reference, parameters["reference_year"]),
            ("latest_count", latest, parameters["latest_year"]),
        ):
            if row.get("metric_type") != "count":
                add("metric_type", bindings[role], f"{role} is not a saved count metric")
            if str(row.get("year")) != str(year):
                add("parameter_disagreement", bindings[role], f"{role} year {row.get('year')!r} differs from recorded {year}")
            if row.get("unit") != parameters["measure"]:
                add("measure_disagreement", bindings[role], f"{role} unit {row.get('unit')!r} differs from recorded measure {parameters['measure']!r}")
        if reference.get("subject") != latest.get("subject"):
            add("metric_subject", bindings["reference_count"], "bound count metrics belong to different subjects")
        if reference.get("subject") != rows.get("result", {}).get("subject"):
            add("metric_subject", bindings["result"], "result metric subject differs from the bound counts")

    saved_value = None
    if "result" in rows:
        result_row = rows["result"]
        if result_row.get("metric_type") != "reference_change":
            add("metric_type", bindings["result"], "the result metric is not a reference_change metric")
        if result_row.get("formula") != evidence["calculation"]["formula"]:
            add("formula_disagreement", bindings["result"], "saved formula differs from the recorded formula")
        if result_row.get("unit") != evidence["results"]["unit"]:
            add("unit_disagreement", bindings["result"], "saved unit differs from the recorded unit")
        if str(result_row.get("year")) != str(parameters["latest_year"]):
            add("parameter_disagreement", bindings["result"], "saved result year differs from the recorded latest year")
        declared_inputs = _json_list(result_row.get("inputs_json"))
        if declared_inputs != [bindings["reference_count"], bindings["latest_count"]]:
            add("inputs_disagreement", bindings["result"], "saved metric inputs differ from the bound counts")
        saved_value = _cell_number(result_row.get("value"))
        declared_value = evidence["results"]["value"]
        if saved_value is None and declared_value is not None:
            add("result_disagreement", bindings["result"], "the evidence claims a value that the saved result does not contain")
        elif saved_value is not None and declared_value is None:
            add("result_disagreement", bindings["result"], "the evidence omits a value that the saved result contains")
        elif saved_value is not None and declared_value is not None and float(declared_value) != saved_value:
            add("result_disagreement", bindings["result"], f"recorded value {declared_value!r} differs from saved value {saved_value!r}")
        if saved_value is None:
            if evidence["results"]["availability"] != "unavailable":
                add("availability_disagreement", bindings["result"], "saved result is unavailable but the evidence claims availability")
            if evidence["results"].get("unavailable_reason") != UNAVAILABLE_REASON:
                add("availability_disagreement", bindings["result"], f"unavailable results must record {UNAVAILABLE_REASON}")
            if "reference_count" in rows:
                reference_value = _cell_number(rows["reference_count"].get("value"))
                if reference_value not in (None, 0.0):
                    add("availability_disagreement", bindings["reference_count"], "an unavailable percentage requires a zero saved reference count")
        elif evidence["results"]["availability"] != "available":
            add("availability_disagreement", bindings["result"], "saved result is available but the evidence declares it unavailable")
        if saved_value is not None and "reference_count" in rows:
            if _cell_number(rows["reference_count"].get("value")) == 0:
                add("availability_disagreement", bindings["reference_count"],
                    "a zero saved reference count must make the percentage unavailable")

    if evidence["inputs"]["metric_ids"] != [bindings["reference_count"], bindings["latest_count"]]:
        add("inputs_disagreement", "inputs.metric_ids", "evidence inputs differ from the bound counts")
    if evidence["results"]["metric_id"] != bindings["result"]:
        add("result_disagreement", "results.metric_id", "evidence result metric differs from the bound result")

    subject = rows.get("result", {}).get("subject") or rows.get("reference_count", {}).get("subject")
    bound_series = {}
    if subject:
        for role, year in (("reference_count", parameters["reference_year"]),
                           ("latest_count", parameters["latest_year"])):
            matches = [item for item in bundle.series
                       if item.get("topic") == subject
                       and str(item.get("year")) == str(year)
                       and item.get("count_metric_id") == bindings[role]]
            if len(matches) == 1:
                bound_series[role] = matches[0]
        for role, item in bound_series.items():
            saved_series_value = _cell_number(item.get("value"))
            bound_metric_value = _cell_number(rows[role].get("value")) if role in rows else None
            if saved_series_value is None or bound_metric_value is None or saved_series_value != bound_metric_value:
                add("series_value_disagreement", bindings[role],
                    f"saved series value {item.get('value')!r} differs from the bound count value {(rows.get(role) or {}).get('value')!r}")
            if role in rows and item.get("measure") != rows[role].get("unit"):
                add("series_scope_disagreement", bindings[role],
                    "saved series measure differs from the bound count unit")
            if item.get("geography") != scope["geography"]:
                add("series_scope_disagreement", bindings[role],
                    "saved series geography differs from the saved scope")
        sources = {(item.get("dataset_id"), item.get("source_system"))
                   for item in bound_series.values()}
        if not bound_series or len(sources) != 1:
            add("series_source_mismatch", subject,
                "the bound count metrics do not share one saved dataset/source row")
        else:
            dataset_id, source_system = next(iter(sources))
            candidates = [
                item for item in bundle.selection
                if item.get("topic") == subject
                and item.get("dataset_id") == dataset_id
                and item.get("source_system") == source_system
            ]
            if not candidates:
                add("selection_missing", subject,
                    f"no saved selection row for dataset {dataset_id!r} / source {source_system!r}")
            elif len(candidates) > 1:
                add("selection_ambiguous", subject,
                    "several saved selection rows match the bound dataset and source")
            elif candidates[0].get("status") != "included":
                add("selection_excluded", subject,
                    f"saved selection status {candidates[0].get('status')!r}: {candidates[0].get('reason')!r}")

    manifest_files = bundle.manifest.get("files") or {}
    plotted = instance["plotted"]
    if plotted["file"] != PLOTTED_ARTIFACT:
        add("plotted_artifact", plotted["file"], f"this component plots {PLOTTED_ARTIFACT} only")
    if plotted["file"] not in manifest_files:
        add("plotted_missing", plotted["file"], "plotted artifact is not listed in bundle.json")
    elif manifest_files[plotted["file"]] != plotted["digest"]:
        add("digest_disagreement", plotted["file"], "plotted digest differs from the bundle manifest")
    artifact = bundle.root / plotted["file"]
    if not _safe_regular_file(artifact, bundle.root):
        add("artifact_unsafe", plotted["file"], "plotted artifact is not a regular file inside the bundle")
    elif _sha256_file(artifact) != plotted["digest"]:
        add("digest_disagreement", plotted["file"], "plotted digest differs from the saved artifact bytes")

    for row in plotted["rows"]:
        matches = [s for s in bundle.series if s.get("topic") == row["topic"] and str(s.get("year")) == str(row["year"])]
        if len(matches) != 1:
            add("plotted_row", f"{row['topic']}:{row['year']}", "plotted row is not a unique saved series row")
        elif row["year"] == parameters["reference_year"]:
            if matches[0].get("count_metric_id") != bindings["reference_count"]:
                add("plotted_row", f"{row['topic']}:{row['year']}", "saved series row is bound to a different count metric")
        elif row["year"] == parameters["latest_year"]:
            if matches[0].get("count_metric_id") != bindings["latest_count"]:
                add("plotted_row", f"{row['topic']}:{row['year']}", "saved series row is bound to a different count metric")

    declared_rows = [(item["topic"], item["year"]) for item in plotted["rows"]]
    if len(declared_rows) != len(set(declared_rows)):
        add("plotted_row", subject or "plotted", "plotted rows repeat a topic/year")
    expected_rows = {(subject, parameters["reference_year"]), (subject, parameters["latest_year"])} if subject else set()
    if expected_rows and set(declared_rows) != expected_rows:
        add("plotted_row", subject, f"plotted rows {sorted(declared_rows)} are not exactly the two bound endpoints")

    project_root = Path(project_root)
    for role in ("analysis", "presentation"):
        reference = evidence["implementation"][role]
        try:
            _check_reference_path(reference["file"], f"implementation.{role}.file")
        except ContractError as exc:
            add(exc.code, exc.subject or f"implementation.{role}.file", exc.detail)
            continue
        path = project_root / reference["file"]
        if not _safe_regular_file(path, project_root):
            add("implementation_missing", reference["file"], f"{role} implementation file is missing or outside the project root")
        elif _sha256_file(path) != reference["sha256"]:
            add("digest_disagreement", reference["file"], f"{role} implementation digest differs from the retained file")

    for role in ("reference_count", "latest_count"):
        metric_id = bindings[role]
        metric_lineage = [row for row in bundle.lineage if row.get("metric_id") == metric_id]
        if not metric_lineage:
            add("lineage_missing", metric_id, "no lineage row for the bound count metric")
        for row in metric_lineage:
            kind = row.get("input_kind")
            if kind == "metric":
                add("lineage_unsupported", metric_id,
                    "count metrics must retain raw provenance, not metric-derived lineage")
                if row.get("input_id") not in bundle.metrics:
                    add("lineage_dangling", metric_id, f"lineage names unknown metric {row.get('input_id')!r}")
            elif kind == "raw":
                try:
                    _check_reference_path(row.get("source_file", ""), f"lineage.{metric_id}.source_file")
                except ContractError as exc:
                    add(exc.code, metric_id, exc.detail)
                if not SHA256.match(row.get("sha256", "") or ""):
                    add("lineage_digest", metric_id, "raw lineage row lacks a source sha256")
                if _record_number(row.get("source_row")) is None:
                    add("lineage_row", metric_id,
                        "raw lineage row lacks an exact positive data-record number (>=2)")
            else:
                add("lineage_kind", metric_id, f"unsupported lineage input kind {kind!r}")

    snapshot_path = bundle.snapshot.get("snapshot_path")
    if results_root is not None and snapshot_path is not None:
        try:
            _check_reference_path(str(snapshot_path), "snapshot_path")
        except ContractError as exc:
            add("snapshot_path", "snapshot.json", exc.detail)
        else:
            results_resolved = Path(results_root).resolve()
            archive = Path(results_root) / snapshot_path
            symlinked = None
            current = Path(results_root)
            for part in Path(snapshot_path).parts:
                current = current / part
                if current.is_symlink():
                    symlinked = part
                    break
            if symlinked is not None:
                add("snapshot_path", str(snapshot_path),
                    f"snapshot path component {symlinked!r} is a symlink")
            elif not archive.is_dir():
                for row in bundle.lineage:
                    if row.get("input_kind") == "raw" and row.get("source_file"):
                        add("lineage_source_missing", row["source_file"],
                            "the recorded snapshot directory is absent")
            else:
                archive_resolved = archive.resolve(strict=True)
                if archive_resolved != results_resolved and results_resolved not in archive_resolved.parents:
                    add("snapshot_path", str(snapshot_path),
                        "the snapshot directory is not contained in the results root")
                else:
                    for row in bundle.lineage:
                        if row.get("input_kind") != "raw":
                            continue
                        source = row.get("source_file", "")
                        if not source:
                            continue
                        candidate = archive / source
                        if not _safe_regular_file(candidate, archive):
                            add("lineage_source_missing", source, "archived source file named by lineage is absent")

    return tuple(findings)


def check_block(instance: dict, evidence: dict, bundle: BundleEvidence, *, project_root, results_root=None, profile=None) -> BlockRecord:
    """Resolve one block and require it to be consistent with the saved bundle."""
    resolved = resolve_instance(instance, evidence, profile=profile)
    findings = verify_references(resolved, bundle, project_root=project_root, results_root=results_root)
    if findings:
        raise ContractError("inconsistent", "; ".join(str(item) for item in findings), subject=resolved.instance_id, findings=findings)
    return BlockRecord(
        instance_id=resolved.instance_id,
        effective=resolved.effective,
        trace=resolved.trace,
        identities=resolved.identities,
        available=evidence["results"]["value"] is not None,
    )


__all__ = [
    "BlockRecord",
    "BundleEvidence",
    "COMPONENT_DEFAULTS",
    "COMPOSITION_CONTRACT",
    "ContractError",
    "EVIDENCE_CONTRACT",
    "Finding",
    "INSTANCE_CONTRACT",
    "PROFILE_DEFAULT_FIELDS",
    "ResolvedComposition",
    "ResolvedInstance",
    "SCOPE_FIELDS",
    "TOPIC_SCOPE_FIELDS",
    "analytical_identity",
    "canonical_scope",
    "check_block",
    "composition_identity",
    "contract_schema",
    "instance_identity",
    "load_bundle",
    "load_document",
    "resolve_composition",
    "resolve_instance",
    "result_identity",
    "scope_of",
    "validate_composition",
    "validate_evidence",
    "validate_instance",
    "verify_references",
]
