"""Verified local tabular bundles; not connected to workflow or rendering.

Publication requires Linux renameat2(RENAME_NOREPLACE), a trusted existing
parent directory, and no hostile concurrent filesystem mutation. Hashes prove
internal identity, not source authenticity. Verification requires matching
preparation code files and Python/pandas versions.
"""
from __future__ import annotations

import copy
import ctypes
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from tabular_prepare import PreparedTable, prepare_payload

SCHEMA = "health-report/tabular-bundle/1"
TABLE_SCHEMA = "health-report/prepared-rows/1"


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def _json_load(payload):
    return json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs,
                      parse_constant=_constant)


def _table_bytes(table):
    if not isinstance(table, pd.DataFrame):
        raise ValueError("Prepared rows must be a DataFrame.")
    if list(table.columns) != ["category", "value", "period"]:
        raise ValueError("Unexpected prepared columns.")
    if not table.index.equals(pd.RangeIndex(len(table))) or table.index.name is not None:
        raise ValueError("Prepared row index changed.")
    rows = []
    for category, value, period in table.itertuples(index=False, name=None):
        if pd.isna(category):
            category = None
        elif not isinstance(category, str):
            raise ValueError("Category must be text or missing.")
        if pd.isna(value):
            value = None
        else:
            value = value.item() if hasattr(value, "item") else value
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Measure must be numeric or missing.")
        if pd.isna(period):
            period = None
        else:
            if not isinstance(period, pd.Timestamp) or period.tzinfo is not None:
                raise ValueError("Period must be a timezone-naive Timestamp.")
            period = period.isoformat()
        rows.append([category, value, period])
    return _json_bytes({
        "schema": TABLE_SCHEMA,
        "columns": [
            {"name": "category", "type": "string|null"},
            {"name": "value", "type": "number|null"},
            {"name": "period", "type": "ISO-8601-naive-datetime|null"},
        ],
        "rows": rows,
    })


def _reproduce(payload, provenance):
    if not isinstance(payload, bytes) or not isinstance(provenance, dict):
        raise ValueError("Invalid captured input or provenance.")
    try:
        stamp = datetime.fromisoformat(provenance["prepared_at_utc"])
        if stamp.utcoffset() != timedelta(0):
            raise ValueError("Preparation timestamp must be UTC-aware.")
        name = provenance["input"]["source_filename"]
        if (not isinstance(name, str) or not name or "/" in name or "\\" in name
                or name in {".", ".."}):
            raise ValueError("Unsafe source filename.")
        parameters = provenance["parameters"]
        if not isinstance(parameters, dict) or set(parameters) != {"mapping", "mode", "period"}:
            raise ValueError("Invalid preparation parameters.")
        reproduced = prepare_payload(payload, source_filename=name, **parameters)
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid provenance contract.") from exc
    actual = dict(provenance)
    expected = dict(reproduced.provenance)
    actual.pop("prepared_at_utc")
    expected.pop("prepared_at_utc")
    if _json_bytes(actual) != _json_bytes(expected):
        raise ValueError("Provenance does not match reproduced preparation.")
    return reproduced


def _safe_path(path):
    path = Path(path)
    if ".." in path.parts:
        raise ValueError("Parent traversal is not allowed.")
    path = path.absolute()
    for component in [path, *path.parents]:
        if component.is_symlink():
            raise ValueError("Symlink paths are not allowed.")
    return path


def _read_regular(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("Bundle artifacts must be regular files.")
        return handle.read()


def verify_prepared_bundle(destination):
    """Capture artifacts once, verify hashes, and independently replay preparation.

    No files are written. Return reproduced rows with the saved provenance.
    A matching runtime/code identity is required; timestamps are validated,
    but their historical truth cannot be independently established.
    """
    root = _safe_path(destination)
    if not root.is_dir():
        raise ValueError("Bundle directory is missing.")
    entries = list(root.iterdir())
    names = {entry.name for entry in entries}
    sources = names & {"source.csv", "source.tsv"}
    if len(sources) != 1:
        raise ValueError("Bundle must contain exactly one source artifact.")
    source_name = next(iter(sources))
    expected_names = {source_name, "table.json", "provenance.json", "manifest.json"}
    if names != expected_names:
        raise ValueError("Missing or unexpected bundle artifacts.")
    for entry in entries:
        if entry.is_symlink() or not entry.is_file():
            raise ValueError("Symlinks and non-files are forbidden.")
    captured = {name: _read_regular(root / name) for name in expected_names}
    manifest = _json_load(captured["manifest.json"])
    if (not isinstance(manifest, dict) or set(manifest) != {"schema", "artifacts"}
            or manifest["schema"] != SCHEMA):
        raise ValueError("Invalid bundle manifest.")
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != expected_names - {"manifest.json"}:
        raise ValueError("Invalid manifest artifact set.")
    for name, description in artifacts.items():
        if (not isinstance(description, dict) or set(description) != {"sha256", "bytes"}
                or type(description["bytes"]) is not int):
            raise ValueError("Invalid artifact description.")
        payload = captured[name]
        if (description["bytes"] != len(payload)
                or description["sha256"] != hashlib.sha256(payload).hexdigest()):
            raise ValueError(f"Artifact hash or byte count mismatch: {name}")
    provenance = _json_load(captured["provenance.json"])
    reproduced = _reproduce(captured[source_name], provenance)
    suffix = Path(provenance["input"]["source_filename"]).suffix.lower()
    if source_name != "source" + suffix:
        raise ValueError("Source encoding and artifact name disagree.")
    if captured["provenance.json"] != _json_bytes(provenance):
        raise ValueError("Provenance is not canonically serialized.")
    if captured["table.json"] != _table_bytes(reproduced.table):
        raise ValueError("Saved rows differ from reproduced preparation.")
    return PreparedTable(reproduced.table, provenance, captured[source_name])


def _rename_no_replace(source, destination):
    if not sys.platform.startswith("linux"):
        raise NotImplementedError("No-overwrite publication requires Linux.")
    library = ctypes.CDLL(None, use_errno=True)
    try:
        rename = library.renameat2
    except AttributeError as exc:
        raise NotImplementedError("renameat2 is unavailable.") from exc
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                       ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def _write_artifacts(stage, artifacts):
    for name, payload in artifacts.items():
        with (stage / name).open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())


def publish_prepared_bundle(prepared, destination):
    """Verify mutable input, stage, verify on disk, then publish without replacement.

    The parent must exist and be trusted. This is atomic namespace publication,
    not a power-loss durability guarantee or an authenticated archive.
    """
    if not isinstance(prepared, PreparedTable):
        raise ValueError("Expected a PreparedTable.")
    payload = prepared.source_bytes
    provenance = copy.deepcopy(prepared.provenance)
    table = prepared.table.copy(deep=True)
    reproduced = _reproduce(payload, provenance)
    table_bytes = _table_bytes(table)
    if table_bytes != _table_bytes(reproduced.table):
        raise ValueError("Mutable prepared rows disagree with captured input.")
    destination = _safe_path(destination)
    if not destination.name or not destination.parent.is_dir():
        raise ValueError("A named destination and existing parent are required.")
    if os.path.lexists(destination):
        raise FileExistsError(str(destination))
    source_name = "source" + Path(provenance["input"]["source_filename"]).suffix.lower()
    artifacts = {
        source_name: payload,
        "table.json": table_bytes,
        "provenance.json": _json_bytes(provenance),
    }
    manifest = {"schema": SCHEMA, "artifacts": {
        name: {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for name, content in artifacts.items()
    }}
    artifacts["manifest.json"] = _json_bytes(manifest)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-",
                                  dir=destination.parent))
    try:
        _write_artifacts(stage, artifacts)
        verify_prepared_bundle(stage)
        _rename_no_replace(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination
