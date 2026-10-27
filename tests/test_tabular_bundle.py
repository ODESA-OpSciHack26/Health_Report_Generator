"""Prepared bundles must be reproducible, not merely self-consistently hashed."""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/health_pipeline"))

import tabular_bundle as bundle  # noqa: E402
from tabular_prepare import prepare_table  # noqa: E402


def prepared(tmp_path, temporal=False, suffix=".csv"):
    source = tmp_path / ("input" + suffix)
    sep = "\t" if suffix == ".tsv" else ","
    text = ("group,amount,date\nAlpha,10,2023-01-01\nBeta,,\n"
            if temporal else "group,amount\nNA,10\nBeta,\n")
    source.write_text(text.replace(",", sep))
    mapping = {"category": "group", "measure": "amount"}
    if temporal:
        mapping["time"] = "date"
    return prepare_table(source, mapping=mapping,
                         mode="timeseries" if temporal else "snapshot",
                         period="year" if temporal else None)


def rewrite(destination, name, mutate):
    path = destination / name
    data = json.loads(path.read_text())
    mutate(data)
    path.write_bytes(bundle._json_bytes(data))
    rehash(destination, name)


def rehash(destination, name):
    manifest = json.loads((destination / "manifest.json").read_text())
    data = (destination / name).read_bytes()
    manifest["artifacts"][name] = {
        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()
    }
    (destination / "manifest.json").write_bytes(bundle._json_bytes(manifest))


@pytest.mark.parametrize("temporal,suffix", [(False, ".csv"), (True, ".csv"), (True, ".tsv")])
def test_round_trip_and_deterministic_serialization(tmp_path, temporal, suffix):
    original = prepared(tmp_path, temporal, suffix)
    first = bundle.publish_prepared_bundle(original, tmp_path / "one")
    second = bundle.publish_prepared_bundle(original, tmp_path / "two")
    verified = bundle.verify_prepared_bundle(first)
    pd.testing.assert_frame_equal(verified.table, original.table)
    assert verified.provenance == original.provenance
    assert verified.source_bytes == original.source_bytes
    assert {p.name for p in first.iterdir()} == {
        "source" + suffix, "table.json", "provenance.json", "manifest.json"
    }
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    assert not list(tmp_path.glob(".*.staging-*"))


@pytest.mark.parametrize("mutation", ["rows", "source", "parameters", "filters", "missing"])
def test_mutated_in_memory_input_is_rejected(tmp_path, mutation):
    original = prepared(tmp_path)
    if mutation == "rows":
        original.table.loc[0, "value"] = 999
    elif mutation == "source":
        original.source_bytes = original.source_bytes.replace(b"10", b"99")
    elif mutation == "parameters":
        original.provenance["parameters"]["mapping"]["measure"] = "group"
    elif mutation == "filters":
        original.provenance["filters"] = ["unperformed selection"]
    else:
        original.provenance["output"]["missing"]["value"] = 0
    with pytest.raises((ValueError, TypeError)):
        bundle.publish_prepared_bundle(original, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
    assert not list(tmp_path.glob(".*.staging-*"))


@pytest.mark.parametrize("name", ["source.csv", "table.json", "provenance.json"])
def test_hash_damage_is_rejected(tmp_path, name):
    destination = bundle.publish_prepared_bundle(prepared(tmp_path), tmp_path / "out")
    path = destination / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="mismatch"):
        bundle.verify_prepared_bundle(destination)


@pytest.mark.parametrize("attack", ["rows", "mapping", "source", "counts", "filters"])
def test_rehashed_false_content_is_rejected(tmp_path, attack):
    destination = bundle.publish_prepared_bundle(prepared(tmp_path), tmp_path / "out")
    if attack == "rows":
        rewrite(destination, "table.json", lambda d: d["rows"][0].__setitem__(1, 999))
    elif attack == "mapping":
        rewrite(destination, "provenance.json",
                lambda d: d["parameters"]["mapping"].__setitem__("measure", "group"))
    elif attack == "source":
        path = destination / "source.csv"
        path.write_bytes(path.read_bytes().replace(b"10", b"99"))
        rehash(destination, "source.csv")
        rewrite(destination, "provenance.json", lambda d: d["input"].__setitem__(
            "sha256", hashlib.sha256(path.read_bytes()).hexdigest()))
    elif attack == "counts":
        rewrite(destination, "provenance.json", lambda d: d["output"].__setitem__("rows", 999))
    else:
        rewrite(destination, "provenance.json", lambda d: d.__setitem__("filters", ["not applied"]))
    with pytest.raises(ValueError):
        bundle.verify_prepared_bundle(destination)


@pytest.mark.parametrize("attack", ["missing", "extra", "directory", "symlink", "root-symlink", "traversal"])
def test_artifact_and_path_boundary(tmp_path, attack):
    destination = bundle.publish_prepared_bundle(prepared(tmp_path), tmp_path / "out")
    if attack == "missing":
        (destination / "table.json").unlink()
    elif attack == "extra":
        (destination / "extra.txt").write_text("unexpected")
    elif attack == "directory":
        (destination / "table.json").unlink()
        (destination / "table.json").mkdir()
    elif attack == "symlink":
        external = tmp_path / "external.json"
        (destination / "table.json").rename(external)
        (destination / "table.json").symlink_to(external)
    elif attack == "root-symlink":
        link = tmp_path / "linked"
        link.symlink_to(destination, target_is_directory=True)
        destination = link
    else:
        manifest = json.loads((destination / "manifest.json").read_text())
        manifest["artifacts"]["../outside"] = manifest["artifacts"].pop("table.json")
        (destination / "manifest.json").write_bytes(bundle._json_bytes(manifest))
    with pytest.raises(ValueError):
        bundle.verify_prepared_bundle(destination)


@pytest.mark.parametrize("payload", [b'{"schema":1,"schema":2}', b'{"schema":NaN}', b'[]'])
def test_strict_manifest_json(tmp_path, payload):
    destination = bundle.publish_prepared_bundle(prepared(tmp_path), tmp_path / "out")
    (destination / "manifest.json").write_bytes(payload)
    with pytest.raises(ValueError):
        bundle.verify_prepared_bundle(destination)


def test_valid_utc_timestamp_is_not_reproduced_as_analytic_content(tmp_path):
    destination = bundle.publish_prepared_bundle(prepared(tmp_path), tmp_path / "out")
    rewrite(destination, "provenance.json", lambda d: d.__setitem__(
        "prepared_at_utc", "2020-01-01T00:00:00+00:00"))
    verified = bundle.verify_prepared_bundle(destination)
    assert verified.provenance["prepared_at_utc"].startswith("2020-")


@pytest.mark.parametrize("stamp", ["bad", "2020-01-01", "2020-01-01T00:00:00+01:00"])
def test_invalid_timestamp_rejected(tmp_path, stamp):
    destination = bundle.publish_prepared_bundle(prepared(tmp_path), tmp_path / "out")
    rewrite(destination, "provenance.json", lambda d: d.__setitem__("prepared_at_utc", stamp))
    with pytest.raises(ValueError):
        bundle.verify_prepared_bundle(destination)


@pytest.mark.parametrize("nonempty", [False, True])
def test_existing_destination_is_never_overwritten(tmp_path, nonempty):
    original = prepared(tmp_path)
    destination = tmp_path / "existing"
    destination.mkdir()
    if nonempty:
        (destination / "sentinel").write_text("keep")
    with pytest.raises(FileExistsError):
        bundle.publish_prepared_bundle(original, destination)
    assert sorted(p.name for p in destination.iterdir()) == (["sentinel"] if nonempty else [])


def test_destination_created_at_publication_time_is_preserved(tmp_path, monkeypatch):
    original = prepared(tmp_path)
    rename = bundle._rename_no_replace

    def collision(stage, destination):
        destination.mkdir()
        (destination / "sentinel").write_text("keep")
        rename(stage, destination)

    monkeypatch.setattr(bundle, "_rename_no_replace", collision)
    with pytest.raises(FileExistsError):
        bundle.publish_prepared_bundle(original, tmp_path / "out")
    assert (tmp_path / "out/sentinel").read_text() == "keep"
    assert not list(tmp_path.glob(".*.staging-*"))


def test_interrupted_staging_leaves_no_success_destination(tmp_path, monkeypatch):
    original = prepared(tmp_path)

    def interrupt(stage, artifacts):
        (stage / "partial").write_bytes(b"partial")
        raise KeyboardInterrupt()

    monkeypatch.setattr(bundle, "_write_artifacts", interrupt)
    with pytest.raises(KeyboardInterrupt):
        bundle.publish_prepared_bundle(original, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".*.staging-*"))


def test_publication_failure_is_cleaned_up(tmp_path, monkeypatch):
    original = prepared(tmp_path)

    def unavailable(stage, destination):
        raise NotImplementedError("no atomic no-replace operation")

    monkeypatch.setattr(bundle, "_rename_no_replace", unavailable)
    with pytest.raises(NotImplementedError):
        bundle.publish_prepared_bundle(original, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".*.staging-*"))


def test_read_only_verification_does_not_rewrite_artifacts(tmp_path):
    destination = bundle.publish_prepared_bundle(prepared(tmp_path), tmp_path / "out")
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in destination.iterdir()}
    bundle.verify_prepared_bundle(destination)
    after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in destination.iterdir()}
    assert after == before
