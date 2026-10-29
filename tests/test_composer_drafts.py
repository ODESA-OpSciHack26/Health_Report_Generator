"""Managed drafts: one saved copy per audience, editor-only inclusion state beside the recipe.

The composition schema is untouched: these tests check that exclusion lives in editor state,
that the effective recipe omits excluded sections, and that validation happens before writing.
"""
import hashlib
import json
from pathlib import Path

import pytest

import composer_workspace as ws
import publish

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "scripts/health_pipeline/config/composer/compositions"


def draft_for(tmp_path, audience="researcher"):
    return ws.create_draft(tmp_path / audience, RECIPES / f"{audience}.json",
                           based_on=audience)


def test_create_draft_is_a_byte_copy_and_resumes(tmp_path):
    draft = draft_for(tmp_path)
    assert (draft.root / ws.DRAFT_RECIPE).read_bytes() == \
        (RECIPES / "researcher.json").read_bytes()
    assert draft.audience == "researcher"
    assert draft.revision == 0 and draft.excluded == ()
    assert [entry["instance_id"] for entry in draft.effective()["blocks"]] == \
        [entry["instance_id"] for entry in draft.recipe["blocks"]]
    again = ws.create_draft(draft.root, RECIPES / "researcher.json")
    assert again.root == draft.root and again.revision == draft.revision


def test_open_draft_rejects_a_missing_or_tampered_copy(tmp_path):
    with pytest.raises(ws.WorkspaceError, match="No saved draft"):
        ws.open_draft(tmp_path / "absent")
    draft = draft_for(tmp_path)
    editor_path = draft.root / ws.DRAFT_EDITOR
    editor = json.loads(editor_path.read_text(encoding="utf-8"))
    editor["excluded"] = ["not-a-block"]
    editor_path.write_text(json.dumps(editor), encoding="utf-8")
    with pytest.raises(ws.WorkspaceError, match="does not contain"):
        ws.open_draft(draft.root)

    editor["excluded"] = ["limitations-0001"]
    editor_path.write_text(json.dumps(editor), encoding="utf-8")
    with pytest.raises(ws.WorkspaceError, match="Required"):
        ws.open_draft(draft.root)

    editor["excluded"] = []
    editor["revision"] = -1
    editor_path.write_text(json.dumps(editor), encoding="utf-8")
    with pytest.raises(ws.WorkspaceError, match="revision"):
        ws.open_draft(draft.root)


def test_exclusion_omits_the_section_from_the_effective_recipe(tmp_path):
    draft = draft_for(tmp_path)
    full = draft.effective()
    draft = ws.set_inclusion(draft, "block-coverage-selection", False)
    effective = draft.effective()
    assert "block-coverage-selection" in [entry["instance_id"] for entry in full["blocks"]]
    assert "block-coverage-selection" not in [entry["instance_id"] for entry in effective["blocks"]]
    # The saved recipe still holds every block, so restoring cannot lose settings.
    assert "block-coverage-selection" in [entry["instance_id"] for entry in draft.recipe["blocks"]]
    assert draft.revision == 1
    publish.validate_composition(effective)          # the effective view is still valid


def test_restoring_a_section_restores_order_and_settings(tmp_path):
    draft = draft_for(tmp_path)
    draft = ws.set_draft_option(draft, "researcher-series-collection",
                                "presentation.style", "compact")
    digest_before = ws.draft_digest(draft)
    order_before = [entry["instance_id"] for entry in draft.effective()["blocks"]]
    draft = ws.set_inclusion(draft, "block-coverage-selection", False)
    assert ws.draft_digest(draft) != digest_before
    draft = ws.set_inclusion(draft, "block-coverage-selection", True)
    assert ws.draft_digest(draft) == digest_before
    assert [entry["instance_id"] for entry in draft.effective()["blocks"]] == order_before
    collection = next(entry for entry in draft.effective()["blocks"]
                      if entry["instance_id"] == "researcher-series-collection")
    assert collection["presentation"]["style"] == "compact"


def test_moves_skip_excluded_sections(tmp_path):
    draft = draft_for(tmp_path)
    draft = ws.set_inclusion(draft, "block-sensitivity-comparison", False)
    draft = ws.move_included(draft, "block-coverage-selection", "up")
    visible = [entry["instance_id"] for entry in draft.effective()["blocks"]]
    # coverage-selection swaps with the collection above it; the excluded block stays put.
    assert visible[:3] == ["intro-0001", "block-coverage-selection",
                           "researcher-series-collection"]
    assert "block-sensitivity-comparison" not in visible
    with pytest.raises(ws.WorkspaceError, match="not included"):
        ws.move_included(draft, "block-sensitivity-comparison", "up")


def test_required_and_last_sections_are_guarded(tmp_path):
    draft = draft_for(tmp_path)
    with pytest.raises(ws.WorkspaceError, match="Required"):
        ws.set_inclusion(draft, "limitations-0001", False)
    with pytest.raises(ws.WorkspaceError, match="Required"):
        ws.set_inclusion(draft, "reproduction-0001", False)

    # A composition with no required block type still may not be emptied.
    synthetic = ws.Draft(
        root=tmp_path / "synthetic",
        recipe={"contract": publish.COMPOSITION_CONTRACT_V2, "audience": "researcher",
                "blocks": [{"block": "intro", "instance_id": "intro-0001"},
                           {"block": "coverage-selection",
                            "instance_id": "block-coverage-selection"}]},
        editor={"schema": ws.DRAFT_SCHEMA, "audience": "researcher",
                "excluded": ["intro-0001"], "revision": 0})
    with pytest.raises(ws.WorkspaceError, match="at least one included"):
        ws.set_inclusion(synthetic, "block-coverage-selection", False)


def test_edit_plan_writes_nothing(tmp_path):
    draft = draft_for(tmp_path)
    recipe_path = draft.root / ws.DRAFT_RECIPE
    editor_path = draft.root / ws.DRAFT_EDITOR
    before = (hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
              hashlib.sha256(editor_path.read_bytes()).hexdigest())
    recipe, excluded = ws.edit_plan(draft, "exclude", "block-coverage-selection")
    # Exclusion is editor state: the planned recipe is still the complete recipe.
    assert recipe == draft.recipe
    assert excluded == ["block-coverage-selection"]
    assert (hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
            hashlib.sha256(editor_path.read_bytes()).hexdigest()) == before
    with pytest.raises(ws.WorkspaceError):
        ws.edit_plan(draft, "exclude", "limitations-0001")
    assert (hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
            hashlib.sha256(editor_path.read_bytes()).hexdigest()) == before


def test_noop_edits_do_not_move_the_revision(tmp_path):
    draft = draft_for(tmp_path)
    recipe, excluded = ws.edit_plan(draft, "include", "intro-0001")
    assert ws.commit_edit(draft, recipe, excluded).revision == 0
    draft = ws.set_inclusion(draft, "intro-0001", False)
    assert draft.revision == 1
    same = ws.set_inclusion(draft, "intro-0001", False)
    assert same.revision == 1


def test_default_topic_and_style_survive_reopen(tmp_path):
    draft = draft_for(tmp_path)
    draft = ws.set_draft_option(draft, "researcher-series-collection",
                                "presentation.default_topic", "influenza")
    draft = ws.set_draft_option(draft, "researcher-series-collection",
                                "presentation.style", "compact")
    reopened = ws.open_draft(draft.root)
    collection = next(entry for entry in reopened.recipe["blocks"]
                      if entry["instance_id"] == "researcher-series-collection")
    assert collection["presentation"] == {"style": "compact", "default_topic": "influenza"}
    assert ws.draft_digest(reopened) == ws.draft_digest(draft)


def test_unsupported_options_are_refused(tmp_path):
    draft = draft_for(tmp_path)
    with pytest.raises(ws.WorkspaceError, match="does not support"):
        ws.set_draft_option(draft, "intro-0001", "presentation.style", "compact")
    with pytest.raises(ws.WorkspaceError, match="Unsupported style"):
        ws.set_draft_option(draft, "researcher-series-collection", "presentation.style", "fancy")
    with pytest.raises(ws.WorkspaceError, match="No value supplied"):
        ws.set_draft_option(draft, "researcher-series-collection",
                            "presentation.default_topic", "")


# ------------------------------------------------------------------ pending selection

COLLECTION = "researcher-series-collection"
ELIGIBLE = ["campylobacteriosis", "influenza"]


def selected(draft, topics, default=None):
    selection, note = ws.plan_selection(draft, "set-topics", COLLECTION, topics, ELIGIBLE)
    if default is not None:
        selection, _ = ws.plan_selection(
            ws.Draft(root=draft.root, recipe=draft.recipe,
                     editor={**draft.editor, "selection": selection}),
            "set-default-open", COLLECTION, default, ELIGIBLE)
    return ws.commit_selection(draft, selection), note


def test_pending_selection_is_pure_and_complete(tmp_path):
    draft = draft_for(tmp_path)
    before = (draft.recipe_path.read_bytes(),
              (draft.root / ws.DRAFT_EDITOR).read_bytes())
    selection, note = ws.plan_selection(draft, "set-topics", COLLECTION, ["influenza"], ELIGIBLE)
    assert selection[COLLECTION]["topics"] == ["influenza"]
    assert note == {"kind": "default-open-moved", "from": "campylobacteriosis",
                    "to": "influenza"}
    after = (draft.recipe_path.read_bytes(),
             (draft.root / ws.DRAFT_EDITOR).read_bytes())
    assert before == after                    # planning writes nothing
    draft = ws.commit_selection(draft, selection)
    assert draft.revision == 1
    assert draft.selection[COLLECTION]["topics"] == ["influenza"]
    assert draft.pending_ready() is True
    pending = draft.pending()
    entry = next(item for item in pending["blocks"] if item["instance_id"] == COLLECTION)
    assert entry["topics"] == ["influenza"]
    assert entry["presentation"]["default_topic"] == "influenza"
    # The saved recipe is untouched until a generation commits the choice.
    assert draft.recipe["blocks"][1]["topics"] == "eligible"


def test_empty_pending_selection_is_invalid_but_recoverable(tmp_path):
    draft = draft_for(tmp_path)
    draft, _ = selected(draft, [])
    problem = draft.pending_problem()
    assert problem["kind"] == "empty-selection"
    assert problem["instance_id"] == COLLECTION
    assert draft.pending_ready() is False
    draft.effective()                          # the last accepted recipe still validates
    assert draft.selection[COLLECTION]["topics"] == []
    # Re-checking a disease makes it renderable again without losing the rest of the state.
    draft, _ = selected(draft, ["influenza"])
    assert draft.pending_ready() is True


def test_default_open_must_be_checked(tmp_path):
    draft = draft_for(tmp_path)
    selection, _ = ws.plan_selection(draft, "set-topics", COLLECTION, ["influenza"], ELIGIBLE)
    draft = ws.commit_selection(draft, selection)
    with pytest.raises(ws.WorkspaceError, match="one of the checked"):
        ws.plan_selection(draft, "set-default-open", COLLECTION, "campylobacteriosis", ELIGIBLE)
    selection, _ = ws.plan_selection(draft, "set-default-open", COLLECTION, "influenza", ELIGIBLE)
    assert selection[COLLECTION]["default_topic"] == "influenza"
    draft = ws.commit_selection(draft, selection)
    # Unchecking the open disease moves the choice to the first remaining one, with a note.
    selection, note = ws.plan_selection(draft, "set-topics", COLLECTION, [], ELIGIBLE)
    assert note == {"kind": "default-open-cleared", "from": "influenza"}
    assert selection[COLLECTION]["default_topic"] is None


def test_selection_survives_exclusion_and_restore(tmp_path):
    draft = draft_for(tmp_path)
    draft, _ = selected(draft, ["influenza"])
    draft = ws.set_inclusion(draft, COLLECTION, False)
    assert draft.selection[COLLECTION]["topics"] == ["influenza"]
    assert COLLECTION not in [entry["instance_id"] for entry in draft.pending()["blocks"]]
    draft = ws.set_inclusion(draft, COLLECTION, True)
    assert draft.selection[COLLECTION]["topics"] == ["influenza"]
    assert draft.pending_ready() is True


def test_commit_pending_writes_the_recipe_and_normalises_a_full_set(tmp_path):
    draft = draft_for(tmp_path)
    draft, _ = selected(draft, ["influenza"], default="influenza")
    draft = ws.commit_pending(draft, ELIGIBLE)
    assert draft.selection == {}
    entry = next(item for item in draft.recipe["blocks"] if item["instance_id"] == COLLECTION)
    assert entry["topics"] == ["influenza"]
    assert entry["presentation"]["default_topic"] == "influenza"

    draft2 = ws.create_draft(tmp_path / "full", RECIPES / "researcher.json")
    draft2, _ = selected(draft2, list(ELIGIBLE), default="campylobacteriosis")
    draft2 = ws.commit_pending(draft2, ELIGIBLE)
    entry2 = next(item for item in draft2.recipe["blocks"]
                  if item["instance_id"] == COLLECTION)
    assert entry2["topics"] == "eligible"      # full set in bundle order == the default
    assert draft2.pending_ready() is True


def test_reset_restores_the_default_copy_in_place(tmp_path):
    draft = draft_for(tmp_path)
    draft, _ = selected(draft, ["influenza"])
    draft = ws.set_inclusion(draft, "block-coverage-selection", False)
    revision = draft.revision
    draft = ws.reset_draft(draft, RECIPES / "researcher.json", based_on="researcher")
    assert draft.recipe_path.read_bytes() == (RECIPES / "researcher.json").read_bytes()
    assert draft.excluded == () and draft.selection == {}
    assert draft.revision == revision + 1
    assert draft.recipe["audience"] == "researcher"


def test_legacy_editor_state_without_selection_still_reads(tmp_path):
    draft = draft_for(tmp_path)
    editor_path = draft.root / ws.DRAFT_EDITOR
    legacy = json.loads(editor_path.read_text(encoding="utf-8"))
    legacy["schema"] = ws.DRAFT_SCHEMA
    legacy.pop("selection", None)
    editor_path.write_text(json.dumps(legacy), encoding="utf-8")
    reopened = ws.open_draft(draft.root)
    assert reopened.selection == {}
    assert reopened.pending_ready() is True


def test_bad_selection_state_is_rejected(tmp_path):
    draft = draft_for(tmp_path)
    editor_path = draft.root / ws.DRAFT_EDITOR
    base = json.loads(editor_path.read_text(encoding="utf-8"))
    for broken, pattern in (
        ({"selection": {"nope": {"topics": []}}}, "unknown block"),
        ({"selection": {COLLECTION: {"topics": ["Bad Topic"]}}}, "invalid topics"),
        ({"selection": {COLLECTION: {"topics": ["influenza", "influenza"]}}}, "repeats"),
        ({"selection": {COLLECTION: {"topics": [], "default_topic": "Bad"}}}, "default topic"),
        ({"selection": {COLLECTION: {"topics": [], "extra": 1}}}, "unsupported fields"),
    ):
        editor_path.write_text(json.dumps({**base, **broken}), encoding="utf-8")
        with pytest.raises(ws.WorkspaceError, match=pattern):
            ws.open_draft(draft.root)


def test_pending_digest_is_computable_for_invalid_state(tmp_path):
    draft = draft_for(tmp_path)
    base = ws.pending_digest(draft)
    draft, _ = selected(draft, [])
    assert ws.pending_digest(draft) != base
    assert ws.pending_ready(draft) is False
