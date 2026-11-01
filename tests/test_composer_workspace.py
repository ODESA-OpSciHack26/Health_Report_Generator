"""Composition workbench: same-audience recipe copies, bounded edits, preview and replay.

The preview boundary is exercised with a stub renderer that writes the same artefact names as
`publish.render`, plus a real `publish.build_provenance` on a synthetic saved bundle. Nothing
here claims Quarto or browser behaviour; the real renders are recorded in an evidence directory.
"""
import json
import os
import shlex
from pathlib import Path

import pytest

import composer_workspace as ws
import publish
from test_composer_contracts import sha256
from test_composer_series import build_series_bundle

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "scripts/health_pipeline/config/composer/compositions"
AUDIENCES = ("researcher", "health_institution", "public")

SOURCES = ("dataset_id,topic,source_system,source_file,publishing_date,used,sha256,"
           "metadata_sha256\n"
           "ds1,virus,mandatory_reporting_system,data/virus/data.csv,2026-10-01,True,"
           + "b" * 64 + "," + "c" * 64 + "\n")
CHECKS = "dataset_id,check,status,detail\nds1,value_present,PASS,\n"


def provenance_bundle(tmp_path, **kwargs):
    """The series fixture plus the two saved files `build_provenance` reads.

    The extra rows are fixture bookkeeping so a real provenance record can be built; they
    describe no additional observation.
    """
    built = build_series_bundle(tmp_path, **kwargs)
    bundle = built["bundle"]
    (bundle / "sources.csv").write_text(SOURCES, encoding="utf-8")
    (bundle / "checks.csv").write_text(CHECKS, encoding="utf-8")
    manifest = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))
    for name in ("sources.csv", "checks.csv"):
        manifest["files"][name] = sha256(bundle / name)
    # A real bundle manifest names its snapshot; the series fixture leaves that to callers.
    manifest.setdefault("snapshot_id",
                        json.loads((bundle / "snapshot.json").read_text(encoding="utf-8"))["snapshot_id"])
    (bundle / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    return built


def stub_render(bundle, output, fmt, quarto, provenance, provenance_out, composition):
    """Stand-in for publish.render: same output names, no Quarto, no chart work."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    Path(provenance_out).write_text(json.dumps(provenance), encoding="utf-8")
    output.write_text("<html>stub</html>", encoding="utf-8")
    (output.parent / "methods.html").write_text("<html>stub</html>", encoding="utf-8")
    (output.parent / "data").mkdir(exist_ok=True)


def failing_render(*args, **kwargs):
    raise RuntimeError("synthetic render failure")


def workspace(tmp_path, name="ws"):
    return ws.create_workspace(tmp_path / name)


# ------------------------------------------------------------------ opening and copying

@pytest.mark.parametrize("audience", AUDIENCES)
def test_maintained_recipes_open_and_name_their_audience(audience):
    recipe = ws.open_recipe(RECIPES / f"{audience}.json")
    assert recipe["audience"] == audience
    assert recipe["contract"] == publish.COMPOSITION_CONTRACT_V2
    assert ws.recipe_digest(recipe) == ws.recipe_digest(json.loads(json.dumps(recipe)))


def test_published_style_recipe_opens_after_copy(tmp_path):
    # A published package ships reproduction/composition.json; the workbench opens any valid file.
    published = tmp_path / "reproduction"
    published.mkdir()
    source = RECIPES / "researcher.json"
    (published / "composition.json").write_bytes(source.read_bytes())
    recipe = ws.open_recipe(published / "composition.json")
    assert recipe["audience"] == "researcher"


def test_copy_preserves_source_bytes_and_refuses_overwrite(tmp_path):
    area = workspace(tmp_path)
    source = RECIPES / "researcher.json"
    target = ws.copy_recipe(area, source)
    assert target.read_bytes() == source.read_bytes()
    assert ws.file_digest(target) == ws.file_digest(source)
    with pytest.raises(ws.WorkspaceError, match="Refusing to overwrite"):
        ws.copy_recipe(area, source)
    assert target.read_bytes() == source.read_bytes()


def test_workspace_is_never_reused(tmp_path):
    ws.create_workspace(tmp_path / "once")
    with pytest.raises(ws.WorkspaceError, match="already exists"):
        ws.create_workspace(tmp_path / "once")


def test_recipe_names_cannot_traverse_or_escape(tmp_path):
    area = workspace(tmp_path)
    source = RECIPES / "public.json"
    for name in ("../escape.json", "/abs.json", ".hidden.json", "sub/dir.json", "no-extension"):
        with pytest.raises(ws.WorkspaceError):
            ws.copy_recipe(area, source, name)
    assert not (tmp_path / "escape.json").exists()
    assert not (tmp_path / "abs.json").exists()


def test_recipe_outside_the_workspace_is_refused(tmp_path):
    area = workspace(tmp_path)
    with pytest.raises(ws.WorkspaceError, match="outside the workspace"):
        ws.preview(area, RECIPES / "researcher.json", bundle=tmp_path / "missing",
                   render=stub_render)


def test_workspace_for_finds_the_owner_and_rejects_elsewhere(tmp_path):
    area = workspace(tmp_path)
    saved = ws.copy_recipe(area, RECIPES / "researcher.json")
    assert ws.workspace_for(saved) == area
    with pytest.raises(ws.WorkspaceError, match="not inside a workbench workspace"):
        ws.workspace_for(RECIPES / "researcher.json")


# ------------------------------------------------------------------ bounded edits

def test_edited_recipe_saves_and_reopens_unchanged(tmp_path):
    area = workspace(tmp_path)
    saved = ws.copy_recipe(area, RECIPES / "researcher.json")
    original = ws.open_recipe(saved)
    edited = ws.move_block(original, "block-coverage-selection", "down")
    edited = ws.set_block_option(edited, "researcher-series-collection",
                                 "presentation.default_topic", "influenza")
    ws.save_in_place(area, saved, edited)
    reopened = ws.open_recipe(saved)
    assert reopened == edited
    assert [entry["instance_id"] for entry in reopened["blocks"]][:3] == [
        "intro-0001", "researcher-series-collection", "block-sensitivity-comparison"]
    assert [entry["instance_id"] for entry in original["blocks"]] == [
        "intro-0001", "researcher-series-collection", "block-coverage-selection",
        "block-sensitivity-comparison", "block-reference-comparison", "limitations-0001",
        "reproduction-0001"]
    assert reopened["blocks"][1]["presentation"]["default_topic"] == "influenza"


def test_reordering_changes_only_the_order(tmp_path):
    recipe = ws.open_recipe(RECIPES / "researcher.json")
    moved = ws.move_block(recipe, "block-reference-comparison", "up")
    assert sorted(moved["blocks"], key=lambda entry: entry["instance_id"]) == sorted(
        recipe["blocks"], key=lambda entry: entry["instance_id"])
    assert moved["blocks"] != recipe["blocks"]


def test_move_boundaries_are_reported(tmp_path):
    recipe = ws.open_recipe(RECIPES / "researcher.json")
    with pytest.raises(ws.WorkspaceError, match="already at the top"):
        ws.move_block(recipe, "intro-0001", "up")
    with pytest.raises(ws.WorkspaceError, match="already at the bottom"):
        ws.move_block(recipe, "reproduction-0001", "down")
    with pytest.raises(ws.WorkspaceError, match="Unknown block instance"):
        ws.move_block(recipe, "not-a-block", "up")


def test_only_supported_options_are_accepted(tmp_path):
    recipe = ws.open_recipe(RECIPES / "health_institution.json")
    with pytest.raises(ws.WorkspaceError, match="does not support"):
        ws.set_block_option(recipe, "hi-monitoring-overview", "presentation.style", "compact")
    with pytest.raises(ws.WorkspaceError, match="Unsupported style"):
        ws.set_block_option(recipe, "hi-series-collection", "presentation.style", "fancy")
    with pytest.raises(ws.WorkspaceError, match="No value supplied"):
        ws.set_block_option(recipe, "hi-series-collection", "presentation.default_topic", "")
    edited = ws.set_block_option(recipe, "hi-reference-0001", "topic", "influenza")
    assert next(entry for entry in edited["blocks"]
                if entry["instance_id"] == "hi-reference-0001")["topic"] == "influenza"


@pytest.mark.parametrize("mutate,message", [
    (lambda recipe: recipe["blocks"].append({"block": "sparkline", "instance_id": "x-1"}),
     "Unknown block type"),
    (lambda recipe: recipe["blocks"].append(dict(recipe["blocks"][0])), "Duplicate block instance id"),
    (lambda recipe: recipe["blocks"][0].update({"instance_id": "BAD ID"}),
     "Invalid block instance id"),
    (lambda recipe: recipe.update({"extra": 1}), "Unsupported composition fields"),
])
def test_loader_rejections_are_surfaced_and_nothing_is_written(tmp_path, mutate, message):
    area = workspace(tmp_path)
    recipe = ws.open_recipe(RECIPES / "researcher.json")
    mutate(recipe)
    with pytest.raises(ws.WorkspaceError) as caught:
        ws.save_recipe(area, recipe, "rejected.json")
    assert message in str(caught.value) or "loader" in str(caught.value)
    assert not (area / "rejected.json").exists()


def test_collection_and_trend_cannot_be_combined(tmp_path):
    recipe = ws.open_recipe(RECIPES / "researcher.json")
    recipe = ws.validate_recipe(recipe)
    blocks = list(recipe["blocks"])
    blocks.insert(1, {"block": "series-trend", "instance_id": "extra-trend",
                      "topic": "influenza", "measure": "cases"})
    with pytest.raises(ws.WorkspaceError, match="cannot combine series-trend and series-collection"):
        ws.validate_recipe({**recipe, "blocks": blocks})


def test_default_topic_edit_changes_only_the_collection_identity(tmp_path):
    bundle = build_series_bundle(tmp_path, extra_topics=(("influenza", ((2021, "10.0"),
                                                                       (2025, "12.0"))),))
    topics = ["virus", "influenza"]

    def build(presentation, order=topics):
        return publish.build_series_collection(
            bundle["bundle"], ROOT, "ws-collection", order, "cases", None, presentation)

    base = build({"style": "standard", "default_topic": "virus"})
    moved = build({"style": "standard", "default_topic": "influenza"})
    assert base["identities"]["collection"] != moved["identities"]["collection"]
    for left, right in zip(base["members"], moved["members"]):
        assert left["identities"] == right["identities"]
    # Reordering the collection is a presentation change: the collection identity moves, the
    # members' analytical/rows/instance identities do not.
    reordered = build({"style": "standard", "default_topic": "virus"},
                      order=["influenza", "virus"])
    assert reordered["identities"]["collection"] != base["identities"]["collection"]
    by_topic = {member["selection"]["topic"]: member["identities"]
                for member in base["members"]}
    for member in reordered["members"]:
        assert member["identities"] == by_topic[member["selection"]["topic"]]


# ------------------------------------------------------------------ preview boundary

def test_preview_records_status_and_creates_no_promotion(tmp_path):
    area = workspace(tmp_path)
    saved = ws.copy_recipe(area, RECIPES / "researcher.json")
    bundle = provenance_bundle(tmp_path)
    outside = tmp_path / "accepted-output"
    outside.mkdir()
    (outside / "accepted.json").write_text("{}", encoding="utf-8")
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

    result = ws.preview(area, saved, bundle=bundle["bundle"], render=stub_render)

    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    created = set(after) - set(before)
    assert all(item.startswith(("ws/previews/", "results/")) for item in created)
    assert (outside / "accepted.json").read_text(encoding="utf-8") == "{}"
    assert result.directory.is_dir()
    assert result.recipe_sha256 == ws.file_digest(saved)
    metadata = json.loads((result.directory / "preview.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "preview"
    assert metadata["published"] is False
    assert metadata["accepted_output"] is False
    assert metadata["notice"] == ws.PREVIEW_NOTICE
    provenance = json.loads((result.directory / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["preview"] == {"status": "preview", "notice": ws.PREVIEW_NOTICE,
                                     "accepted_output": False}
    assert result.report.is_file() and result.methods.is_file()
    assert (result.directory / "composition.json").read_bytes() == saved.read_bytes()


def test_preview_directories_are_unique(tmp_path):
    area = workspace(tmp_path)
    saved = ws.copy_recipe(area, RECIPES / "researcher.json")
    bundle = provenance_bundle(tmp_path)
    first = ws.preview(area, saved, bundle=bundle["bundle"], render=stub_render)
    second = ws.preview(area, saved, bundle=bundle["bundle"], render=stub_render)
    assert first.directory != second.directory
    assert first.report.is_file() and second.report.is_file()


def test_preview_refuses_a_different_audience(tmp_path):
    area = workspace(tmp_path)
    saved = ws.copy_recipe(area, RECIPES / "public.json")
    bundle = provenance_bundle(tmp_path)
    with pytest.raises(ws.WorkspaceError, match="same-audience"):
        ws.preview(area, saved, bundle=bundle["bundle"], render=stub_render)


def test_failed_preview_preserves_previous_output(tmp_path):
    area = workspace(tmp_path)
    saved = ws.copy_recipe(area, RECIPES / "researcher.json")
    bundle = provenance_bundle(tmp_path)
    good = ws.preview(area, saved, bundle=bundle["bundle"], render=stub_render)
    good_bytes = (good.directory / "report.html").read_bytes()
    with pytest.raises(ws.WorkspaceError, match="Preview failed"):
        ws.preview(area, saved, bundle=bundle["bundle"], render=failing_render)
    assert (good.directory / "report.html").read_bytes() == good_bytes
    failed = [path for path in (area / "previews").iterdir() if path != good.directory]
    assert len(failed) == 1
    metadata = json.loads((failed[0] / "preview.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert not (failed[0] / "report.html").exists()
    assert saved.read_bytes() == (RECIPES / "researcher.json").read_bytes()


def test_symlinked_previews_directory_is_refused(tmp_path):
    area = workspace(tmp_path)
    saved = ws.copy_recipe(area, RECIPES / "researcher.json")
    (area / "previews").rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, area / "previews")
    bundle = provenance_bundle(tmp_path)
    with pytest.raises(ws.WorkspaceError, match="symlinked previews"):
        ws.preview(area, saved, bundle=bundle["bundle"], render=stub_render)
    assert not any(outside.iterdir())


def test_default_provenance_has_no_preview_marker(tmp_path):
    bundle = provenance_bundle(tmp_path)
    plain = publish.build_provenance(bundle["bundle"], "html")
    assert "preview" not in plain
    marked = publish.build_provenance(bundle["bundle"], "html", preview=True)
    assert marked["preview"]["status"] == "preview"
    assert marked["preview"]["accepted_output"] is False


# ------------------------------------------------------------------ replay command

def test_replay_command_quotes_paths_with_spaces(tmp_path):
    area = ws.create_workspace(tmp_path / "my workspace")
    saved = ws.copy_recipe(area, RECIPES / "researcher.json", "my recipe.json")
    argv, text = ws.replay_command(recipe_path=saved, bundle=tmp_path / "bundle dir",
                                   output_dir=area / "replay out",
                                   data_root=tmp_path / "data root")
    assert shlex.split(text) == argv
    assert "'" in text and str(saved) in text
    assert argv[:3] == ["python", argv[1], "html"]
    assert argv[1].endswith("publish.py")
    assert "--composition" in argv and "--provenance" in argv


def test_replay_reproduces_the_saved_recipe(tmp_path):
    area = workspace(tmp_path)
    saved = ws.copy_recipe(area, RECIPES / "researcher.json")
    recipe = ws.open_recipe(saved)
    edited = ws.set_block_option(recipe, "researcher-series-collection",
                                 "presentation.default_topic", "influenza")
    ws.save_in_place(area, saved, edited)
    argv, _ = ws.replay_command(recipe_path=saved, bundle=tmp_path / "bundle",
                                output_dir=area / "replay")
    composition = argv[argv.index("--composition") + 1]
    replayed = publish.load_composition(composition)
    assert replayed == ws.open_recipe(saved) == edited


def test_discard_pending_keeps_unrelated_selection_and_exclusions(tmp_path):
    draft = ws.Draft(
        root=tmp_path,
        recipe={"audience": "researcher", "blocks": []},
        editor={
            "pending": [{"instance_id": "pending-1", "entry": {"block": "series-trend"}}],
            "selection": {"keep-1": {"topics": ["alpha"]}, "pending-1": {"topics": ["beta"]}},
            "excluded": ["keep-2", "pending-1"],
            "retired": [],
            "next_seq": 4,
        },
    )
    result = ws.discard_pending(draft, "pending-1")
    assert result["pending"] == []
    assert result["selection"] == {"keep-1": {"topics": ["alpha"]}}
    assert result["excluded"] == ["keep-2"]
    assert "pending-1" in result["retired"]
