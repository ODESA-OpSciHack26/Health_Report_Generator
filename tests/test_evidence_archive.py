"""Evidence archive integrity and publication boundaries, not secrecy claims."""
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/health_pipeline"))

import evidence_archive as evidence  # noqa: E402


@pytest.fixture
def project(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    folder = repo / "reproduced/run"
    folder.mkdir(parents=True)
    (folder / "result.txt").write_text("reviewed synthetic evidence")
    monkeypatch.setattr(evidence, "PROJECT", repo)
    monkeypatch.setattr(evidence, "_clean_commit", lambda: "a" * 40)
    return repo, folder, tmp_path / "handover.tar.gz"


def test_archive_round_trip_without_extraction(project):
    _, _, destination = project
    evidence.create_evidence_archive(["reproduced/run"], destination, acknowledge_content=True)
    manifest = evidence.verify_evidence_archive(destination)
    assert set(manifest["artifacts"]) == {"reproduced/run/result.txt"}
    assert manifest["source_commit"] == "a" * 40
    assert manifest["browser_acceptance"].startswith("Not asserted")
    assert sorted(p.name for p in destination.parent.iterdir()) == ["handover.tar.gz", "repo"]


def test_content_acknowledgment_is_required(project):
    _, _, destination = project
    with pytest.raises(ValueError, match="Review content"):
        evidence.create_evidence_archive(["reproduced/run"], destination)
    assert not destination.exists()


@pytest.mark.parametrize("include", ["../outside", "/tmp", ".git", "docs", "reproduced/missing"])
def test_invalid_selection_rejected(project, include):
    _, _, destination = project
    with pytest.raises(ValueError):
        evidence.create_evidence_archive([include], destination, acknowledge_content=True)
    assert not destination.exists()


def test_symlink_rejected(project):
    _, folder, destination = project
    (folder / "linked").symlink_to(folder / "result.txt")
    with pytest.raises(ValueError):
        evidence.create_evidence_archive(["reproduced/run"], destination, acknowledge_content=True)


def test_archive_must_be_outside_repository(project):
    repo, _, _ = project
    with pytest.raises(ValueError, match="outside"):
        evidence.create_evidence_archive(["reproduced/run"], repo / "out.tar.gz", acknowledge_content=True)


def test_existing_archive_preserved(project):
    _, _, destination = project
    destination.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        evidence.create_evidence_archive(["reproduced/run"], destination, acknowledge_content=True)
    assert destination.read_bytes() == b"keep"


def test_failed_publication_cleans_temporary_archive(project, monkeypatch):
    _, _, destination = project
    def fail(*args):
        raise OSError("publication failed")
    monkeypatch.setattr(evidence.bundles, "_rename_no_replace", fail)
    with pytest.raises(OSError):
        evidence.create_evidence_archive(["reproduced/run"], destination, acknowledge_content=True)
    assert not destination.exists()
    assert not list(destination.parent.glob(".handover-*"))


@pytest.mark.parametrize("attack", ["changed", "duplicate", "symlink", "traversal"])
def test_archive_damage_and_unsafe_members_rejected(project, attack):
    _, _, destination = project
    evidence.create_evidence_archive(["reproduced/run"], destination, acknowledge_content=True)
    with tarfile.open(destination, "r:gz") as original:
        saved = [(member.name, original.extractfile(member).read()) for member in original.getmembers()]
    damaged = destination.parent / "damaged.tar.gz"
    with tarfile.open(damaged, "w:gz") as archive:
        for name, payload in saved:
            if attack == "changed" and name.endswith("result.txt"):
                payload += b"tampered"
            evidence._add(archive, name, payload)
        if attack == "duplicate":
            evidence._add(archive, saved[0][0], saved[0][1])
        elif attack == "symlink":
            info = tarfile.TarInfo("reproduced/link")
            info.type = tarfile.SYMTYPE
            info.linkname = "outside"
            archive.addfile(info)
        elif attack == "traversal":
            evidence._add(archive, "../outside", b"bad")
    with pytest.raises(ValueError):
        evidence.verify_evidence_archive(damaged)


def test_dirty_source_worktree_is_rejected(monkeypatch):
    monkeypatch.setattr(evidence.subprocess, "check_output", lambda *args, **kwargs: " M changed.py\n")
    with pytest.raises(ValueError, match="clean source"):
        evidence._clean_commit()


def test_source_commit_change_during_archiving_is_rejected(project, monkeypatch):
    _, _, destination = project
    commits = iter(["a" * 40, "b" * 40])
    monkeypatch.setattr(evidence, "_clean_commit", lambda: next(commits))
    with pytest.raises(ValueError, match="changed while archiving"):
        evidence.create_evidence_archive(["reproduced/run"], destination, acknowledge_content=True)
    assert not destination.exists()
    assert not list(destination.parent.glob(".handover-*"))
