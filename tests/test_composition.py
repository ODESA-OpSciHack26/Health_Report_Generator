"""Composition recipe validation and render plumbing."""
import json
import subprocess
from pathlib import Path

import pytest

import publish
from test_composer_contracts import build_bundle

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "scripts" / "health_pipeline" / "config" / "composer" / "compositions" / "researcher.json"


def write_recipe(tmp_path, blocks, contract=publish.COMPOSITION_CONTRACT, **extra):
    payload = {"contract": contract, "audience": "researcher",
               "blocks": blocks, **extra}
    path = tmp_path / "recipe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path


def fixture_recipe(tmp_path, topic="virus"):
    """v2 recipe bound to the fixture bundle's saved topic."""
    return write_recipe(tmp_path, [{"block": "reference-comparison",
                                    "instance_id": "block-reference-comparison",
                                    "topic": topic}],
                        contract=publish.COMPOSITION_CONTRACT_V2)


def test_researcher_recipe_order_is_data():
    recipe = publish.load_composition(RECIPE)
    assert [entry["block"] for entry in recipe["blocks"]] == [
        "intro", "series-collection", "coverage-selection", "sensitivity-comparison",
        "reference-comparison", "limitations", "reproduction"]
    assert len({entry["instance_id"] for entry in recipe["blocks"]}) == 7


def test_unknown_block_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unknown block type"):
        publish.load_composition(write_recipe(tmp_path, [{"block": "gallery", "instance_id": "i-g"}]))
    assert "gallery" not in publish.KNOWN_BLOCKS


def test_duplicate_instance_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Duplicate block instance id"):
        publish.load_composition(write_recipe(tmp_path, [
            {"block": "intro", "instance_id": "i-same"},
            {"block": "limitations", "instance_id": "i-same"}]))


def test_unknown_recipe_field_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported composition fields"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": "intro", "instance_id": "i-a"}], script="alert(1)"))


def test_empty_recipe_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="non-empty blocks"):
        publish.load_composition(write_recipe(tmp_path, []))


def test_render_passes_recipe_path_only_to_report(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True, stakeholder_overrides={"id": "researcher"})
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append(list(command))
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    publish.render(bundle["bundle"], tmp_path / "out" / "report.html", "html", "quarto",
                   provenance={"schema": "test"}, composition=fixture_recipe(tmp_path))
    report = [c for c in commands if "report.qmd" in c][0]
    methods = [c for c in commands if "methods.qmd" in c][0]
    recipe_args = [arg for arg in report if arg.startswith("block_recipe:")]
    assert len(recipe_args) == 1
    assert Path(recipe_args[0].split(":", 1)[1]).is_absolute()
    assert not any(arg.startswith("block_recipe:") for arg in methods)


def test_composed_render_rejects_recipe_for_another_bundle(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True)
    called = []
    monkeypatch.setattr(publish.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(ValueError, match="does not match bundle audience"):
        publish.render(bundle["bundle"], tmp_path / "out" / "report.html", "html", "quarto",
                       provenance={"schema": "test"}, composition=RECIPE)
    assert called == []


def test_legacy_mode_sends_no_recipe(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True)
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append(list(command))
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    publish.render(bundle["bundle"], tmp_path / "out" / "report.html", "html", "quarto",
                   provenance={"schema": "test"})
    assert not any(arg.startswith("block_recipe:") for c in commands for arg in c)


def _capture(tmp_path, monkeypatch, fmt, **kwargs):
    bundle = build_bundle(tmp_path, archive=True, stakeholder_overrides={"id": "researcher"})
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append(list(command))
        suffix = command[2].split(".")[0]
        (Path(cwd) / (suffix + "." + fmt)).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    publish.render(bundle["bundle"], tmp_path / "out" / f"report.{fmt}", fmt, "quarto", **kwargs)
    return commands


def test_composed_html_suppresses_alternate_format_offer(tmp_path, monkeypatch):
    commands = _capture(tmp_path, monkeypatch, "html",
                        provenance={"schema": "test"}, composition=fixture_recipe(tmp_path))
    report = [c for c in commands if "report.qmd" in c][0]
    methods = [c for c in commands if "methods.qmd" in c][0]
    assert ["-M", "format-links:false"] == report[report.index("-M"):report.index("-M") + 2]
    assert ["-M", "format-links:false"] == methods[methods.index("-M"):methods.index("-M") + 2]
    assert any(arg.startswith("block_recipe:") for arg in report)
    assert not any(arg.startswith("block_recipe:") for arg in methods)


def test_composed_methods_render_without_pdf_offer(tmp_path, monkeypatch):
    commands = _capture(tmp_path, monkeypatch, "html",
                        provenance={"schema": "test"}, composition=fixture_recipe(tmp_path))
    methods = [c for c in commands if "methods.qmd" in c][0]
    assert "html_only:true" in methods
    report = [c for c in commands if "report.qmd" in c][0]
    assert "html_only:true" not in report


def test_legacy_methods_render_keeps_existing_pdf_link(tmp_path, monkeypatch):
    commands = _capture(tmp_path, monkeypatch, "html", provenance={"schema": "test"})
    methods = [c for c in commands if "methods.qmd" in c][0]
    assert not any(arg.startswith("html_only:") for arg in methods)


def test_composed_pdf_is_rejected_before_rendering(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(publish.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(ValueError, match="not supported"):
        publish.render(tmp_path / "bundle", tmp_path / "out" / "report.pdf", "pdf", "quarto",
                       provenance={"schema": "test"}, composition=RECIPE)
    assert called == []


def test_legacy_pdf_is_still_supported(tmp_path, monkeypatch):
    commands = _capture(tmp_path, monkeypatch, "pdf", provenance={"schema": "test"})
    report = [c for c in commands if "report.qmd" in c][0]
    assert "-M" not in report
    assert not any(arg.startswith("block_recipe:") for arg in report)


def _method_params(command, name):
    """Values passed as `-P name:value` pairs, so a bare token is never a match."""
    values = []
    for position, arg in enumerate(command):
        if arg == "-P" and position + 1 < len(command) \
                and command[position + 1].startswith(name + ":"):
            values.append(command[position + 1].split(":", 1)[1])
    return values


def _composed_report_args(command):
    return [arg for arg in command if "composed_report" in arg]


def test_canonical_html_methods_receives_composed_report_false(tmp_path, monkeypatch):
    commands = _capture(tmp_path, monkeypatch, "html", provenance={"schema": "test"})
    methods = [c for c in commands if "methods.qmd" in c][0]
    assert _method_params(methods, "composed_report") == ["false"]
    assert _composed_report_args(methods) == ["composed_report:false"]


def test_composed_html_methods_receives_composed_report_true(tmp_path, monkeypatch):
    commands = _capture(tmp_path, monkeypatch, "html",
                        provenance={"schema": "test"}, composition=fixture_recipe(tmp_path))
    methods = [c for c in commands if "methods.qmd" in c][0]
    assert _method_params(methods, "composed_report") == ["true"]
    assert _composed_report_args(methods) == ["composed_report:true"]


def test_canonical_pdf_methods_receives_composed_report_false(tmp_path, monkeypatch):
    commands = _capture(tmp_path, monkeypatch, "pdf", provenance={"schema": "test"})
    methods = [c for c in commands if "methods.qmd" in c][0]
    assert _method_params(methods, "composed_report") == ["false"]
    assert _composed_report_args(methods) == ["composed_report:false"]


def test_report_documents_receive_no_composed_report(tmp_path, monkeypatch):
    cases = [
        ("html", {"provenance": {"schema": "test"}}),
        ("pdf", {"provenance": {"schema": "test"}}),
    ]
    for fmt, kwargs in cases:
        commands = _capture(tmp_path / fmt, monkeypatch, fmt, **kwargs)
        report = [c for c in commands if "report.qmd" in c][0]
        assert _composed_report_args(report) == []
    composed = _capture(tmp_path / "composed", monkeypatch, "html",
                        provenance={"schema": "test"}, composition=fixture_recipe(tmp_path))
    report = [c for c in composed if "report.qmd" in c][0]
    assert _composed_report_args(report) == []


def test_repeated_reference_comparison_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Repeated reference-comparison"):
        publish.load_composition(write_recipe(tmp_path, [
            {"block": "reference-comparison", "instance_id": "ref-first"},
            {"block": "reference-comparison", "instance_id": "ref-second"}]))


def test_repeated_stateless_blocks_are_allowed_with_distinct_ids(tmp_path):
    recipe = publish.load_composition(write_recipe(tmp_path, [
        {"block": "intro", "instance_id": "intro-first"},
        {"block": "intro", "instance_id": "intro-second"},
        {"block": "limitations", "instance_id": "limits-0001"}]))
    assert [entry["instance_id"] for entry in recipe["blocks"]] == [
        "intro-first", "intro-second", "limits-0001"]


def _composed_sidecar(tmp_path, monkeypatch, blocks, name):
    work = tmp_path / name
    work.mkdir(parents=True, exist_ok=True)
    bundle = build_bundle(work, archive=True, stakeholder_overrides={"id": "researcher"})
    recipe = write_recipe(work, blocks)
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append(list(command))
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    out = work / "report.html"
    sidecar = work / "provenance.json"
    publish.render(bundle["bundle"], out, "html", "quarto",
                   provenance={"schema": "test"}, provenance_out=sidecar, composition=recipe)
    return json.loads(sidecar.read_text())


def test_provenance_binds_recipe_instance_to_checked_contract_record(tmp_path, monkeypatch):
    blocks = [{"block": "intro", "instance_id": "intro-0001"},
              {"block": "reference-comparison", "instance_id": "ref-block-0001"}]
    sidecar = _composed_sidecar(tmp_path, monkeypatch, blocks, "agree")
    instances = sidecar["composition"]["instances"]
    assert [entry["instance_id"] for entry in instances] == ["intro-0001", "ref-block-0001"]
    assert sidecar["blocks"][0]["instance_id"] == "ref-block-0001"
    reference = instances[1]
    assert reference["contract_instance_id"] == "ref-block-0001"
    assert reference["contract_status"] == "verified"
    assert reference["instance_identity"] == sidecar["blocks"][0]["identities"]["instance"]
    assert "contract_instance_id" not in instances[0]


def test_reordering_keeps_contract_instance_identity(tmp_path, monkeypatch):
    forward = [{"block": "intro", "instance_id": "intro-0001"},
               {"block": "reference-comparison", "instance_id": "ref-block-0001"}]
    backward = list(reversed(forward))
    first = _composed_sidecar(tmp_path, monkeypatch, forward, "forward")
    second = _composed_sidecar(tmp_path, monkeypatch, backward, "backward")
    assert first["blocks"][0]["identities"] == second["blocks"][0]["identities"]
    assert [entry["instance_id"] for entry in first["composition"]["instances"]] == [
        "intro-0001", "ref-block-0001"]
    assert [entry["instance_id"] for entry in second["composition"]["instances"]] == [
        "ref-block-0001", "intro-0001"]


RECIPES = ROOT / "scripts" / "health_pipeline" / "config" / "composer" / "compositions"
AUDIENCE_ORDER = {
    "researcher": ["intro", "series-collection", "coverage-selection",
                   "sensitivity-comparison", "reference-comparison",
                   "limitations", "reproduction"],
    "health_institution": ["intro", "monitoring-overview", "series-collection",
                           "reference-comparison", "limitations", "reproduction"],
    "public": ["intro", "reference-comparison", "series-collection",
               "limitations", "reproduction"],
}


def test_three_audience_recipes_declare_their_own_audience():
    for audience, order in AUDIENCE_ORDER.items():
        recipe = publish.load_composition(RECIPES / f"{audience}.json")
        assert recipe["contract"] == publish.COMPOSITION_CONTRACT_V2
        assert recipe["audience"] == audience
        assert [entry["block"] for entry in recipe["blocks"]] == order
        ids = [entry["instance_id"] for entry in recipe["blocks"]]
        assert len(ids) == len(set(ids)) == len(order)
        reference = next(entry for entry in recipe["blocks"]
                         if entry["block"] == "reference-comparison")
        assert reference["topic"] == "campylobacteriosis"


def _fake_bundle(bundle_root, audience, recorded=None):
    data = bundle_root / audience / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "bundle.json").write_text('{"files": {}}')
    (data / "stakeholder.json").write_text(json.dumps({"id": recorded or audience}))
    return data


def _named_recipe(directory, audience, block_order, declared=None, prefix=None):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{audience}.json"
    tag = prefix or audience[:2]
    blocks = []
    for index, block in enumerate(block_order, start=1):
        entry = {"block": block, "instance_id": f"{tag}-{block[:3]}-{index}"}
        if block == "reference-comparison":
            entry["topic"] = "campylobacteriosis"
        if block == "series-trend":
            entry.update({"topic": "campylobacteriosis", "measure": "cases"})
        if block == "series-collection":
            entry.update({"topics": ["campylobacteriosis"], "measure": "cases"})
        blocks.append(entry)
    path.write_text(json.dumps({"contract": "health-report/composition-recipe/2",
                                "audience": declared or audience, "blocks": blocks}))
    return path


def _stub_batch(tmp_path, monkeypatch, audiences=None):
    calls = []

    def fake_provenance(bundle, fmt, quarto=None, data_root=None, wf=None,
                        source_identity_path=None):
        return {"schema": "test", "bundle": str(bundle), "format": fmt}

    def fake_render(bundle, output, fmt, quarto="quarto", provenance=None,
                    provenance_out=None, composition=None):
        calls.append({"bundle": Path(bundle), "output": Path(output),
                      "composition": Path(composition)})
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text("rendered")
        Path(provenance_out).write_text("{}")

    monkeypatch.setattr(publish, "build_provenance", fake_provenance)
    monkeypatch.setattr(publish, "render", fake_render)
    return calls


def test_batch_renders_each_audience_from_its_own_bundle_and_recipe(tmp_path, monkeypatch):
    calls = _stub_batch(tmp_path, monkeypatch)
    bundle_root = tmp_path / "bundles"
    recipes = tmp_path / "recipes"
    for audience, order in AUDIENCE_ORDER.items():
        _fake_bundle(bundle_root, audience)
        _named_recipe(recipes, audience, order,
                      prefix={"researcher": "res", "health_institution": "hi",
                              "public": "pub"}[audience])
    results = publish.render_composition_batch(bundle_root, recipes, tmp_path / "out")
    assert [item["status"] for item in results] == ["rendered", "rendered", "rendered"]
    assert [item["audience"] for item in results] == list(publish.BATCH_AUDIENCES)
    assert [Path(item["report"]).parent.name for item in results] == list(publish.BATCH_AUDIENCES)
    assert [call["bundle"] for call in calls] == [
        bundle_root / audience / "data" for audience in publish.BATCH_AUDIENCES]
    assert [call["composition"] for call in calls] == [
        recipes / f"{audience}.json" for audience in publish.BATCH_AUDIENCES]
    assert len({call["output"] for call in calls}) == 3


def test_batch_rejects_recipe_for_another_audience(tmp_path, monkeypatch):
    calls = _stub_batch(tmp_path, monkeypatch)
    bundle_root = tmp_path / "bundles"
    recipes = tmp_path / "recipes"
    for audience, order in AUDIENCE_ORDER.items():
        _fake_bundle(bundle_root, audience)
        _named_recipe(recipes, audience, order)
    _named_recipe(recipes, "health_institution", AUDIENCE_ORDER["health_institution"],
                  declared="researcher")
    results = publish.render_composition_batch(bundle_root, recipes, tmp_path / "out")
    by_audience = {item["audience"]: item for item in results}
    assert by_audience["researcher"]["status"] == "rendered"
    assert by_audience["public"]["status"] == "rendered"
    assert by_audience["health_institution"]["status"] == "failed"
    assert "does not match requested audience" in by_audience["health_institution"]["error"]
    assert len(calls) == 2


def test_batch_never_substitutes_another_audience_bundle(tmp_path, monkeypatch):
    calls = _stub_batch(tmp_path, monkeypatch)
    bundle_root = tmp_path / "bundles"
    recipes = tmp_path / "recipes"
    for audience, order in AUDIENCE_ORDER.items():
        _fake_bundle(bundle_root, audience, recorded="researcher" if audience == "public" else audience)
        _named_recipe(recipes, audience, order)
    results = publish.render_composition_batch(bundle_root, recipes, tmp_path / "out")
    by_audience = {item["audience"]: item for item in results}
    assert by_audience["public"]["status"] == "failed"
    assert "Bundle audience 'researcher' does not match requested audience 'public'" in by_audience["public"]["error"]
    assert [call["bundle"].parent.name for call in calls] == ["researcher", "health_institution"]


def test_batch_reports_missing_audience_bundle(tmp_path, monkeypatch):
    _stub_batch(tmp_path, monkeypatch)
    bundle_root = tmp_path / "bundles"
    recipes = tmp_path / "recipes"
    for audience in ("researcher", "health_institution"):
        _fake_bundle(bundle_root, audience)
        _named_recipe(recipes, audience, AUDIENCE_ORDER[audience])
    _named_recipe(recipes, "public", AUDIENCE_ORDER["public"])
    results = publish.render_composition_batch(bundle_root, recipes, tmp_path / "out")
    by_audience = {item["audience"]: item for item in results}
    assert by_audience["public"]["status"] == "failed"
    assert "No retained bundle for audience 'public'" in by_audience["public"]["error"]


def test_batch_exits_nonzero_when_any_report_fails(tmp_path, monkeypatch, capsys):
    calls = _stub_batch(tmp_path, monkeypatch)
    bundle_root = tmp_path / "bundles"
    recipes = tmp_path / "recipes"
    for audience, order in AUDIENCE_ORDER.items():
        _fake_bundle(bundle_root, audience)
        _named_recipe(recipes, audience, order)

    def failing_render(bundle, output, fmt, quarto="quarto", provenance=None,
                       provenance_out=None, composition=None):
        if Path(composition).stem == "health_institution":
            raise RuntimeError("renderer exploded")
        calls.append({"bundle": Path(bundle), "output": Path(output)})
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text("rendered")
        Path(provenance_out).write_text("{}")

    monkeypatch.setattr(publish, "render", failing_render)
    with pytest.raises(SystemExit) as excinfo:
        publish.main(["batch", "--bundle-root", str(bundle_root), "--recipes", str(recipes),
                      "--output-root", str(tmp_path / "out")])
    assert excinfo.value.code != 0
    assert "1 of 3 composed reports failed: health_institution" in str(excinfo.value)
    out = capsys.readouterr().out
    assert "researcher: rendered" in out
    assert "health_institution: failed" in out
    assert "public: rendered" in out
    assert len(calls) == 2


def test_batch_success_returns_without_exit(tmp_path, monkeypatch):
    _stub_batch(tmp_path, monkeypatch)
    bundle_root = tmp_path / "bundles"
    recipes = tmp_path / "recipes"
    for audience, order in AUDIENCE_ORDER.items():
        _fake_bundle(bundle_root, audience)
        _named_recipe(recipes, audience, order)
    assert publish.main(["batch", "--bundle-root", str(bundle_root), "--recipes", str(recipes),
                         "--output-root", str(tmp_path / "out")]) is None


def test_render_publishes_exact_evidence_artifacts(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True, stakeholder_overrides={"id": "researcher"})
    out = tmp_path / "out" / "report.html"

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        links = ('<a href="data/stakeholder.json" download>params</a>'
                 '<a href="data/bundle.json" download>manifest</a>'
                 '<a href="data/metrics.csv" download>metrics</a>')
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text(f"<html>{links}</html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    publish.render(bundle["bundle"], out, "html", "quarto",
                   provenance={"schema": "test"},
                   provenance_out=out.parent / "provenance.json", composition=fixture_recipe(tmp_path))

    manifest = json.loads((bundle["bundle"] / "bundle.json").read_text())
    data = out.parent / "data"
    for name, expected in manifest["files"].items():
        assert (data / name).read_bytes() == (bundle["bundle"] / name).read_bytes()
        assert publish.digest(data / name) == expected
    assert (data / "bundle.json").is_file()
    assert publish.validate_published_evidence(out.parent) is True


def test_published_evidence_check_rejects_workspace_only_artifact(tmp_path):
    published = tmp_path / "published"
    workspace = tmp_path / "workspace"
    published.mkdir()
    workspace.mkdir()
    (published / "report.html").write_text('<a href="data/metrics.csv" download>metrics</a>')
    (published / "methods.html").write_text("<html></html>")
    (published / "provenance.json").write_text("{}")
    (workspace / "metrics.csv").write_text("only in the temporary workspace")
    with pytest.raises(ValueError, match="unresolved local evidence links"):
        publish.validate_published_evidence(published)
    (published / "data").mkdir()
    (published / "data" / "metrics.csv").write_text("copied")
    assert publish.validate_published_evidence(published) is True


def test_published_evidence_check_ignores_template_literals(tmp_path):
    published = tmp_path / "published"
    published.mkdir()
    (published / "report.html").write_text(
        '<a href="data/metrics.csv" download>metrics</a>'
        '<a href="${t}">script template</a><a href="https://example.org/x">external</a>'
        '<a href="#section">anchor</a>')
    (published / "methods.html").write_text("<html></html>")
    (published / "provenance.json").write_text("{}")
    (published / "data").mkdir()
    (published / "data" / "metrics.csv").write_text("saved")
    assert publish.validate_published_evidence(published) is True


def test_publish_evidence_copies_every_manifest_file(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "stakeholder.json").write_text("{}")
    (bundle / "extra_artifact.txt").write_text("saved bytes")
    files = {name: publish.digest(bundle / name)
             for name in ("stakeholder.json", "extra_artifact.txt")}
    (bundle / "bundle.json").write_text(json.dumps({
        "schema_version": "2.0", "snapshot_id": "x", "files": files}))
    published = publish.publish_evidence(bundle, tmp_path / "out" / "data")
    assert set(published) == {"stakeholder.json", "extra_artifact.txt", "bundle.json"}
    assert (tmp_path / "out" / "data" / "extra_artifact.txt").read_text() == "saved bytes"


def test_published_evidence_check_covers_methods_page(tmp_path):
    published = tmp_path / "published"
    published.mkdir()
    (published / "report.html").write_text('<a href="data/metrics.csv" download>metrics</a>')
    (published / "methods.html").write_text('<a href="data/checks.csv" download>checks</a>')
    (published / "provenance.json").write_text("{}")
    (published / "data").mkdir()
    (published / "data" / "metrics.csv").write_text("saved")
    with pytest.raises(ValueError, match="methods.html:data/checks.csv"):
        publish.validate_published_evidence(published)
    (published / "data" / "checks.csv").write_text("saved")
    assert publish.validate_published_evidence(published) is True


def test_publish_evidence_does_not_invent_absent_artifacts(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "stakeholder.json").write_text("{}")
    (bundle / "bundle.json").write_text(json.dumps({
        "schema_version": "2.0", "snapshot_id": "x",
        "files": {"stakeholder.json": publish.digest(bundle / "stakeholder.json")}}))
    data = tmp_path / "published" / "data"
    published = publish.publish_evidence(bundle, data)
    assert set(published) == {"stakeholder.json", "bundle.json"}
    assert not (data / "metrics.csv").exists()
    (tmp_path / "published" / "report.html").write_text(
        '<a href="data/metrics.csv" download>metrics</a>')
    (tmp_path / "published" / "methods.html").write_text("<html></html>")
    (tmp_path / "published" / "provenance.json").write_text("{}")
    with pytest.raises(ValueError, match="unresolved local evidence links"):
        publish.validate_published_evidence(tmp_path / "published")


# --- recipe v2: explicit reference-comparison topic -------------------------

def _render_with_fakes(tmp_path, monkeypatch, bundle, recipe):
    out = tmp_path / "render" / "report.html"
    commands = []

    def fake_package(source, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)

    def fake_run(command, cwd=None, check=True, env=None):
        commands.append(list(command))
        (Path(cwd) / (command[2].replace(".qmd", ".html"))).write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(publish, "package", fake_package)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    publish.render(bundle["bundle"], out, "html", "quarto",
                   provenance={"schema": "test"},
                   provenance_out=out.parent / "provenance.json", composition=recipe)
    return out, commands


def test_v2_requires_topic_for_reference_comparison(tmp_path):
    with pytest.raises(ValueError, match=r"expected \['block', 'instance_id', 'topic'\]"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": "reference-comparison", "instance_id": "ref-x"}],
            contract=publish.COMPOSITION_CONTRACT_V2))


def test_v2_rejects_topic_on_other_blocks(tmp_path):
    with pytest.raises(ValueError, match="Invalid fields"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": "intro", "instance_id": "intro-x", "topic": "virus"}],
            contract=publish.COMPOSITION_CONTRACT_V2))


def test_v1_rejects_topic_field(tmp_path):
    with pytest.raises(ValueError, match="Invalid fields"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": "reference-comparison", "instance_id": "ref-x", "topic": "virus"}]))


def test_v2_rejects_invalid_topic_id(tmp_path):
    with pytest.raises(ValueError, match="Invalid topic id"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": "reference-comparison", "instance_id": "ref-x", "topic": "Virus!"}],
            contract=publish.COMPOSITION_CONTRACT_V2))


def test_v2_explicit_topic_binds_requested_saved_records(tmp_path):
    bundle = build_bundle(tmp_path, archive=True, stakeholder_overrides={"id": "researcher"})
    record = publish.build_block(bundle["bundle"], bundle["results"], ROOT, "ref-x", "virus")
    assert record["status"] == "verified"
    assert record["subject"] == "virus"
    assert record["result"]["metric_id"] == "virus:reference_change"
    assert record["result"]["value"] == 60.0
    assert record["reference_count"] == {"metric_id": "virus:2019:count", "value": "10"}
    assert record["latest_count"] == {"metric_id": "virus:2025:count", "value": "16"}


def test_v2_unknown_topic_fails_without_fallback(tmp_path):
    bundle = build_bundle(tmp_path, archive=True)
    record = publish.build_block(bundle["bundle"], bundle["results"], ROOT, "ref-x", "bacterium")
    assert record["status"] == "failed"
    assert record["code"] == "selection"
    assert "bacterium" in record["detail"]
    assert "subject" not in record and "result" not in record


def test_v2_excluded_topic_fails_with_recorded_reason(tmp_path):
    bundle = build_bundle(tmp_path, archive=True, selection_status="excluded")
    record = publish.build_block(bundle["bundle"], bundle["results"], ROOT, "ref-x", "virus")
    assert record["status"] == "failed"
    assert record["code"] == "selection"
    assert "not included" in record["detail"]
    assert "Complete compatible series" in record["detail"]


def test_v2_failed_explicit_binding_fails_render(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True, stakeholder_overrides={"id": "researcher"})
    with pytest.raises(ValueError, match="failed explicit reference binding"):
        _render_with_fakes(tmp_path, monkeypatch, bundle, fixture_recipe(tmp_path, "bacterium"))
    sidecar = json.loads((tmp_path / "render" / "provenance.json").read_text())
    assert sidecar["blocks"][0]["status"] == "failed"
    assert (tmp_path / "render" / "report.html").is_file()


def test_v2_provenance_records_explicit_topic_and_identity(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True, stakeholder_overrides={"id": "researcher"})
    _render_with_fakes(tmp_path, monkeypatch, bundle, fixture_recipe(tmp_path, "virus"))
    sidecar = json.loads((tmp_path / "render" / "provenance.json").read_text())
    reference = next(entry for entry in sidecar["composition"]["instances"]
                     if entry["block"] == "reference-comparison")
    assert reference["topic"] == "virus"
    assert reference["binding"] == "explicit"
    assert reference["contract_instance_id"] == reference["instance_id"]
    assert reference["instance_identity"] == sidecar["blocks"][0]["identities"]["instance"]
    assert sidecar["blocks"][0]["subject"] == "virus"


def test_v1_provenance_records_deterministic_binding(tmp_path, monkeypatch):
    bundle = build_bundle(tmp_path, archive=True, stakeholder_overrides={"id": "researcher"})
    recipe = write_recipe(tmp_path, [{"block": "reference-comparison",
                                      "instance_id": "block-reference-comparison"}])
    _render_with_fakes(tmp_path, monkeypatch, bundle, recipe)
    sidecar = json.loads((tmp_path / "render" / "provenance.json").read_text())
    reference = next(entry for entry in sidecar["composition"]["instances"]
                     if entry["block"] == "reference-comparison")
    assert reference["topic"] is None
    assert reference["binding"] == "deterministic"
    assert sidecar["blocks"][0]["subject"] == "virus"


def test_v2_repeated_reference_comparison_still_rejected(tmp_path):
    with pytest.raises(ValueError, match="Repeated reference-comparison"):
        publish.load_composition(write_recipe(
            tmp_path, [{"block": "reference-comparison", "instance_id": "ref-one", "topic": "virus"},
                       {"block": "reference-comparison", "instance_id": "ref-two", "topic": "virus"}],
            contract=publish.COMPOSITION_CONTRACT_V2))
