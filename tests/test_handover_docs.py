"""Active handover instructions must remain safe and current."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_setup_clone_is_a_plain_command_for_current_repository():
    text = (ROOT / "GETTING_STARTED.md").read_text()
    commands = re.findall(r"^git clone (.+)$", text, re.MULTILINE)
    assert commands == [
        "https://github.com/ODESA-OpSciHack26/Health_Report_Generator.git"
    ]
    assert "git switch integration/steward-ready-v1" in text


def test_release_checklist_preserves_existing_version_and_licence():
    text = (ROOT / "docs/release-checklist.md").read_text()
    assert "MIT" in text
    assert (ROOT / "LICENSE").read_text().startswith("MIT License")
    assert "Preserve the original `release/v1.0.0`" in text
    assert not re.search(r"^\s*git (?:tag|push)\b", text, re.MULTILINE)
    assert "github.com/LarsEBaumann/Health_Report_Generator" not in text


def test_handover_links_evidence_without_claiming_merge_reexecution():
    text = (ROOT / "docs/handover.md").read_text()
    for milestone in ("m0", "m1", "m2", "m3"):
        assert f"evidence/{milestone}/" in text
        assert (ROOT / "docs/evidence" / milestone).is_dir()
    assert "not a\nnew execution against the integration merge commit" in text
    assert "187 Python tests" in text
    assert "pre-commit evidence" in text


def test_setup_distinguishes_the_two_optional_interfaces():
    text = (ROOT / "GETTING_STARTED.md").read_text()
    assert "docs/local-interface.md" in text
    assert "CONNECTOR_SETUP.md" in text
    assert "Neither interface is required" in text
