"""Static integrity checks for the pilot dependency inputs and build flags."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "scripts" / "health_pipeline"


def _requirements(path):
    text = (PIPE / path).read_text(encoding="utf-8")
    blocks, current = [], []
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        current.append(line.strip())
        if not line.rstrip().endswith("\\"):
            blocks.append(" ".join(current)); current = []
    return blocks


def test_runtime_lock_hashes_every_requirement_and_preserves_versions():
    blocks = _requirements("requirements.pilot.lock.txt")
    assert len(blocks) == 62
    for block in blocks:
        assert re.match(r"^[A-Za-z0-9_.-]+==", block), block
        assert "--hash=sha256:" in block, block
    connection = [block for block in blocks if block.startswith("connection-pool==")]
    assert len(connection) == 1
    assert "bf429e7aef65921c69b4ed48f3d48d3eac1383b05d2df91884705842d974d0dc" in connection[0]


def test_bootstrap_tools_are_separate_hashed_pins():
    blocks = _requirements("requirements.pilot.bootstrap.txt")
    pins = {block.split("==")[0]: block.split("==")[1].split()[0] for block in blocks}
    assert pins == {"pip": "26.2.2", "setuptools": "65.5.1", "wheel": "0.42.0"}
    assert all("--hash=sha256:" in block for block in blocks)


def test_pilot_dockerfile_enforces_hashes_and_offline_install():
    text = (ROOT / "Dockerfile.report.pilot").read_text(encoding="utf-8")
    assert "ghcr.io/astral-sh/uv:${UV_VERSION}@sha256:d97bc3f4" in text
    assert "python:3.11.6-slim-bookworm@sha256:38a28170" in text
    assert "--require-hashes" in text
    assert "--no-index" in text
    assert "--no-build-isolation" in text
    assert text.count("--network=none") >= 2
    assert "pip install --upgrade pip" not in text
    assert "requirements.pilot.bootstrap.txt" in text


def test_quarto_checksum_is_pinned_and_verified_before_extraction():
    text = (ROOT / "Dockerfile.report.pilot").read_text(encoding="utf-8")
    digest = "5c34a326f3c9fe5ecba251b1bfe840229524b6db93982478e516fa17af89dde4"
    assert f"ARG QUARTO_SHA256={digest}" in text
    assert "ARG QUARTO_BYTES=89745288" in text
    assert "sha256sum -c quarto.expected" in text
    assert text.index("sha256sum -c quarto.expected") < text.index("tar -xzf")
    assert "checksums.txt" not in text.split("RUN set -eu", 1)[1]  # no dynamic checksum fetch
    assert "Invalid QUARTO_SHA256" in text and "Quarto archive size mismatch" in text
