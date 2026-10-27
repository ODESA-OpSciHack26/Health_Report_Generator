"""Shared-source renderer contracts; unit tests mock Quarto, not acceptance."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/health_pipeline"))

import tabular_render as renderer  # noqa: E402
from tabular_prepare import prepare_table  # noqa: E402
from tabular_bundle import publish_prepared_bundle  # noqa: E402


def source_bundle(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text('group,amount,date\n"</script><img src=x>",10,2023-01-01\nBeta,,\n')
    prepared = prepare_table(path, mapping={"category": "group", "measure": "amount", "time": "date"},
                             mode="timeseries", period="year")
    return publish_prepared_bundle(prepared, tmp_path / "source-bundle")


@pytest.fixture
def fake_quarto(monkeypatch):
    calls = []
    monkeypatch.setattr(renderer, "_tool_version", lambda command: "test-version")

    def run(command, *, cwd, env, check):
        work = Path(cwd)
        calls.append(command)
        template = (work / "report.qmd").read_bytes()
        assert template == (renderer.HERE / "report_shared.qmd").read_bytes()
        params = json.loads((work / "params.yml").read_text())
        assert params["input_kind"] == "tabular"
        record = json.loads((work / "provenance.json").read_text())
        context = json.loads((work / "tabular_context.json").read_text())
        text = (f'<div data-tabular-audience="{context["audience"]}">'
                + context["rows_html"] + '</div><script>var x="table-filter";</script>'
                + '<script type="application/json" id="report-provenance">'
                + json.dumps(record).replace('</', '<\\/') + '</script>')
        (work / command[command.index("--output") + 1]).write_text(text)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(renderer.subprocess, "run", run)
    return calls


def test_one_shared_source_and_distinct_profiles(tmp_path, fake_quarto):
    destination = renderer.render_tabular_reports(source_bundle(tmp_path), tmp_path / "reports")
    assert len(fake_quarto) == 6
    renderer.verify_tabular_reports(destination)
    records = [json.loads((destination / audience / "provenance.json").read_text())
               for audience in renderer.AUDIENCES]
    assert {record["stakeholder"]["presentation"]["layout"] for record in records} == {
        "technical", "dashboard", "editorial"}
    assert len({json.dumps(record["effective_parameters"]["preparation"], sort_keys=True)
                for record in records}) == 1
    assert len({record["data"]["table_sha256"] for record in records}) == 1
    assert all(record["aggregation"] == "none" and record["filters"] == [] for record in records)
    assert not list(tmp_path.glob(".*.staging-*"))


def test_html_rows_are_escaped_and_not_aggregated(tmp_path):
    bundle = source_bundle(tmp_path)
    prepared = renderer.bundles.verify_prepared_bundle(bundle)
    text = renderer._rows_html(prepared)
    assert '&lt;/script&gt;&lt;img src=x&gt;' in text
    assert '<img src=x>' not in text
    assert text.count('<tr>') == len(prepared.table) + 1
    assert 'Missing' in text


def test_tampered_bundle_blocks_all_tools_and_output(tmp_path, monkeypatch):
    bundle = source_bundle(tmp_path)
    (bundle / "table.json").write_text("damaged")
    def forbidden(command):
        raise AssertionError("Tools must not run before bundle verification")
    monkeypatch.setattr(renderer, "_tool_version", forbidden)
    with pytest.raises(ValueError):
        renderer.render_tabular_reports(bundle, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("attack", ["embedded", "audience", "missing", "extra", "symlink", "provenance"])
def test_render_verifier_rejects_damage(tmp_path, fake_quarto, attack):
    destination = renderer.render_tabular_reports(source_bundle(tmp_path), tmp_path / "reports")
    if attack == "missing":
        (destination / "public/methods.html").unlink()
    elif attack == "extra":
        (destination / "extra.txt").write_text("unexpected")
    elif attack == "symlink":
        target = destination / "public/report.html"
        target.unlink()
        target.symlink_to(destination / "researcher/report.html")
    else:
        target = destination / ("public/provenance.json" if attack == "provenance" else "public/report.html")
        if attack == "embedded":
            target.write_text(target.read_text().replace('"aggregation": "none"', '"aggregation": "sum"'))
        elif attack == "audience":
            target.write_text(target.read_text().replace('data-tabular-audience="public"', 'data-tabular-audience="researcher"'))
        else:
            record = json.loads(target.read_text())
            record["filters"] = ["not applied"]
            target.write_bytes(renderer.bundles._json_bytes(record))
        manifest = json.loads((destination / "render_manifest.json").read_text())
        name = target.relative_to(destination).as_posix()
        manifest["artifacts"][name] = {"bytes": target.stat().st_size, "sha256": renderer._hash(target)}
        (destination / "render_manifest.json").write_bytes(renderer.bundles._json_bytes(manifest))
    with pytest.raises(ValueError):
        renderer.verify_tabular_reports(destination)


def test_failed_second_document_never_publishes(tmp_path, fake_quarto, monkeypatch):
    run = renderer.subprocess.run
    def failure(command, **kwargs):
        if command[command.index("--output") + 1] == "methods.html":
            raise subprocess.CalledProcessError(1, command)
        return run(command, **kwargs)
    monkeypatch.setattr(renderer.subprocess, "run", failure)
    with pytest.raises(subprocess.CalledProcessError):
        renderer.render_tabular_reports(source_bundle(tmp_path), tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".*.staging-*"))


def test_existing_destination_is_preserved(tmp_path, fake_quarto):
    bundle = source_bundle(tmp_path)
    destination = tmp_path / "out"
    destination.mkdir()
    (destination / "sentinel").write_text("keep")
    with pytest.raises(FileExistsError):
        renderer.render_tabular_reports(bundle, destination)
    assert (destination / "sentinel").read_text() == "keep"
    assert not fake_quarto


def test_template_keeps_canonical_default_and_has_no_additional_qmd():
    text = (renderer.HERE / "report_shared.qmd").read_text()
    assert 'input_kind: "canonical"' in text
    assert "if(!is_tabular && knitr::" in text
    assert "tabular_document_html" in text
    reports = sorted(path.name for path in renderer.HERE.rglob('*.qmd')
                     if 'example_output' not in path.parts)
    assert reports == ['methods.qmd', 'report_shared.qmd']
