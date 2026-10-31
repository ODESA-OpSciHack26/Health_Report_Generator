"""Source-state wording: derived once from recorded provenance, never inferred from a SHA.

The three states are clean committed source, source with uncommitted changes, and unknown.
Availability is a separate statement: a clean commit never implies that a reader has the
source checkout or the container image.
"""
import json
import subprocess
from pathlib import Path

import publish

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
