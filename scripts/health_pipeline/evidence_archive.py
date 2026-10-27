"""Create/verify an explicit local evidence archive; never extract its files."""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import platform
import re
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import tabular_bundle as bundles

PROJECT = Path(__file__).resolve().parents[2]
SCHEMA = "health-report/evidence-archive/1"
MANIFEST = "handover-manifest.json"


def _clean_commit():
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=PROJECT, text=True)
    if status.strip():
        raise ValueError("Evidence archiving requires a clean source worktree.")
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip()


def _members(includes):
    if not includes:
        raise ValueError("Select at least one evidence path explicitly.")
    selected = {}
    for name in includes:
        relative = Path(name)
        if (relative.is_absolute() or ".." in relative.parts
                or not relative.parts or relative.parts[0] != "reproduced"
                or ".git" in relative.parts):
            raise ValueError("Include paths must stay under reproduced/.")
        root = bundles._safe_path(PROJECT / relative)
        if not root.exists():
            raise ValueError(f"Selected evidence is missing: {name}")
        paths = [root, *root.rglob("*")] if root.is_dir() else [root]
        for path in paths:
            if path.is_symlink() or ".git" in path.relative_to(PROJECT).parts:
                raise ValueError("Symlinks and Git metadata are not archived.")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError("Only regular evidence files are supported.")
            selected[path.relative_to(PROJECT).as_posix()] = path
    if not selected:
        raise ValueError("Selected paths contain no evidence files.")
    return selected


def _add(archive, name, payload):
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o644
    info.mtime = 0
    archive.addfile(info, io.BytesIO(payload))


def verify_evidence_archive(path):
    """Inspect members as streams; no filesystem extraction occurs.

    No decompression/resource-limit or hostile-archive security acceptance is
    claimed. Use with the explicitly created local handover archives.
    """
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(set(names)) != len(names) or MANIFEST not in names:
            raise ValueError("Duplicate members or missing handover manifest.")
        for member in members:
            name = PurePosixPath(member.name)
            if (not member.isfile() or name.is_absolute() or ".." in name.parts
                    or "\\" in member.name or name.as_posix() != member.name):
                raise ValueError("Unsafe archive member.")
        manifest = bundles._json_load(archive.extractfile(MANIFEST).read())
        keys = {"schema", "created_at_utc", "source_commit", "python",
                "source_availability", "content_review_acknowledged", "browser_acceptance",
                "selected_paths", "artifacts"}
        if not isinstance(manifest, dict) or set(manifest) != keys or manifest["schema"] != SCHEMA:
            raise ValueError("Invalid handover manifest.")
        if (not isinstance(manifest["source_commit"], str)
                or not re.fullmatch(r"[0-9a-f]{40,64}", manifest["source_commit"])
                or manifest["content_review_acknowledged"] is not True):
            raise ValueError("Invalid archive source/content-review metadata.")
        artifacts = manifest["artifacts"]
        if not isinstance(artifacts, dict) or set(artifacts) != set(names) - {MANIFEST}:
            raise ValueError("Archive artifact set disagrees with manifest.")
        for name, description in artifacts.items():
            if not name.startswith("reproduced/"):
                raise ValueError("Unexpected archive artifact root.")
            payload = archive.extractfile(name).read()
            if (not isinstance(description, dict) or set(description) != {"bytes", "sha256"}
                    or type(description["bytes"]) is not int
                    or description["bytes"] != len(payload)
                    or description["sha256"] != hashlib.sha256(payload).hexdigest()):
                raise ValueError("Archive artifact hash/size mismatch.")
    return manifest


def create_evidence_archive(includes, destination, *, acknowledge_content=False):
    """Capture selected file bytes once, verify archive, publish without replacement."""
    if acknowledge_content is not True:
        raise ValueError("Review content before acknowledging archiving original data/logs.")
    commit = _clean_commit()
    selected = _members(includes)
    destination = bundles._safe_path(destination)
    project = PROJECT.resolve()
    if destination == project or project in destination.parents:
        raise ValueError("Evidence archive must be outside the Git repository.")
    if not destination.parent.is_dir() or not destination.name:
        raise ValueError("An existing archive parent and named destination are required.")
    if os.path.lexists(destination):
        raise FileExistsError(str(destination))
    descriptor, temporary = tempfile.mkstemp(prefix=".handover-", suffix=".tar.gz",
                                            dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        artifacts = {}
        with tarfile.open(temporary, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            for name, path in sorted(selected.items()):
                payload = bundles._read_regular(path)
                artifacts[name] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                _add(archive, name, payload)
            manifest = {
                "schema": SCHEMA,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_commit": commit, "python": platform.python_version(),
                "source_availability": "Local archiver checkout; artifact generation revisions remain in run provenance. Remote availability is not asserted.",
                "content_review_acknowledged": True,
                "browser_acceptance": "Not asserted; consult included human review records.",
                "selected_paths": list(includes), "artifacts": artifacts,
            }
            _add(archive, MANIFEST, bundles._json_bytes(manifest))
        verify_evidence_archive(temporary)
        if _clean_commit() != commit:
            raise ValueError("Source checkout changed while archiving.")
        bundles._rename_no_replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    create = commands.add_parser("create")
    create.add_argument("--include", action="append", required=True)
    create.add_argument("--output", required=True)
    create.add_argument("--acknowledge-content-review", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("archive")
    args = parser.parse_args(argv)
    try:
        if args.action == "create":
            path = create_evidence_archive(args.include, args.output,
                acknowledge_content=args.acknowledge_content_review)
            print("Verified local evidence archive:", path)
            print("SHA256:", hashlib.sha256(path.read_bytes()).hexdigest())
        else:
            manifest = verify_evidence_archive(args.archive)
            print("Verified archived artifacts:", len(manifest["artifacts"]))
    except (ValueError, OSError, tarfile.TarError, NotImplementedError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
