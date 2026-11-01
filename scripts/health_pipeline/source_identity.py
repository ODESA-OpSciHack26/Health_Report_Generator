"""One shared source-identity record for reporting runs.

A linked Git worktree keeps its administration directory outside the checkout, so a
container that mounts the checkout cannot resolve ``git``.  The host therefore collects
a record before the run and the runtime verifies the part it can actually see.

What the runtime verifies
-------------------------
The declared execution inputs (``ROOT_FILES`` + ``ROOT_DIRS``) are hashed from the
mounted tree and compared with the host-supplied manifest: path set, per-file digests,
count and canonical digest.  A mismatch, an unreadable file, a symlink or a malformed
record fails the generation instead of being downgraded to "unknown".

What remains an external assertion
----------------------------------
The commit, HEAD tree and the staged/unstaged/untracked classification are reported by
the host.  The runtime has no Git object database and cannot prove that a commit
describes these bytes.  The published record says so; this module never claims complete
source attestation.

Published output carries safe summaries only (commit, counts, content digest).  Detailed
path lists stay in the local host record and in actionable error messages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "health-report/source-identity/1"
ENV_VAR = "HEALTH_REPORT_SOURCE_IDENTITY"
MAX_RECORD_BYTES = 512 * 1024

# Declared execution inputs: orchestration, pipeline code, workflow configuration and the
# composer service.  Tests, data, dependency locks and external tools are deliberately
# outside this content claim; see LIMITS below and docs/reproduction.md.
ROOT_FILES = ("Snakefile", ".Rprofile", "renv.lock", "pyproject.toml", "Dockerfile.report")
ROOT_DIRS = ("scripts", "workflow", "src")
ROOTS = ROOT_FILES + ROOT_DIRS
EXCLUDED_DIR_NAMES = frozenset({".git", ".snakemake", ".pytest_cache", "__pycache__",
                                ".venv", "venv", "results", "reproduced", "out",
                                "node_modules"})
EXCLUDED_SUFFIXES = (".pyc", ".pyo")
EXCLUDED_NAMES = (".DS_Store",)

LIMITS = ("Commit, HEAD tree and the staged/unstaged/untracked classification are "
          "host-reported external assertions. The runtime verified only the content "
          "digest of the declared execution inputs. Data snapshots, dependency locks, "
          "container images and external tools are recorded separately; this is not "
          "complete source attestation.")

_SHA = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SourceIdentityError(ValueError):
    """A supplied identity, or the source it claims to describe, is unusable."""


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise SourceIdentityError("source identity paths must be non-empty strings")
    if value.startswith("/") or "\\" in value:
        raise SourceIdentityError(f"source identity path is not repository-relative: {value!r}")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise SourceIdentityError(f"source identity path escapes or is ambiguous: {value!r}")
    return value


def _declared(path: str) -> bool:
    return path in ROOT_FILES or any(path == d or path.startswith(d + "/") for d in ROOT_DIRS)


def _hash_file(path: Path, relative: str) -> str:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SourceIdentityError(
            f"declared execution input cannot be read: {relative} ({exc.strerror or exc})") from None
    return hashlib.sha256(payload).hexdigest()


def content_manifest(project_root) -> dict:
    """Hash every declared execution input; deterministic and fail-closed.

    Included: regular files under ``ROOT_DIRS`` and the exact ``ROOT_FILES``.
    Excluded: generated caches, VCS metadata and publishing outputs by documented name.
    Git ignore rules are not used: a source file is hashed even if Git ignores it.
    Symlinks, missing declared roots and unreadable files raise instead of being skipped.
    """
    root = Path(project_root).resolve()
    entries = {}
    for name in ROOT_FILES:
        path = root / name
        if not path.exists():
            raise SourceIdentityError(f"declared execution input is missing: {name}")
        if path.is_symlink() or not path.is_file():
            raise SourceIdentityError(f"declared execution input is not a regular file: {name}")
        entries[name] = _hash_file(path, name)
    for name in ROOT_DIRS:
        base = root / name
        if not base.is_dir() or base.is_symlink():
            raise SourceIdentityError(f"declared execution root is missing or a symlink: {name}")
        for directory, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIR_NAMES)
            for child in dirnames:
                if (Path(directory) / child).is_symlink():
                    relative = (Path(directory) / child).relative_to(root).as_posix()
                    raise SourceIdentityError(
                        f"symlinked directory is not allowed in declared inputs: {relative}")
            for filename in sorted(filenames):
                path = Path(directory) / filename
                if filename in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
                    continue
                if path.is_symlink():
                    relative = path.relative_to(root).as_posix()
                    raise SourceIdentityError(
                        f"symlinked file is not allowed in declared inputs: {relative}")
                if not path.is_file():
                    relative = path.relative_to(root).as_posix()
                    raise SourceIdentityError(
                        f"declared execution input is not a regular file: {relative}")
                relative = path.relative_to(root).as_posix()
                entries[relative] = _hash_file(path, relative)
    if len(entries) != len(set(entries)):
        raise SourceIdentityError("declared execution inputs contain duplicate paths")
    return {"roots": list(ROOTS), "files": entries, "count": len(entries),
            "digest": canonical_digest({"roots": list(ROOTS), "files": entries})}


def observe_commit(project_root) -> str | None:
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_root,
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    value = done.stdout.strip()
    return value if done.returncode == 0 and _SHA.match(value) else None


def observe_status(project_root, *, include_untracked: bool) -> str | None:
    command = ["git", "status", "--porcelain"]
    if not include_untracked:
        command.append("--untracked-files=no")
    try:
        done = subprocess.run(command, cwd=project_root, capture_output=True, text=True,
                              timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout


def _git(project_root, *args) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=project_root, capture_output=True,
                              text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SourceIdentityError(f"Git metadata could not be collected: {exc}") from None
    if done.returncode != 0:
        message = (done.stderr or done.stdout).strip().splitlines()[:1]
        raise SourceIdentityError(
            "Git metadata could not be collected: " + (message[0] if message else "git failed"))
    return done.stdout


def _split_paths(output: str) -> list[str]:
    return [item for item in output.split("\x00") if item]


def collect_metadata(project_root) -> dict:
    """Host-side Git metadata. Requires a readable checkout (linked worktree is fine)."""
    root = Path(project_root)
    commit = _git(root, "rev-parse", "HEAD").strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").strip()
    if not _SHA.match(commit) or not _SHA.match(tree):
        raise SourceIdentityError("Git returned an unexpected commit or tree identifier")
    staged = sorted(_split_paths(_git(root, "diff", "--cached", "--name-only", "-z")))
    unstaged = sorted(_split_paths(_git(root, "diff", "--name-only", "-z")))
    untracked = sorted(_split_paths(
        _git(root, "ls-files", "--others", "--exclude-standard", "-z")))
    for path in staged + unstaged + untracked:
        _relative_path(path)
    untracked_inputs = [path for path in untracked if _declared(path)]
    return {
        "commit": commit, "tree": tree,
        "staged": staged, "unstaged": unstaged,
        "untracked": untracked, "untracked_inputs": untracked_inputs,
        "tracked_dirty": bool(staged or unstaged),
    }


def collect(project_root, destination) -> dict:
    """Collect and write the host record. Never writes inside the declared inputs."""
    root = Path(project_root).resolve()
    destination = Path(destination)
    target = (root / destination).resolve() if not destination.is_absolute() else destination.resolve()
    for declared in ROOTS:
        declared_path = (root / declared).resolve()
        if target == declared_path or declared_path in target.parents:
            raise SourceIdentityError(
                "the source-identity record must not be written inside the declared inputs")
    if target.exists() and target.is_symlink():
        raise SourceIdentityError("refusing to replace a symlinked source-identity record")
    metadata = collect_metadata(root)
    manifest = content_manifest(root)
    untracked = metadata["untracked"]
    record = {
        "schema": SCHEMA,
        "origin": "host-supplied",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": {"commit": metadata["commit"], "tree": metadata["tree"]},
        "worktree": {
            "tracked_dirty": metadata["tracked_dirty"],
            "staged": metadata["staged"],
            "unstaged": metadata["unstaged"],
            "untracked_inputs": metadata["untracked_inputs"],
            "untracked_outside_count": len(untracked) - len(metadata["untracked_inputs"]),
        },
        "content": manifest,
        "limits": LIMITS,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".source-identity-", dir=target.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(record, stream, indent=1, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return record


def _require(condition, message):
    if not condition:
        raise SourceIdentityError(message)


def load_supplied(path) -> dict:
    """Read and strictly validate a host record. Any defect is fatal for the run."""
    source = Path(path)
    if source.is_symlink():
        raise SourceIdentityError("the supplied source-identity record is a symlink; refusing it")
    if not source.is_file():
        raise SourceIdentityError("the supplied source-identity record is missing or unreadable")
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise SourceIdentityError(
            f"the supplied source-identity record cannot be inspected: {exc.strerror or exc}") from None
    if size > MAX_RECORD_BYTES:
        raise SourceIdentityError(
            f"the supplied source-identity record is too large ({size} bytes; limit {MAX_RECORD_BYTES})")
    try:
        record = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SourceIdentityError(
            f"the supplied source-identity record is not valid JSON: {exc}") from None
    _require(isinstance(record, dict), "the supplied source-identity record must be a JSON object")
    _require(set(record) == {"schema", "origin", "collected_at_utc", "git", "worktree",
                             "content", "limits"},
             "the supplied source-identity record has unexpected or missing keys")
    _require(record["schema"] == SCHEMA,
             f"unsupported source-identity schema: {record['schema']!r}")
    _require(record["origin"] == "host-supplied",
             "the supplied source-identity record does not declare a host-supplied origin")
    try:
        collected = datetime.fromisoformat(record["collected_at_utc"])
    except (TypeError, ValueError):
        raise SourceIdentityError("the supplied source-identity record has an invalid collection time") from None
    _require(collected.utcoffset() is not None, "the collection time must include a UTC offset")
    git = record["git"]
    _require(isinstance(git, dict) and set(git) == {"commit", "tree"},
             "the supplied source-identity record has an invalid git block")
    _require(isinstance(git["commit"], str) and _SHA.match(git["commit"]),
             "the supplied commit identifier is not a hexadecimal object id")
    _require(isinstance(git["tree"], str) and _SHA.match(git["tree"]),
             "the supplied tree identifier is not a hexadecimal object id")
    worktree = record["worktree"]
    _require(isinstance(worktree, dict) and set(worktree) == {
        "tracked_dirty", "staged", "unstaged", "untracked_inputs", "untracked_outside_count"},
        "the supplied source-identity record has an invalid worktree block")
    _require(isinstance(worktree["tracked_dirty"], bool),
             "tracked_dirty must be a boolean")
    for key in ("staged", "unstaged", "untracked_inputs"):
        _require(isinstance(worktree[key], list), f"worktree.{key} must be a list")
        for item in worktree[key]:
            _relative_path(item)
    _require(isinstance(worktree["untracked_outside_count"], int)
             and not isinstance(worktree["untracked_outside_count"], bool)
             and worktree["untracked_outside_count"] >= 0,
             "untracked_outside_count must be a non-negative integer")
    if worktree["tracked_dirty"] != bool(worktree["staged"] or worktree["unstaged"]):
        raise SourceIdentityError("tracked_dirty disagrees with the recorded staged/unstaged paths")
    for item in worktree["untracked_inputs"]:
        _require(_declared(item),
                 f"untracked_inputs names a path outside the declared inputs: {item}")
    content = record["content"]
    _require(isinstance(content, dict) and set(content) == {"roots", "files", "count", "digest"},
             "the supplied source-identity record has an invalid content block")
    _require(content["roots"] == list(ROOTS),
             "the supplied content roots do not match this runtime's declared execution inputs")
    files = content["files"]
    _require(isinstance(files, dict), "content.files must be an object")
    for name, value in files.items():
        _relative_path(name)
        _require(_declared(name),
                 f"content.files names a path outside the declared inputs: {name}")
        _require(isinstance(value, str) and _HEX64.match(value),
                 f"content.files[{name!r}] is not a SHA-256 digest")
    _require(isinstance(content["count"], int) and not isinstance(content["count"], bool)
             and content["count"] == len(files),
             "content.count disagrees with content.files")
    _require(content["digest"] == canonical_digest({"roots": list(ROOTS), "files": files}),
             "content.digest does not match content.files")
    return record


def _compare(supplied: dict, current: dict) -> None:
    _require(supplied["roots"] == current["roots"],
             "the supplied content roots do not match the declared execution inputs")
    expected, observed = supplied["files"], current["files"]
    missing = sorted(set(expected) - set(observed))
    added = sorted(set(observed) - set(expected))
    changed = sorted(name for name in set(expected) & set(observed)
                     if expected[name] != observed[name])
    if missing or added or changed:
        detail = []
        if changed:
            detail.append("changed: " + ", ".join(changed[:10]))
        if added:
            detail.append("not in the supplied record: " + ", ".join(added[:10]))
        if missing:
            detail.append("missing: " + ", ".join(missing[:10]))
        raise SourceIdentityError(
            "the supplied source identity does not describe the files used at render time ("
            + "; ".join(detail) + ")")
    _require(supplied["count"] == current["count"],
             "the supplied source identity records a different input count")
    _require(supplied["digest"] == current["digest"],
             "the supplied source-identity digest does not match the recomputed content digest")


def public_record(origin: str, verification: str, *, commit=None, tree=None,
                  tracked_dirty=None, staged_count=None, unstaged_count=None,
                  untracked_inputs=None, untracked_outside=None, manifest=None,
                  collected_at=None) -> dict:
    return {
        "schema": SCHEMA,
        "origin": origin,
        "verification": verification,
        "commit": commit,
        "tree": tree,
        "tracked_dirty": tracked_dirty,
        "staged_count": staged_count,
        "unstaged_count": unstaged_count,
        "untracked_inputs": untracked_inputs,
        "untracked_outside_inputs": untracked_outside,
        "content": ({"roots": manifest["roots"], "count": manifest["count"],
                     "digest": manifest["digest"]} if manifest else None),
        "collected_at_utc": collected_at,
        "limits": LIMITS,
    }


def resolve(project_root, supplied_path=None) -> dict:
    """Resolve the identity used by a run. Invalid supplied records fail the run."""
    chosen = supplied_path or os.environ.get(ENV_VAR)
    if chosen:
        supplied = load_supplied(chosen)
        current = content_manifest(project_root)
        _compare(supplied["content"], current)
        worktree = supplied["worktree"]
        return public_record(
            "host-supplied", "supplied-digest-match",
            commit=supplied["git"]["commit"], tree=supplied["git"]["tree"],
            tracked_dirty=worktree["tracked_dirty"],
            staged_count=len(worktree["staged"]),
            unstaged_count=len(worktree["unstaged"]),
            untracked_inputs=len(worktree["untracked_inputs"]),
            untracked_outside=worktree["untracked_outside_count"],
            manifest=current, collected_at=supplied["collected_at_utc"])
    current = content_manifest(project_root)
    commit = observe_commit(project_root)
    status = observe_status(project_root, include_untracked=False)
    if commit is None:
        return public_record("unavailable", "computed-in-runtime", manifest=current)
    tree = None
    tracked_dirty = None
    staged = unstaged = 0
    try:
        metadata = collect_metadata(project_root)
        tree = metadata["tree"]
        tracked_dirty = metadata["tracked_dirty"]
        staged, unstaged = len(metadata["staged"]), len(metadata["unstaged"])
        untracked_inputs = len(metadata["untracked_inputs"])
        untracked_outside = len(metadata["untracked"]) - untracked_inputs
    except SourceIdentityError:
        untracked_inputs = untracked_outside = None
    return public_record(
        "runtime-git", "computed-in-runtime", commit=commit, tree=tree,
        tracked_dirty=tracked_dirty, staged_count=staged, unstaged_count=unstaged,
        untracked_inputs=untracked_inputs, untracked_outside=untracked_outside,
        manifest=current)


def assert_unchanged(public, project_root) -> None:
    """Detect declared-input changes across the generation/publication boundary.

    This is a before/after check, not continuous monitoring: a change after the final
    check is not observed.
    """
    if not isinstance(public, dict):
        return
    content = public.get("content")
    if not isinstance(content, dict) or not content.get("digest"):
        return
    current = content_manifest(project_root)
    if current["digest"] != content.get("digest") or current["count"] != content.get("count"):
        expected = content.get("digest", "")
        changed = []
        # Recompute against the summary only: name the first few differing paths.
        # The summary omits the map, so report counts and digests instead of paths.
        raise SourceIdentityError(
            "declared execution inputs changed during generation; refusing to publish "
            f"(recorded digest {expected[:16]}…, current {current['digest'][:16]}…, "
            f"count {content.get('count')} -> {current['count']})")


def derive_state(code) -> dict:
    """Reader-facing source state. Existing categories and wording are preserved.

    A host-supplied identity is never upgraded to "clean" merely because reported
    staged/unstaged paths are empty: untracked files outside the declared inputs still
    mean the worktree is not wholly clean, so that case is reported conservatively.
    """
    code = code if isinstance(code, dict) else {}
    identity = code.get("source_identity")
    commit = code.get("git_commit")
    clean = code.get("git_worktree_clean")
    short = commit[:12] if isinstance(commit, str) and commit else None
    availability = ("This package contains neither the source checkout nor the container image; "
                    "both must be supplied separately before either can be inspected.")
    if isinstance(identity, dict) and identity.get("origin") == "host-supplied":
        supplied = identity.get("commit")
        supplied_short = supplied[:12] if isinstance(supplied, str) and supplied else "not recorded"
        tracked = identity.get("tracked_dirty")
        inputs = identity.get("untracked_inputs")
        outside = identity.get("untracked_outside_inputs")
        if identity.get("verification") != "supplied-digest-match":
            return {"state": "unknown", "commit": supplied,
                    "label": "source identity not verified",
                    "detail": ("Source state recorded at render time: a host-supplied identity "
                               "was present but its content digest was not verified; source "
                               "identity is unverified and this is not evidence of a clean tree."),
                    "availability": availability}
        if tracked or (isinstance(inputs, int) and inputs > 0):
            return {"state": "uncommitted", "commit": supplied,
                    "label": "uncommitted changes present",
                    "detail": (f"Source state recorded at render time: host-reported commit "
                               f"{supplied_short} with tracked changes and/or untracked execution "
                               f"inputs present; the declared input content digest was verified in "
                               f"the runtime. The Git commit is an external assertion."),
                    "availability": availability}
        if isinstance(outside, int) and outside > 0:
            return {"state": "uncommitted", "commit": supplied,
                    "label": "untracked files outside execution inputs",
                    "detail": (f"Source state recorded at render time: host-reported commit "
                               f"{supplied_short}; tracked changes none; no untracked execution "
                               f"inputs; {outside} untracked path(s) outside the declared inputs "
                               f"(not part of this content claim); declared input content digest "
                               f"verified in the runtime. The worktree is not wholly clean and the "
                               f"Git commit is an external assertion."),
                    "availability": availability}
        return {"state": "clean", "commit": supplied,
                "label": "clean worktree at the recorded commit",
                "detail": (f"Source state recorded at render time: host-reported commit "
                           f"{supplied_short}; no tracked changes and no untracked files; declared "
                           f"input content digest verified in the runtime. The Git commit is an "
                           f"external assertion."),
                "availability": availability}
    if clean is True and short:
        return {"state": "clean", "commit": commit,
                "label": "clean worktree at the recorded commit",
                "detail": (f"Source state recorded at render time: clean worktree at commit {short}. "
                           "A clean commit identifies the source revision; it does not by itself "
                           "provide the source."),
                "availability": availability}
    if clean is False:
        return {"state": "uncommitted", "commit": commit,
                "label": "uncommitted changes present",
                "detail": (f"Source state recorded at render time: commit {short or 'not recorded'} "
                           "with uncommitted changes present. The Git SHA alone does not identify "
                           "the full working-tree source."),
                "availability": availability}
    return {"state": "unknown", "commit": commit,
            "label": "source state not determined",
            "detail": ("Source state recorded at render time: not determined, because the Git "
                       "state could not be read. Source identity is therefore unverified; this "
                       "is not evidence of a clean tree."),
            "availability": availability}


def verify_record(project_root, path) -> dict:
    """Validate a supplied record against the current tree (CLI helper)."""
    supplied = load_supplied(path)
    _compare(supplied["content"], content_manifest(project_root))
    return supplied


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Collect or verify reporting source identity")
    commands = parser.add_subparsers(dest="command", required=True)
    collect_parser = commands.add_parser("collect", help="collect a host record")
    collect_parser.add_argument("--project", default=".")
    collect_parser.add_argument("--out", required=True)
    verify_parser = commands.add_parser("verify", help="verify a record against a tree")
    verify_parser.add_argument("--project", default=".")
    verify_parser.add_argument("--identity", required=True)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "collect":
            record = collect(arguments.project, arguments.out)
            print(json.dumps({"commit": record["git"]["commit"],
                              "tree": record["git"]["tree"],
                              "content_digest": record["content"]["digest"],
                              "content_count": record["content"]["count"],
                              "tracked_dirty": record["worktree"]["tracked_dirty"],
                              "untracked_inputs": len(record["worktree"]["untracked_inputs"]),
                              "untracked_outside_inputs":
                                  record["worktree"]["untracked_outside_count"]},
                             indent=1, sort_keys=True))
        else:
            record = verify_record(arguments.project, arguments.identity)
            print(json.dumps({"verified": True, "commit": record["git"]["commit"],
                              "content_digest": record["content"]["digest"],
                              "content_count": record["content"]["count"]}, indent=1,
                             sort_keys=True))
    except SourceIdentityError as exc:
        print(f"source identity error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
