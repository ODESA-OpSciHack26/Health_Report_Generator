"""The local UI must not require GitHub connector credentials."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_local_ui_has_no_github_token_dependency():
    content = (ROOT / "src/ui.py").read_text()
    assert "GITHUB_TOKEN" not in content
    assert "GITHUB_REPOSITORY" not in content
    assert "snakemake" in content
    assert "generic_report.py" in content
