"""Default collection must not recurse into generated donor checkouts."""
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_default_collection_excludes_generated_checkouts(tmp_path):
    config = (ROOT / "pyproject.toml").read_text()
    parsed = tomllib.loads(config)
    assert parsed["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]

    (tmp_path / "pyproject.toml").write_text(config)
    own = tmp_path / "tests"
    own.mkdir()
    (own / "test_duplicate.py").write_text("def test_owned():\n    pass\n")

    donor = tmp_path / "reproduced/donor/tests"
    donor.mkdir(parents=True)
    (donor / "test_duplicate.py").write_text(
        'raise RuntimeError("GENERATED-CHECKOUT-WAS-COLLECTED")\n'
    )

    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_PLUGINS", None)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "tests/test_duplicate.py::test_owned" in result.stdout
    assert "GENERATED-CHECKOUT-WAS-COLLECTED" not in result.stdout + result.stderr
    assert "1 test collected" in result.stdout
