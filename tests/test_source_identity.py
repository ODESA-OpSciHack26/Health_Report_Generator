"""Source-identity collection, verification and fail-closed behavior."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import source_identity as si

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "Snakefile": "rule all:\n    input: []\n",
    ".Rprofile": "options(warn=1)\n",
    "renv.lock": "{}\n",
    "pyproject.toml": "[project]\nname='probe'\n",
    "Dockerfile.report": "FROM scratch\n",
    "scripts/pipeline.py": "print('pipeline')\n",
    "workflow/config.yaml": "out: results\n",
    "src/service.py": "print('service')\n",
}


def _write(root: Path, files=None):
    for name, content in (files or FILES).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _git(root: Path, *args):
    return subprocess.run(["git", "-c", "user.name=Probe", "-c", "user.email=probe@example.invalid",
                           *args], cwd=root, check=True, capture_output=True, text=True)


def make_project(root: Path, files=None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write(root, files)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "probe")
    return root


def record_for(project: Path, tmp_path: Path, name="identity.json") -> Path:
    target = tmp_path / name
    si.collect(project, target)
    return target


def test_manifest_is_deterministic_and_ignores_generated_caches(tmp_path):
    project = make_project(tmp_path / "project")
    first = si.content_manifest(project)
    (project / "scripts" / "__pycache__").mkdir()
    (project / "scripts" / "__pycache__" / "pipeline.pyc").write_bytes(b"cache")
    (project / ".pytest_cache").mkdir()
    (project / ".pytest_cache" / "x").write_text("cache")
    second = si.content_manifest(project)
    assert first == second
    assert first["count"] == len(FILES)
    assert "scripts/pipeline.py" in first["files"]


def test_manifest_hashes_git_ignored_source_files(tmp_path):
    project = make_project(tmp_path / "project")
    (project / ".gitignore").write_text("workflow/local.yaml\n")
    (project / "workflow" / "local.yaml").write_text("keep: me\n")
    manifest = si.content_manifest(project)
    assert "workflow/local.yaml" in manifest["files"]
    assert ".gitignore" not in manifest["files"]  # root file outside the declared inputs


def test_manifest_rejects_symlinked_inputs(tmp_path):
    project = make_project(tmp_path / "project")
    outside = tmp_path / "outside.py"
    outside.write_text("secret\n")
    (project / "scripts" / "linked.py").symlink_to(outside)
    with pytest.raises(si.SourceIdentityError, match="symlinked file"):
        si.content_manifest(project)


def test_manifest_rejects_missing_declared_root(tmp_path):
    project = make_project(tmp_path / "project")
    (project / "renv.lock").unlink()
    with pytest.raises(si.SourceIdentityError, match="missing"):
        si.content_manifest(project)


def test_collect_clean_checkout_and_outside_untracked(tmp_path):
    project = make_project(tmp_path / "project")
    (project / "Dockerfile.report.no-marimo").write_text("FROM scratch\n")
    record = si.collect(project, tmp_path / "identity.json")
    assert record["git"]["commit"] == _git(project, "rev-parse", "HEAD").stdout.strip()
    assert record["git"]["tree"] == _git(project, "rev-parse", "HEAD^{tree}").stdout.strip()
    assert record["worktree"]["tracked_dirty"] is False
    assert record["worktree"]["untracked_inputs"] == []
    assert record["worktree"]["untracked_outside_count"] == 1
    # The published summary must not carry private path lists.
    public = si.resolve(project, tmp_path / "identity.json")
    assert "files" not in public["content"]
    assert public["untracked_outside_inputs"] == 1
    assert public["untracked_inputs"] == 0


def test_collect_distinguishes_relevant_untracked_from_outside(tmp_path):
    project = make_project(tmp_path / "project")
    (project / "workflow" / "extra.yaml").write_text("new: true\n")
    (project / "notes.txt").write_text("outside\n")
    record = si.collect(project, tmp_path / "identity.json")
    assert record["worktree"]["untracked_inputs"] == ["workflow/extra.yaml"]
    assert record["worktree"]["untracked_outside_count"] == 1


def test_collect_reports_staged_and_unstaged_changes(tmp_path):
    project = make_project(tmp_path / "project")
    (project / "scripts" / "pipeline.py").write_text("print('changed')\n")
    _git(project, "add", "scripts/pipeline.py")
    (project / "workflow" / "config.yaml").write_text("out: other\n")
    record = si.collect(project, tmp_path / "identity.json")
    assert record["worktree"]["tracked_dirty"] is True
    assert record["worktree"]["staged"] == ["scripts/pipeline.py"]
    assert record["worktree"]["unstaged"] == ["workflow/config.yaml"]


def test_collect_works_from_a_linked_worktree(tmp_path):
    project = make_project(tmp_path / "project")
    linked = tmp_path / "linked"
    _git(project, "worktree", "add", "-q", str(linked), "-b", "probe-linked")
    record = si.collect(linked, tmp_path / "linked-identity.json")
    assert record["git"]["commit"] == _git(project, "rev-parse", "HEAD").stdout.strip()
    assert record["worktree"]["tracked_dirty"] is False


def test_collect_refuses_to_write_inside_declared_inputs(tmp_path):
    project = make_project(tmp_path / "project")
    with pytest.raises(si.SourceIdentityError, match="must not be written inside"):
        si.collect(project, project / "scripts" / "identity.json")


def test_load_rejects_malformed_records(tmp_path):
    project = make_project(tmp_path / "project")
    good = json.loads(record_for(project, tmp_path).read_text())

    def broken(name, mutate):
        payload = json.loads(json.dumps(good))
        mutate(payload)
        path = tmp_path / name
        path.write_text(json.dumps(payload))
        return path

    cases = {
        "schema": broken("schema.json", lambda d: d.update(schema="other")),
        "origin": broken("origin.json", lambda d: d.update(origin="runtime-git")),
        "commit": broken("commit.json", lambda d: d["git"].update(commit="zz")),
        "path": broken("path.json", lambda d: d["worktree"]["untracked_inputs"].append(
            "/etc/passwd")),
        "count": broken("count.json", lambda d: d["content"].update(count=1)),
        "digest": broken("digest.json", lambda d: d["content"].update(
            files={"Snakefile": "0" * 64})),
        "unknown": broken("unknown.json", lambda d: d.update(extra=1)),
    }
    for name, path in cases.items():
        with pytest.raises(si.SourceIdentityError):
            si.load_supplied(path)
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{")
    with pytest.raises(si.SourceIdentityError, match="not valid JSON"):
        si.load_supplied(bad_json)
    large = tmp_path / "large.json"
    large.write_text("x" * (si.MAX_RECORD_BYTES + 1))
    with pytest.raises(si.SourceIdentityError, match="too large"):
        si.load_supplied(large)
    with pytest.raises(si.SourceIdentityError, match="missing or unreadable"):
        si.load_supplied(tmp_path / "absent.json")


def test_resolve_verifies_supplied_digest_and_rejects_disagreement(tmp_path):
    project = make_project(tmp_path / "project")
    identity = record_for(project, tmp_path)
    public = si.resolve(project, identity)
    assert public["origin"] == "host-supplied"
    assert public["verification"] == "supplied-digest-match"
    assert public["commit"] == _git(project, "rev-parse", "HEAD").stdout.strip()

    (project / "scripts" / "pipeline.py").write_text("print('edited')\n")
    with pytest.raises(si.SourceIdentityError, match="does not describe the files"):
        si.resolve(project, identity)

    # Restore and prove a new file inside a declared root is also detected.
    (project / "scripts" / "pipeline.py").write_text(FILES["scripts/pipeline.py"])
    (project / "workflow" / "added.yaml").write_text("x: 1\n")
    with pytest.raises(si.SourceIdentityError, match="not in the supplied record"):
        si.resolve(project, identity)


def test_resolve_without_git_records_honest_unknown(tmp_path):
    project = make_project(tmp_path / "project")
    copied = tmp_path / "nogit"
    _write(copied, FILES)
    public = si.resolve(copied, None)
    assert public["origin"] == "unavailable"
    assert public["verification"] == "computed-in-runtime"
    assert public["commit"] is None
    assert public["content"]["digest"]
    state = si.derive_state({"source_identity": public})
    assert state["state"] == "unknown"
    assert "not evidence of a clean tree" in state["detail"]


def test_state_never_calls_a_worktree_with_outside_untracked_clean(tmp_path):
    project = make_project(tmp_path / "project")
    (project / "Dockerfile.report.no-marimo").write_text("FROM scratch\n")
    identity = record_for(project, tmp_path)
    public = si.resolve(project, identity)
    state = si.derive_state({"source_identity": public})
    assert state["state"] == "uncommitted"
    assert "outside the declared inputs" in state["detail"]
    assert "not wholly clean" in state["detail"]


def test_state_is_clean_only_without_any_untracked_or_tracked_change(tmp_path):
    project = make_project(tmp_path / "project")
    identity = record_for(project, tmp_path)
    public = si.resolve(project, identity)
    state = si.derive_state({"source_identity": public})
    assert state["state"] == "clean"
    assert "host-reported" in state["detail"]


def test_assert_unchanged_detects_an_edit(tmp_path):
    project = make_project(tmp_path / "project")
    public = si.resolve(project, record_for(project, tmp_path))
    (project / "workflow" / "config.yaml").write_text("out: changed\n")
    with pytest.raises(si.SourceIdentityError, match="changed during generation"):
        si.assert_unchanged(public, project)


def test_cli_exit_codes(tmp_path, capsys):
    project = make_project(tmp_path / "project")
    target = tmp_path / "identity.json"
    assert si.main(["collect", "--project", str(project), "--out", str(target)]) == 0
    assert si.main(["verify", "--project", str(project), "--identity", str(target)]) == 0
    (project / "scripts" / "pipeline.py").write_text("print('edited')\n")
    assert si.main(["verify", "--project", str(project), "--identity", str(target)]) == 1
    assert "does not describe the files" in capsys.readouterr().err
