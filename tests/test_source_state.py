"""Source-state wording: derived once from recorded provenance, never inferred from a SHA.

The three states are clean committed source, source with uncommitted changes, and unknown.
Availability is a separate statement: a clean commit never implies that a reader has the
source checkout or the container image.
"""
import json
import subprocess
from pathlib import Path

import pytest

import publish
import source_identity

CLEAN_SHA = "8e8ad84c99d9d877e574cde15b6aaf74d141b6b2"


def _code(commit=CLEAN_SHA, clean: "bool | None" = True):
    code = {"git_commit": commit, "git_worktree_clean": clean, "workflow_config": None}
    code["source_state"] = publish.source_state_record(code)
    return code


def test_clean_committed_state_is_reported_with_its_limits():
    state = publish.source_state_record({"git_commit": CLEAN_SHA, "git_worktree_clean": True})
    assert state["state"] == "clean"
    assert state["commit"] == CLEAN_SHA
    assert "clean worktree at commit 8e8ad84c99d9" in state["detail"]
    # A clean commit is not presented as delivering the source to a reader.
    assert "does not by itself provide the source" in state["detail"]
    assert state["availability"] == publish.SOURCE_STATE_AVAILABILITY


def test_dirty_state_is_never_described_as_clean():
    state = publish.source_state_record({"git_commit": CLEAN_SHA, "git_worktree_clean": False})
    assert state["state"] == "uncommitted"
    assert state["label"] == "uncommitted changes present"
    assert "uncommitted changes present" in state["detail"]
    assert "does not identify the full working-tree source" in state["detail"]
    assert "clean worktree" not in state["detail"]


def test_unknown_state_covers_null_and_missing_git_detection():
    cases = [
        {"git_commit": CLEAN_SHA, "git_worktree_clean": None},   # git status unreadable
        {"git_commit": None, "git_worktree_clean": None},        # no git at all
        {"git_commit": CLEAN_SHA},                               # flag absent
        {},                                                      # nothing recorded
        None,                                                    # not a mapping
    ]
    for code in cases:
        state = publish.source_state_record(code)
        assert state["state"] == "unknown", code
        assert "not determined" in state["detail"]
        # Unknown must not read as a pass.
        assert "not evidence of a clean tree" in state["detail"]
        assert state["availability"] == publish.SOURCE_STATE_AVAILABILITY


def test_clean_requires_both_a_commit_and_a_clean_flag():
    assert publish.source_state_record({"git_commit": None, "git_worktree_clean": True})["state"] == "unknown"
    assert publish.source_state_record({"git_commit": "", "git_worktree_clean": True})["state"] == "unknown"


def test_availability_is_stated_separately_from_cleanliness():
    state = publish.source_state_record({"git_commit": CLEAN_SHA, "git_worktree_clean": True})
    availability = state["availability"].lower()
    assert "neither the source checkout nor the container image" in availability
    assert "supplied separately" in availability
    # The two concepts are distinct statements, not one blended claim.
    assert state["detail"] != state["availability"]
    assert state["availability"] not in state["detail"]


def test_reproduction_record_reuses_the_recorded_state():
    code = _code()
    state = publish.reproduction_source_state({"code": code})
    assert state == code["source_state"]
    assert state["state"] == "clean"


def test_reproduction_record_never_infers_clean_without_a_record():
    for provenance in (None, {}, {"code": {}}, {"code": {"git_worktree_clean": None}}):
        state = publish.reproduction_source_state(provenance)
        assert state["state"] == "unknown", provenance


def test_provenance_and_reproduction_record_agree(tmp_path, monkeypatch):
    from test_composer_series import build_series_bundle, write_recipe

    bundle = build_series_bundle(tmp_path)
    work = tmp_path / "render"
    work.mkdir()
    recipe = write_recipe(work, [{"block": "intro", "instance_id": "intro-0001"}])

    monkeypatch.setattr(publish, "package",
                        lambda source, dest: Path(dest).mkdir(parents=True, exist_ok=True))

    def fake_run(command, cwd=None, check=True, env=None):
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish.subprocess, "run", fake_run)

    code = _code()
    sidecar = {"schema": "test", "code": code}
    publish.render(bundle["bundle"], work / "report.html", "html", "quarto",
                   sidecar, work / "provenance.json", recipe)

    record = json.loads((work / "reproduction" / "reproduction.json").read_text())
    assert record["source_state_status"] == "clean"
    # The published sentence is exactly the provenance wording: no second claim to drift.
    assert record["source_state"] == f"{code['source_state']['detail']} {code['source_state']['availability']}"
    assert record["source_availability"] == code["source_state"]["availability"]


def test_published_reproduction_record_for_dirty_and_unknown_states(tmp_path, monkeypatch):
    from test_composer_series import build_series_bundle, write_recipe

    for clean, expected in ((False, "uncommitted"), (None, "unknown")):
        root = tmp_path / f"case-{expected}"
        root.mkdir()
        bundle = build_series_bundle(root)
        work = root / "render"
        work.mkdir()
        recipe = write_recipe(work, [{"block": "intro", "instance_id": "intro-0001"}])
        monkeypatch.setattr(publish, "package",
                            lambda source, dest: Path(dest).mkdir(parents=True, exist_ok=True))

        def fake_run(command, cwd=None, check=True, env=None):
            (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
            return subprocess.CompletedProcess(command, 0)

        monkeypatch.setattr(publish.subprocess, "run", fake_run)
        code = _code(clean=clean)
        publish.render(bundle["bundle"], work / "report.html", "html", "quarto",
                       {"schema": "test", "code": code}, work / "provenance.json", recipe)
        record = json.loads((work / "reproduction" / "reproduction.json").read_text())
        assert record["source_state_status"] == expected
        assert code["source_state"]["detail"] in record["source_state"]


def _project_and_bundle(tmp_path):
    import hashlib
    from test_composer_series import build_series_bundle
    from test_source_identity import make_project, record_for

    project = make_project(tmp_path / "project")
    bundle = build_series_bundle(tmp_path / "case")
    root = bundle["bundle"]
    sources = root / "sources.csv"
    sources.write_text(
        "source_file,metadata_file,sha256,metadata_sha256,snapshot_id,dataset_id,topic,"
        "source_system,publishing_date,rows,status,detail,used\n"
        "data/virus/data.csv,data/virus/metadata.json," + "b" * 64 + "," + "c" * 64 +
        "," + "d" * 64 + ",ds1,virus,mandatory_reporting_system,2026-01-01,4,ok,,True\n")
    checks = root / "checks.csv"
    checks.write_text("dataset_id,check,status,detail\nds1,no_duplicate_rows,PASS,0\n")
    manifest = json.loads((root / "bundle.json").read_text())
    manifest["snapshot_id"] = json.loads((root / "snapshot.json").read_text())["snapshot_id"]
    for name in ("sources.csv", "checks.csv"):
        manifest["files"][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    (root / "bundle.json").write_text(json.dumps(manifest))
    return project, bundle, record_for(project, tmp_path)


def test_build_provenance_verifies_supplied_identity(tmp_path, monkeypatch):
    project, bundle, identity = _project_and_bundle(tmp_path)
    monkeypatch.setattr(publish, "PROJECT", project)
    html = publish.build_provenance(bundle["bundle"], "html",
                                    source_identity_path=identity)
    pdf = publish.build_provenance(bundle["bundle"], "pdf",
                                   source_identity_path=identity)
    for record in (html, pdf):
        source = record["code"]["source_identity"]
        assert source["origin"] == "host-supplied"
        assert source["verification"] == "supplied-digest-match"
        assert source["content"]["digest"] == json.loads(Path(identity).read_text())[
            "content"]["digest"]
        assert record["code"]["source_state"]["state"] == "clean"
        assert record["code"]["git_commit"] == source["commit"]
        assert "files" not in source["content"]
    assert html["code"]["source_identity"]["content"]["digest"] == \
        pdf["code"]["source_identity"]["content"]["digest"]


def test_build_provenance_fails_closed_on_invalid_supplied_identity(tmp_path, monkeypatch):
    project, bundle, identity = _project_and_bundle(tmp_path)
    monkeypatch.setattr(publish, "PROJECT", project)
    payload = json.loads(Path(identity).read_text())
    payload["content"]["count"] = 1
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(payload))
    with pytest.raises(source_identity.SourceIdentityError):
        publish.build_provenance(bundle["bundle"], "html", source_identity_path=broken)


def test_build_provenance_fails_closed_without_git_and_no_identity(tmp_path, monkeypatch):
    project, bundle, _ = _project_and_bundle(tmp_path)
    plain = tmp_path / "no-git"
    from test_source_identity import FILES
    from test_source_identity import _write
    _write(plain, FILES)
    monkeypatch.setattr(publish, "PROJECT", plain)
    record = publish.build_provenance(bundle["bundle"], "html")
    source = record["code"]["source_identity"]
    assert source["origin"] == "unavailable"
    assert source["commit"] is None
    assert source["content"]["digest"]
    assert record["code"]["source_state"]["state"] == "unknown"


def test_render_refuses_when_inputs_change_after_provenance(tmp_path, monkeypatch):
    project, bundle, identity = _project_and_bundle(tmp_path)
    monkeypatch.setattr(publish, "PROJECT", project)
    monkeypatch.setattr(publish, "build_block", lambda *args, **kwargs: {"status": "verified"})
    record = publish.build_provenance(bundle["bundle"], "html",
                                      source_identity_path=identity)
    work = tmp_path / "render"
    work.mkdir()
    monkeypatch.setattr(publish, "package",
                        lambda source, dest: Path(dest).mkdir(parents=True, exist_ok=True))

    def fake_run(command, cwd=None, check=True, env=None):
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    (project / "workflow" / "config.yaml").write_text("out: changed\n")
    with pytest.raises(source_identity.SourceIdentityError):
        publish.render(bundle["bundle"], work / "report.html", "html", "quarto",
                       record, work / "provenance.json")
    assert not (work / "report.html").exists()
    assert not (work / "provenance.json").exists()


def test_release_records_identity_and_fails_closed(tmp_path, monkeypatch):
    import release
    from test_source_identity import make_project, record_for

    project = make_project(tmp_path / "project")
    (project / "tests").mkdir()
    (project / "scripts" / "health_pipeline").mkdir()
    (project / "scripts" / "health_pipeline" / "step.py").write_text("x = 1\n")
    out = project / "results"
    out.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setattr(release, "command", lambda args: "test")
    identity = record_for(project, tmp_path)

    record = release.build_release(out, source_identity_path=identity)
    saved = json.loads((out / "release.json").read_text())
    assert saved["source_identity"]["origin"] == "host-supplied"
    assert saved["source_identity"]["content"]["digest"] == \
        record["source_identity"]["content"]["digest"]
    assert saved["git_commit"] == saved["source_identity"]["commit"]

    payload = json.loads(Path(identity).read_text())
    payload["git"]["commit"] = "z" * 40
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(payload))
    (out / "release.json").unlink()
    with pytest.raises(source_identity.SourceIdentityError):
        release.build_release(out, source_identity_path=broken)
    assert not (out / "release.json").exists()
