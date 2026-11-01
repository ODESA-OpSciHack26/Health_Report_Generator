"""Pilot boundary checks: no R invocation, explicit selection, no silent fallback."""
import importlib.util
import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

import tabular_render

ROOT = Path(__file__).resolve().parents[1]
PILOT = ("pilot_document.py", "pilot_charts.py", "tabular_python.py")


def test_pilot_modules_contain_no_r_invocation():
    for name in PILOT:
        text = (ROOT / "scripts" / "health_pipeline" / name).read_text(encoding="utf-8")
        assert not re.search(r"\bRscript\b|\bknitr\b|\brmarkdown\b", text), name


def test_r_is_the_default_renderer_and_selection_is_explicit():
    signature = inspect.signature(tabular_render.render_tabular_reports)
    assert signature.parameters["renderer"].default == "r"
    assert signature.parameters["source_identity_path"].default is None
    with pytest.raises(ValueError, match="Unsupported tabular renderer"):
        tabular_render.render_tabular_reports(None, None, renderer="implicit")


def test_documented_cli_exposes_renderer_selection():
    commands = (("tabular_run.py", "build"), ("tabular_render.py", None))
    for module, subcommand in commands:
        argv = [sys.executable, str(ROOT / "scripts" / "health_pipeline" / module)]
        if subcommand:
            argv.append(subcommand)
        completed = subprocess.run(argv + ["--help"], capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        assert "--renderer" in completed.stdout
        assert "{r,python}" in completed.stdout


def test_missing_pilot_dependency_is_actionable_not_a_fallback():
    if importlib.util.find_spec("matplotlib") is None:
        with pytest.raises(ValueError, match="requirements.pilot.lock.txt"):
            tabular_render._matplotlib_version()
    else:
        assert tabular_render._matplotlib_version().split(".")[0].isdigit()


def test_verifier_v1_does_not_import_pilot_modules():
    completed = subprocess.run(
        [sys.executable, "-c", "import sys, tabular_render; tabular_render.verify_tabular_reports; "
                               "print('matplotlib' in sys.modules)"],
        cwd=ROOT / "scripts" / "health_pipeline", capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False"
