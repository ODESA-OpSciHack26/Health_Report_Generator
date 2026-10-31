"""Custom block-library composer: library inventory, capability-aware addition, drafts, jobs.

The bundles here are synthetic fixtures, not findings. Probes call the real block builders
against those fixtures, so an "unavailable" reason is a builder prerequisite and not a guessed
one. Rendering is stubbed and labelled; the real end-to-end Custom render lives in the Round B1
evidence directory.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import composer_library as library  # noqa: E402
import composer_site  # noqa: E402
import composer_workspace as workbench  # noqa: E402
import publish  # noqa: E402
from test_composer_series import build_series_bundle  # noqa: E402
from test_composer_site import (RECIPES, call, payload, stub_render,  # noqa: E402
                                wait_for_job, write_bundle)  # noqa: E402

DEFAULT_ROWS = ((2019, "7253.0"), (2021, "6802.0"), (2022, "7645.0"),
                (2023, "6784.0"), (2024, "8360.0"), (2025, "8716.0"))

# --------------------------------------------------------------------------- fixtures


def build_inputs(tmp_path, audiences=("researcher", "public"), rows=DEFAULT_ROWS,
                 extra_topics=(("influenza", ((2021, "10.0"), (2025, "12.0"))),)):
    """Bundles plus the snapshot the reference builder resolves, under a site data root."""
    inputs = tmp_path / "inputs"
    for audience in audiences:
        root = tmp_path / f"build-{audience}"
        built = build_series_bundle(tmp_path, root=root, rows=list(rows),
                                    topic="campylobacteriosis", label="Campylobacteriosis",
                                    extra_topics=extra_topics, archive=True)
        bundle = built["bundle"]
        stakeholder = json.loads((bundle / "stakeholder.json").read_text(encoding="utf-8"))
        stakeholder.update({"id": audience, "years": [2021, 2025], "reference_year": 2019,
                            "geography": "CHFL"})
        (bundle / "stakeholder.json").write_text(json.dumps(stakeholder), encoding="utf-8")
        (bundle / "sources.csv").write_text(
            "dataset_id,topic,source_system,source_file,publishing_date,used,sha256,"
            "metadata_sha256\nds1,campylobacteriosis,mandatory_reporting_system,"
            "data/campylobacteriosis/data.csv,2026-10-01,True," + "b" * 64 + "," + "c" * 64
            + "\nds2,influenza,mandatory_reporting_system,data/influenza/data.csv,"
            "2026-10-01,True," + "d" * 64 + "," + "e" * 64 + "\n", encoding="utf-8")
        (bundle / "checks.csv").write_text(
            "dataset_id,check,status,detail\nds1,value_present,PASS,\n", encoding="utf-8")
        manifest = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))
        for name in ("sources.csv", "checks.csv", "stakeholder.json"):
            manifest["files"][name] = hashlib.sha256(
                (bundle / name).read_bytes()).hexdigest()
        manifest["snapshot_id"] = json.loads(
            (bundle / "snapshot.json").read_text(encoding="utf-8"))["snapshot_id"]
        (bundle / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
        destination = inputs / audience / "data"
        destination.parent.mkdir(parents=True, exist_ok=True)
        bundle.rename(destination)
        snapshots = root / "results" / "snapshots"
        # The extra topic's lineage names an archived source file; create it so the reference
        # builder's lineage check can resolve every recorded row.
        for snapshot_dir in snapshots.glob("*"):
            extra = snapshot_dir / "data" / "extra"
            extra.mkdir(parents=True, exist_ok=True)
            (extra / "data.csv").write_text("value\n10\n12\n", encoding="utf-8")
        if not (inputs / "snapshots").is_dir():
            snapshots.rename(inputs / "snapshots")
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    for audience in ("researcher", "health_institution", "public"):
        (recipes / f"{audience}.json").write_bytes((RECIPES / f"{audience}.json").read_bytes())
    return inputs, recipes


def make_custom_site(tmp_path, rows=DEFAULT_ROWS, audiences=("researcher", "public")):
    inputs, recipes = build_inputs(tmp_path, audiences=audiences, rows=rows)
    site = composer_site.Site(tmp_path / "work", inputs, inputs, recipes,
                              workflow_config=None, quarto="quarto", render=stub_render)
    server = composer_site.build_server(site, "127.0.0.1", 0)
    import threading
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host = f"127.0.0.1:{server.server_address[1]}"
    status, headers, _ = exchange(host, site.access_token)
    assert status == composer_site.HTTPStatus.FOUND, status
    from test_composer_site import SESSIONS, cookie_from
    cookie = cookie_from(headers)
    assert cookie
    SESSIONS[host] = cookie
    return site, server, host


def exchange(host, token):
    from test_composer_site import token_exchange
    return token_exchange(host, token)


@pytest.fixture()
def custom(tmp_path):
    site, server, host = make_custom_site(tmp_path)
    yield site, host
    site.wait_idle(5)
    server.shutdown()
    server.server_close()


@pytest.fixture()
def sparse(tmp_path):
    """A bundle whose rows start after the reference year: no reference change was saved."""
    rows = tuple(row for row in DEFAULT_ROWS if row[0] != 2019)
    site, server, host = make_custom_site(tmp_path, rows=rows, audiences=("public",))
    yield site, host
    site.wait_idle(5)
    server.shutdown()
    server.server_close()


# --------------------------------------------------------------------------- helpers

def document(host, context="researcher"):
    status, _, body = call(host, "GET", f"/api/custom?context={context}")
    assert status == 200, body
    return json.loads(body)


def edit(host, action, instance=None, value=None, context="researcher"):
    status, _, body = call(host, "POST", "/api/custom/edit",
                           {"context": context, "action": action, "instance": instance,
                            "value": value}, action="custom-edit")
    return status, (json.loads(body) if body else None)


def edit_ok(host, action, instance=None, value=None, context="researcher"):
    status, body = edit(host, action, instance, value, context)
    assert status == 200, body
    return body


def add(host, block, options=None, context="researcher", replace=None):
    value = {"block": block, "options": options or {}}
    if replace:
        value["replace"] = replace
    return edit(host, "add-block", None, value, context)


def generate(host, context="researcher"):
    status, _, body = call(host, "POST", "/api/generate",
                           {"preset": "custom", "context": context}, action="generate")
    return status, (json.loads(body) if body else None)


def by_block(document, block):
    return next(item for item in document["blocks"] if item["block"] == block)


def ids(document):
    return [item["instance_id"] for item in document["blocks"]]


def draft_recipe(site, context="researcher"):
    path = site.drafts_root / "custom" / context / workbench.DRAFT_RECIPE
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- library

def test_library_lists_every_offered_block_type(custom):
    _, host = custom
    doc = document(host)
    assert [item["block"] for item in doc["library"]] == list(library.composable_blocks())
    assert set(library.composable_blocks()) <= set(publish.KNOWN_BLOCKS)
    # The single-disease trend stays a registered contract, but is no longer offered as a new
    # section: one collection covers one or many diseases.
    assert "series-trend" in publish.KNOWN_BLOCKS
    assert "series-trend" not in [item["block"] for item in doc["library"]]
    publish.validate_composition({"contract": publish.COMPOSITION_CONTRACT_V2,
                                  "audience": "researcher",
                                  "blocks": [{"block": "series-trend", "instance_id": "hist-0001",
                                              "topic": "influenza", "measure": "cases"}]})
    for item in doc["library"]:
        assert item["label"] and item["description"]
        assert isinstance(item["available"], bool)
        if not item["available"]:
            assert item["reason"]


def test_availability_comes_from_the_builder_not_from_files(custom):
    _, host = custom
    doc = document(host)
    # The fixture has no saved main/sensitivity group pair, so this block must be refused with
    # a reason even though every file the bundle declares is present.
    sensitivity = next(item for item in doc["library"]
                       if item["block"] == "sensitivity-comparison")
    assert sensitivity["available"] is False
    assert sensitivity["reason"]
    status, body = add(host, "sensitivity-comparison")
    assert status == 409 and body["error"]["code"] == "block_unavailable"


def test_unavailable_block_is_not_added_and_nothing_is_written(custom):
    site, host = custom
    before = ids(document(host))
    status, body = add(host, "sensitivity-comparison")
    assert status == 409
    assert "sensitivity" in body["error"]["message"].lower() or body["error"]["message"]
    assert ids(document(host)) == before
    assert not (site.drafts_root / "custom" / "researcher").exists()


def test_reference_block_is_unavailable_without_a_saved_reference_result(sparse):
    _, host = sparse
    doc = document(host, "public")
    reference = next(item for item in doc["library"] if item["block"] == "reference-comparison")
    assert reference["available"] is False
    assert reference["reason"]
    # The same context can still build an annual series, so the refusal is specific.
    assert next(item for item in doc["library"]
                if item["block"] == "series-collection")["available"] is True


# --------------------------------------------------------------------------- composition

def test_initial_composition_is_the_evidence_floor_and_not_a_preset(custom):
    _, host = custom
    doc = document(host)
    assert [item["block"] for item in doc["blocks"]] == ["intro", "limitations", "reproduction"]
    assert doc["draft"] is False                     # opening the card writes nothing
    assert doc["ready"] is True
    preset = json.loads((RECIPES / "researcher.json").read_text(encoding="utf-8"))
    assert [entry["block"] for entry in preset["blocks"]] != \
        [item["block"] for item in doc["blocks"]]
    assert doc["different_from_preset"] is True


def test_add_remove_restore_and_reorder_keep_instance_ids(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    coverage = by_block(doc, "coverage-selection")
    first_id = coverage["instance_id"]
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection_id = by_block(doc, "series-collection")["instance_id"]
    assert ids(doc)[-2:] == [first_id, collection_id]

    doc = edit_ok(host, "move-up", collection_id)
    assert by_block(doc, "series-collection")["instance_id"] == collection_id
    assert ids(doc).index(collection_id) < ids(doc).index(first_id)

    doc = edit_ok(host, "remove", collection_id)
    assert by_block(doc, "series-collection")["included"] is False
    assert by_block(doc, "series-collection")["instance_id"] == collection_id
    assert by_block(doc, "series-collection")["options"]["topics"]   # settings kept

    doc = edit_ok(host, "restore", collection_id)
    assert by_block(doc, "series-collection")["included"] is True
    assert by_block(doc, "series-collection")["instance_id"] == collection_id

    stored = draft_recipe(site)
    assert collection_id in [entry["instance_id"] for entry in stored["blocks"]]


def test_required_sections_cannot_be_removed(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    limitations = by_block(doc, "limitations")["instance_id"]
    status, body = edit(host, "remove", limitations)
    assert status == 400 and body["error"]["code"] == "edit_rejected"
    assert "Required" in body["error"]["message"] or "required" in body["error"]["message"].lower()
    assert by_block(document(host), "limitations")["included"] is True


def test_singleton_and_mutually_exclusive_blocks_need_an_explicit_replacement(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection_id = by_block(doc, "series-collection")["instance_id"]

    status, body = add(host, "series-trend", {"topic": "influenza", "measure": "cases"})
    assert status == 409 and body["error"]["code"] == "combination_conflict"
    # Nothing was removed or added by the refused attempt.
    assert by_block(document(host), "series-collection")["included"] is True
    assert "series-trend" not in [item["block"] for item in document(host)["blocks"]]

    doc = edit_ok(host, "add-block", None, {"block": "series-trend",
                                            "options": {"topic": "influenza",
                                                        "measure": "cases"},
                                            "replace": [collection_id]})
    assert "series-collection" not in [item["block"] for item in doc["blocks"]]
    assert by_block(doc, "series-trend")["included"] is True
    assert collection_id not in ids(doc)              # retired, never reissued

    status, body = add(host, "reference-comparison", {"topic": "campylobacteriosis"})
    assert status == 200
    # A second comparison block is refused even with a valid topic for this context.
    status, body = add(host, "reference-comparison", {"topic": "campylobacteriosis"})
    assert status == 409 and body["error"]["code"] == "combination_conflict"


def test_duplication_only_where_the_contract_permits_it(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "monitoring-overview"})
    monitoring = by_block(doc, "monitoring-overview")["instance_id"]
    doc = edit_ok(host, "duplicate", monitoring)
    copies = [item for item in doc["blocks"] if item["block"] == "monitoring-overview"]
    assert len(copies) == 2
    assert copies[0]["instance_id"] != copies[1]["instance_id"]

    limitations = by_block(doc, "limitations")["instance_id"]
    status, body = edit(host, "duplicate", limitations)
    assert status == 400
    assert "cannot be duplicated" in body["error"]["message"]


def test_instance_ids_are_never_reissued_after_replacement_or_reset(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    retired = by_block(doc, "series-collection")["instance_id"]
    doc = edit_ok(host, "add-block", None, {"block": "series-trend",
                                            "options": {"topic": "influenza",
                                                        "measure": "cases"},
                                            "replace": [retired]})
    newly = by_block(doc, "series-trend")["instance_id"]
    assert newly != retired

    status, _, body = call(host, "POST", "/api/custom/reset",
                           {"context": "researcher"}, action="custom-reset")
    assert status == 200
    doc = json.loads(body)
    fresh = ids(doc)
    assert retired not in fresh and newly not in fresh
    assert set(fresh).isdisjoint({retired, newly})
    stored_editor = json.loads((site.drafts_root / "custom" / "researcher" /
                                workbench.DRAFT_EDITOR).read_text(encoding="utf-8"))
    assert retired in stored_editor["retired"] and newly in stored_editor["retired"]


def test_replacing_a_section_drops_its_exclusions_too(custom):
    """The exact sequence that left c-trend-0016 in the reviewer's excluded list."""
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-trend",
                                            "options": {"topic": "influenza",
                                                        "measure": "cases"}})
    trend = by_block(doc, "series-trend")["instance_id"]
    edit_ok(host, "remove", trend)
    editor_path = site.drafts_root / "custom" / "researcher" / workbench.DRAFT_EDITOR
    assert trend in json.loads(editor_path.read_text(encoding="utf-8"))["excluded"]

    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"},
                                            "replace": [trend]})
    stored = json.loads(editor_path.read_text(encoding="utf-8"))
    assert trend not in stored["excluded"]          # no orphaned exclusion
    assert trend in stored["retired"]               # history is kept
    assert trend not in ids(doc)
    assert document(host)["needs_repair"] == []     # reopens cleanly
    workbench.open_draft(editor_path.parent)


def test_stale_editor_references_block_generation_until_explicitly_repaired(custom):
    site, host = custom
    edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    editor_path = site.drafts_root / "custom" / "researcher" / workbench.DRAFT_EDITOR
    recipe_path = site.drafts_root / "custom" / "researcher" / workbench.DRAFT_RECIPE
    recipe_before = recipe_path.read_bytes()
    before = json.loads(editor_path.read_text(encoding="utf-8"))
    broken = json.loads(json.dumps(before))
    broken["excluded"] = list(broken["excluded"]) + ["c-trend-9999"]
    broken["selection"]["c-trend-9998"] = {"topics": ["influenza"]}
    editor_path.write_text(json.dumps(broken), encoding="utf-8")

    reopened = document(host)                       # opens, does not rewrite
    assert reopened["needs_repair"] == ["c-trend-9998", "c-trend-9999"]
    assert reopened["ready"] is False
    assert "Repair the draft" in reopened["blocking_reason"]
    assert json.loads(editor_path.read_text(encoding="utf-8")) == broken   # untouched

    status, body = generate(host)
    assert status == 400 and body["error"]["code"] == "draft_not_ready"

    repaired = edit_ok(host, "repair-draft")
    assert repaired["needs_repair"] == [] and repaired["ready"] is True
    stored = json.loads(editor_path.read_text(encoding="utf-8"))
    assert "c-trend-9999" not in stored["excluded"]
    assert "c-trend-9998" not in stored["selection"]
    assert recipe_path.read_bytes() == recipe_before   # composition untouched
    assert stored["repairs"][-1]["removed"] == ["c-trend-9998", "c-trend-9999"]


def test_repair_keeps_valid_exclusions_and_settings(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "monitoring-overview"})
    monitoring = by_block(doc, "monitoring-overview")["instance_id"]
    edit_ok(host, "remove", monitoring)
    editor_path = site.drafts_root / "custom" / "researcher" / workbench.DRAFT_EDITOR
    broken = json.loads(editor_path.read_text(encoding="utf-8"))
    broken["excluded"].append("c-gone-0001")
    editor_path.write_text(json.dumps(broken), encoding="utf-8")

    repaired = edit_ok(host, "repair-draft")
    stored = json.loads(editor_path.read_text(encoding="utf-8"))
    assert stored["excluded"] == [monitoring]       # the valid exclusion survives
    assert monitoring in ids(repaired) and by_block(repaired, "monitoring-overview")["included"] is False


def test_an_existing_single_trend_draft_still_opens_and_renders(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-trend",
                                            "options": {"topic": "influenza",
                                                        "measure": "cases"}})
    reopened = document(host)
    trend = by_block(reopened, "series-trend")
    assert trend["included"] is True and trend["label"] == "Annual trend for one disease"
    assert set(trend["editable"]) == {"topic", "measure", "years", "style"}
    # It is not offered as a *new* section by this composer.
    assert "series-trend" not in [item["block"] for item in reopened["library"]]


def test_display_labels_are_reader_facing_not_ids(custom):
    _, host = custom
    doc = document(host)
    assert doc["topic_labels"]["influenza"] == "Influenza"
    assert doc["topic_labels"]["campylobacteriosis"] == "Campylobacteriosis"
    assert "influenza" in doc["eligible_topics"]          # the canonical id is unchanged
    assert all(topic in doc["eligible_topics"] for topic in doc["topic_labels"])
    assert all(label != topic for topic, label in doc["topic_labels"].items())
    # The curated labels used by the retained bundle, independent of the synthetic fixture.
    assert library.display_label("hepatitis_a") == "Hepatitis A"
    assert library.display_label("hiv") == "HIV"
    assert library.display_label("unknown_topic") == "unknown_topic"


# --------------------------------------------------------------------------- options

def test_saved_result_selection_changes_the_binding_not_the_instance(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-trend",
                                            "options": {"topic": "campylobacteriosis",
                                                        "measure": "cases"}})
    entry = by_block(doc, "series-trend")
    instance = entry["instance_id"]
    assert entry["options"]["topic"] == "campylobacteriosis"
    # Both diseases have saved annual rows in this context, so both are offered.
    assert set(doc["topics_by_measure"]["cases"]) == {"campylobacteriosis", "influenza"}

    doc = edit_ok(host, "set-option", instance,
                  {"option": "topic", "value": "influenza"})
    entry = by_block(doc, "series-trend")
    assert entry["instance_id"] == instance          # identity is not regenerated
    assert entry["options"]["topic"] == "influenza"

    # The saved reference result exists for one disease only; that binds a different record.
    doc = edit_ok(host, "add-block", None, {"block": "reference-comparison",
                                            "options": {"topic": "campylobacteriosis"}})
    assert doc["reference_topics"] == ["campylobacteriosis"]


def test_option_values_outside_the_saved_context_are_refused(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "reference-comparison",
                                            "options": {"topic": "campylobacteriosis"}})
    instance = by_block(doc, "reference-comparison")["instance_id"]
    for missing in ("shigellosis", "influenza"):
        status, body = edit(host, "set-option", instance,
                            {"option": "topic", "value": missing})
        assert status == 409 and body["error"]["code"] == "saved_result_unavailable"
    assert by_block(document(host), "reference-comparison")["options"]["topic"] == \
        "campylobacteriosis"

    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection = by_block(doc, "series-collection")["instance_id"]
    status, body = edit(host, "set-option", collection,
                        {"option": "years", "value": [2019, 2025]})
    assert status == 400 and body["error"]["code"] == "invalid_years"
    doc = edit_ok(host, "set-option", collection, {"option": "years", "value": [2022, 2024]})
    assert by_block(doc, "series-collection")["options"]["years"] == [2022, 2024]
    assert by_block(doc, "series-collection")["instance_id"] == collection


def test_collection_disease_choice_is_pending_editor_state(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection = by_block(doc, "series-collection")["instance_id"]
    doc = edit_ok(host, "set-topics", collection, [])
    assert doc["ready"] is False
    assert doc["blocking_reason"] == ("Select at least one disease, or turn off "
                                      "‘Annual trends by disease’.")
    # The saved composition stays valid; only editor state is incomplete.
    stored = draft_recipe(site)
    publish.validate_composition(stored)
    status, body = generate(host)
    assert status == 400 and body["error"]["code"] in ("collection_empty", "draft_not_ready")

    reopened = document(host)
    assert reopened["ready"] is False
    assert by_block(reopened, "series-collection")["options"]["topics"] == []

    doc = edit_ok(host, "set-topics", collection, ["campylobacteriosis", "influenza"])
    assert doc["ready"] is True
    assert by_block(doc, "series-collection")["options"]["topics"] == \
        ["campylobacteriosis", "influenza"]


def test_incomplete_pending_addition_blocks_generation_and_survives_reopen(custom):
    site, host = custom
    status, body = add(host, "series-trend")           # no topic/measure chosen yet
    assert status == 200
    assert body["pending"] and body["ready"] is False
    assert "Choose" in body["pending"][0]["problem"]
    assert "series-trend" not in [item["block"] for item in body["blocks"]]
    publish.validate_composition(draft_recipe(site))    # on-disk recipe stays valid

    status, payload_body = generate(host)
    assert status == 400 and payload_body["error"]["code"] == "draft_not_ready"
    assert not list(site.jobs_root.glob("*"))          # nothing was rendered instead

    reopened = document(host)
    assert len(reopened["pending"]) == 1
    assert reopened["pending"][0]["block"] == "series-trend"

    doc = edit_ok(host, "discard-pending", reopened["pending"][0]["instance_id"])
    assert doc["pending"] == [] and doc["ready"] is True


def test_replacing_a_section_drops_its_pending_editor_state(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection = by_block(doc, "series-collection")["instance_id"]
    edit_ok(host, "set-topics", collection, ["campylobacteriosis"])
    editor_path = site.drafts_root / "custom" / "researcher" / workbench.DRAFT_EDITOR
    assert collection in json.loads(editor_path.read_text(encoding="utf-8"))["selection"]

    doc = edit_ok(host, "add-block", None, {"block": "series-trend",
                                            "options": {"topic": "influenza",
                                                        "measure": "cases"},
                                            "replace": [collection]})
    assert collection not in ids(doc)
    stored = json.loads(editor_path.read_text(encoding="utf-8"))
    assert collection not in stored["selection"]
    workbench.open_draft(editor_path.parent)          # the saved draft still opens
    assert document(host)["ready"] is True


def test_a_stale_pending_selection_is_reported_then_repaired(custom):
    site, host = custom
    edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    editor_path = site.drafts_root / "custom" / "researcher" / workbench.DRAFT_EDITOR
    editor = json.loads(editor_path.read_text(encoding="utf-8"))
    editor["selection"]["c-gone-9999"] = {"topics": ["campylobacteriosis"]}
    editor_path.write_text(json.dumps(editor), encoding="utf-8")

    reopened = document(host)          # must not fail with draft_invalid
    assert reopened["needs_repair"] == ["c-gone-9999"]
    assert reopened["ready"] is False

    repaired = edit_ok(host, "repair-draft")
    assert repaired["ready"] is True
    assert "c-gone-9999" not in json.loads(
        editor_path.read_text(encoding="utf-8"))["selection"]


# --------------------------------------------------------------------------- contexts

def test_each_context_keeps_an_independent_custom_draft(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    researcher_ids = ids(doc)

    other = document(host, "public")
    assert other["draft"] is False
    assert [item["block"] for item in other["blocks"]] == ["intro", "limitations",
                                                          "reproduction"]
    other = edit_ok(host, "add-block", None, {"block": "monitoring-overview"}, context="public")
    assert "coverage-selection" not in [item["block"] for item in other["blocks"]]

    back = document(host, "researcher")
    assert ids(back) == researcher_ids
    assert back["audience"] == "researcher"
    assert (site.drafts_root / "custom" / "public" / workbench.DRAFT_RECIPE).is_file()
    assert (site.drafts_root / "custom" / "researcher" / workbench.DRAFT_RECIPE).is_file()


def test_custom_drafts_are_separate_from_audience_drafts(custom):
    site, host = custom
    edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    # The audience editor never sees the custom draft, and vice versa.
    status, _, body = call(host, "GET", "/api/editor?preset=researcher")
    audience_doc = json.loads(body)
    assert audience_doc["draft"] is False and audience_doc["customized"] is False
    assert not (site.drafts_root / "researcher").exists()
    assert site.saved()["custom_drafts"] == ["researcher"]


def test_reset_only_restores_the_selected_custom_composition(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    first = ids(doc)
    public_before = ids(document(host, "public"))
    status, _, body = call(host, "POST", "/api/custom/reset", {"context": "researcher"},
                           action="custom-reset")
    assert status == 200
    reset = json.loads(body)
    assert [item["block"] for item in reset["blocks"]] == ["intro", "limitations",
                                                          "reproduction"]
    assert set(ids(reset)).isdisjoint(first)       # ids are not reissued
    assert ids(document(host, "public")) == public_before
    status, _, body = call(host, "POST", "/api/custom/reset", {"context": "public"},
                           action="custom-reset")
    assert status == 409 and json.loads(body)["error"]["code"] == "no_draft"


# --------------------------------------------------------------------------- generation

def test_custom_generation_records_origin_context_and_reuses_exact_settings(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    coverage = by_block(doc, "coverage-selection")["instance_id"]
    status, job = generate(host)
    assert status == 202, job
    assert job["preset"] == "custom" and job["origin"] == "custom"
    assert job["context"] == "researcher" and job["classification"] == "custom"
    finished = wait_for_job(host, job["job_id"])
    assert finished["status"] == "succeeded", finished
    assert finished["report_url"] == f"/reports/{job['job_id']}/report.html"

    record = json.loads((site.jobs_root / job["job_id"] / "job.json").read_text(encoding="utf-8"))
    assert record["origin"] == "custom" and record["context"] == "researcher"
    snapshot = json.loads((site.work_root / record["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["audience"] == "researcher"          # the bundle's stakeholder id
    assert coverage in [entry["instance_id"] for entry in snapshot["blocks"]]

    fresh = document(host)
    assert fresh["reuse"]["available"] is True
    assert fresh["reuse"]["job_id"] == job["job_id"]

    rows = call(host, "GET", "/api/saved")[2]
    row = next(item for item in json.loads(rows)["jobs"] if item["job_id"] == job["job_id"])
    assert row["origin"] == "custom" and row["context"] == "researcher"
    assert row["reuse"]["eligible"] is True
    assert row["context_label"] == "Researcher"

    # A different composition is not reusable with the same retained job.
    edit_ok(host, "add-block", None, {"block": "monitoring-overview"})
    changed = document(host)
    assert changed["reuse"] is None            # no retained report matches the new composition
    status, _, body = call(host, "POST", "/api/reuse",
                           {"preset": "custom", "context": "researcher",
                            "job_id": job["job_id"]}, action="reuse")
    assert status == 409 and json.loads(body)["error"]["code"] == "reuse_unavailable"


def test_reuse_follows_the_effective_composition_not_the_saved_file(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "monitoring-overview"})
    monitoring = by_block(doc, "monitoring-overview")["instance_id"]
    edit_ok(host, "remove", monitoring)          # kept in the saved file, not in the report
    assert monitoring in [entry["instance_id"] for entry in draft_recipe(site)["blocks"]]

    status, job = generate(host)
    assert status == 202
    assert wait_for_job(host, job["job_id"])["status"] == "succeeded"
    snapshot = json.loads((site.work_root /
                           json.loads((site.jobs_root / job["job_id"] /
                                       "job.json").read_text(encoding="utf-8"))["snapshot"]
                           ).read_text(encoding="utf-8"))
    assert monitoring not in [entry["instance_id"] for entry in snapshot["blocks"]]

    fresh = document(host)
    assert fresh["reuse"] is not None and fresh["reuse"]["job_id"] == job["job_id"]
    assert fresh["excluded"] == [monitoring]


def test_custom_and_audience_jobs_stay_separate_in_history(custom):
    _, host = custom
    status, job = generate(host)
    assert status == 202
    wait_for_job(host, job["job_id"])
    status, _, body = call(host, "POST", "/api/generate", {"preset": "researcher"},
                           action="generate")
    assert status == 202
    wait_for_job(host, json.loads(body)["job_id"])
    rows = json.loads(call(host, "GET", "/api/saved")[2])["jobs"]
    custom_rows = [row for row in rows if row["origin"] == "custom"]
    preset_rows = [row for row in rows if row["origin"] == "preset"]
    assert custom_rows and preset_rows
    assert all(row["context"] == "researcher" for row in custom_rows)
    assert all(row["context"] is None for row in preset_rows)


def test_audience_workflow_is_unchanged_by_a_custom_draft(custom):
    _, host = custom
    edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    status, _, body = call(host, "GET", "/api/editor?preset=researcher")
    audience_doc = json.loads(body)
    assert audience_doc["preset"] == "researcher"
    assert audience_doc["blocks"][0]["instance_id"] == "intro-0001"
    assert audience_doc["ready"] is True and audience_doc["draft"] is False
    status, _, body = call(host, "POST", "/api/generate", {"preset": "researcher"},
                           action="generate")
    assert status == 202
    job = json.loads(body)
    assert job["origin"] == "preset" and job["classification"] == "default"
    wait_for_job(host, job["job_id"])


# --------------------------------------------------------------------------- security

def test_custom_endpoints_require_the_session_and_the_action_header(custom):
    _, host = custom
    status, _, _ = call(host, "GET", "/api/custom?context=researcher", auth=False)
    assert status == 401
    status, _, _ = call(host, "POST", "/api/custom/edit",
                        {"context": "researcher", "action": "add-block",
                         "value": {"block": "intro"}}, action=None)
    assert status == 403
    status, _, body = call(host, "POST", "/api/custom/edit",
                           {"context": "researcher", "action": "add-block",
                            "value": {"block": "intro"}}, action="custom-edit",
                           origin="http://evil.example")
    assert status == 403
    status, _, body = call(host, "POST", "/api/custom/edit",
                           {"context": "researcher", "action": "add-block", "value": {},
                            "unexpected": 1}, action="custom-edit")
    assert status == 400
    status, _, body = call(host, "GET", "/api/custom?context=../../etc")
    assert status == 400


def test_unknown_context_and_action_are_refused(custom):
    _, host = custom
    status, body = edit(host, "add-block", None, {"block": "intro"}, context="custom")
    assert status == 400
    status, body = edit(host, "teleport", None, None)
    assert status == 400 and body["error"]["code"] == "invalid_request"


# --------------------------------------------------------------------------- frontend

def test_frontend_shows_one_ordered_editor_without_a_library(custom):
    _, host = custom
    status, _, body = call(host, "GET", "/")
    assert status == 200
    page = body.decode("utf-8")
    assert 'id="custom-blocks"' in page and "Report sections, in order" in page
    for removed in ('id="context-select"', 'id="context-summary"', 'id="context-note"',
                    'id="library"', "Block library"):
        assert removed not in page, removed
    assert 'id="custom-drafts"' in page
    source = (ROOT / "src" / "composer_web" / "app.js").read_text(encoding="utf-8")
    assert "absentTypes" in source and "Not in this report" in source
    assert '"delete-instance"' in source
    assert "Delete duplicate" in source


def test_new_collections_start_in_the_combined_layout(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    entry = by_block(doc, "series-collection")
    assert entry["options"]["layout"] == "combined"
    assert "layout" in entry["editable"]


def test_layout_can_be_switched_explicitly_and_is_validated(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection = by_block(doc, "series-collection")["instance_id"]
    doc = edit_ok(host, "set-option", collection,
                  {"option": "presentation.layout", "value": "panels"})
    assert by_block(doc, "series-collection")["options"]["layout"] == "panels"
    recipe = json.loads((site.drafts_root / "custom" / "researcher" /
                         workbench.DRAFT_RECIPE).read_text(encoding="utf-8"))
    assert by_block({"blocks": recipe["blocks"]}, "series-collection")["presentation"]["layout"] \
        == "panels"
    doc = edit_ok(host, "set-option", collection,
                  {"option": "presentation.layout", "value": "combined"})
    assert by_block(doc, "series-collection")["options"]["layout"] == "combined"
    status, body = edit(host, "set-option", collection,
                        {"option": "presentation.layout", "value": "stacked"})
    assert status == 400
    assert by_block(document(host), "series-collection")["options"]["layout"] == "combined"


def test_a_working_copy_keeps_the_preset_presentation_and_can_switch_layout(custom):
    site, host = custom
    maintained = (RECIPES / "researcher.json").read_bytes()
    status, _, body = call(host, "POST", "/api/edit",
                           {"preset": "researcher", "action": "exclude",
                            "instance": "block-coverage-selection", "value": None},
                           action="edit")
    assert status == 200, body                       # first edit creates the working copy
    copied = json.loads((site.drafts_root / "researcher" /
                         workbench.DRAFT_RECIPE).read_text(encoding="utf-8"))
    collection = next(item for item in copied["blocks"] if item["block"] == "series-collection")
    assert "layout" not in (collection.get("presentation") or {})   # maintained panels behaviour
    assert (RECIPES / "researcher.json").read_bytes() == maintained   # preset untouched

    # The layout is switched explicitly, through the shared editor control.
    doc = site.save_draft_edit("researcher", "set-layout", "researcher-series-collection",
                               "combined")
    entry = next(item for item in doc["blocks"]
                 if item["instance_id"] == "researcher-series-collection")
    assert entry["options"]["layout"] == "combined"

    status, _, body = call(host, "POST", "/api/reset", {"preset": "researcher"}, action="reset")
    assert status == 200
    restored = json.loads((site.drafts_root / "researcher" /
                           workbench.DRAFT_RECIPE).read_text(encoding="utf-8"))
    restored_collection = next(item for item in restored["blocks"]
                               if item["block"] == "series-collection")
    assert "layout" not in (restored_collection.get("presentation") or {})


def test_topic_labels_come_from_the_saved_bundle(custom):
    _, host = custom
    doc = document(host)
    labels = doc["topic_labels"]
    assert labels["campylobacteriosis"] == "Campylobacteriosis"
    assert labels["influenza"] == "Influenza"
    assert set(labels) == set(doc["eligible_topics"])


# --------------------------------------------------------------------------- duplicate/delete

def test_delete_duplicate_removes_only_that_instance(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "monitoring-overview"})
    first = by_block(doc, "monitoring-overview")["instance_id"]
    doc = edit_ok(host, "duplicate", first)
    instances = [item["instance_id"] for item in doc["blocks"]
                 if item["block"] == "monitoring-overview"]
    assert len(instances) == 2
    second = next(name for name in instances if name != first)

    doc = edit_ok(host, "delete-instance", second)
    assert second not in ids(doc)
    assert first in ids(doc)
    editor = json.loads((site.drafts_root / "custom" / "researcher" /
                         workbench.DRAFT_EDITOR).read_text(encoding="utf-8"))
    assert second in editor["retired"]

    # The retired id is never reissued for the next duplicate.
    doc = edit_ok(host, "duplicate", first)
    fresh = [item["instance_id"] for item in doc["blocks"]
             if item["block"] == "monitoring-overview"]
    assert second not in fresh and len(fresh) == 2


def test_last_instance_and_singletons_cannot_be_deleted(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "monitoring-overview"})
    monitoring = by_block(doc, "monitoring-overview")["instance_id"]
    status, body = edit(host, "delete-instance", monitoring)
    assert status == 400 and "one instance" in body["error"]["message"]
    assert monitoring in ids(document(host))

    doc = edit_ok(host, "add-block", None, {"block": "reference-comparison",
                                            "options": {"topic": "campylobacteriosis"}})
    reference = by_block(doc, "reference-comparison")["instance_id"]
    status, body = edit(host, "delete-instance", reference)
    assert status == 400
    status, body = edit(host, "duplicate", reference)
    assert status == 400 and "cannot be duplicated" in body["error"]["message"]
    assert reference in ids(document(host))


def test_required_sections_are_never_deleted(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "coverage-selection"})
    limitations = by_block(doc, "limitations")["instance_id"]
    status, body = edit(host, "duplicate", limitations)
    assert status == 400
    status, body = edit(host, "delete-instance", limitations)
    assert status == 400
    assert by_block(document(host), "limitations")["included"] is True


def test_section_titles_are_persisted_cleared_and_validated(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection = by_block(doc, "series-collection")["instance_id"]
    doc = edit_ok(host, "set-title", collection, "Hepatitis focus")
    entry = by_block(doc, "series-collection")
    assert entry["title"] == "Hepatitis focus"
    stored = draft_recipe(site)
    assert stored["titles"] == {collection: "Hepatitis focus"}
    assert document(host)["blocks"][-1]["title"] == "Hepatitis focus"

    # Blank removes the override; the recipe returns to its historical shape.
    doc = edit_ok(host, "set-title", collection, "   ")
    assert by_block(doc, "series-collection")["title"] is None
    assert "titles" not in draft_recipe(site)

    for bad, code in (("x" * 81, "edit_rejected"), ("bad\u0007title", "edit_rejected")):
        status, body = edit(host, "set-title", collection, bad)
        assert status == 400, body
    status, body = edit(host, "set-title", "c-unknown-9999", "Title")
    assert status == 400


def test_duplicate_copies_the_title_and_delete_removes_it(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "monitoring-overview"})
    first = by_block(doc, "monitoring-overview")["instance_id"]
    doc = edit_ok(host, "set-title", first, "Institution watch")
    doc = edit_ok(host, "duplicate", first)
    copy = next(item["instance_id"] for item in doc["blocks"]
                if item["block"] == "monitoring-overview" and item["instance_id"] != first)
    assert draft_recipe(site)["titles"] == {first: "Institution watch", copy: "Institution watch"}
    copy_entry = next(item for item in doc["blocks"]
                      if item["instance_id"] == copy)
    assert copy_entry["copy_label"] == "Copy 2"

    doc = edit_ok(host, "delete-instance", copy)
    assert draft_recipe(site)["titles"] == {first: "Institution watch"}
    assert copy not in ids(doc)


def test_replacing_a_section_drops_its_title(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection = by_block(doc, "series-collection")["instance_id"]
    edit_ok(host, "set-title", collection, "Focus")
    doc = edit_ok(host, "add-block", None, {"block": "reference-comparison",
                                            "options": {"topic": "campylobacteriosis"}})
    reference = by_block(doc, "reference-comparison")["instance_id"]
    edit_ok(host, "set-title", reference, "Comparison")
    doc = edit_ok(host, "delete-instance", collection) if False else doc
    # Reference is a singleton and cannot be deleted; the replacement path drops the title of the
    # replaced collection instead.
    doc = edit_ok(host, "add-block", None, {"block": "series-trend",
                                            "options": {"topic": "influenza",
                                                        "measure": "cases"},
                                            "replace": [collection]})
    stored = draft_recipe(site)
    assert collection not in stored.get("titles", {})
    assert stored.get("titles") == {reference: "Comparison"}


def test_two_collections_in_one_draft_stay_independent(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    first = by_block(doc, "series-collection")["instance_id"]
    doc = edit_ok(host, "set-topics", first, ["campylobacteriosis", "influenza"])
    doc = edit_ok(host, "duplicate", first)
    second = next(item["instance_id"] for item in doc["blocks"]
                  if item["block"] == "series-collection" and item["instance_id"] != first)
    doc = edit_ok(host, "set-option", second,
                  {"option": "presentation.layout", "value": "panels"})
    doc = edit_ok(host, "set-topics", second, ["influenza"])
    doc = edit_ok(host, "set-option", second, {"option": "years", "value": [2022, 2024]})
    doc = edit_ok(host, "set-title", second, "One disease view")

    first_entry = by_block({"blocks": [item for item in doc["blocks"]
                                       if item["instance_id"] == first]}, "series-collection")
    second_entry = by_block({"blocks": [item for item in doc["blocks"]
                                        if item["instance_id"] == second]}, "series-collection")
    assert first_entry["options"]["topics"] == ["campylobacteriosis", "influenza"]
    assert first_entry["options"]["layout"] == "combined"
    assert second_entry["options"]["topics"] == ["influenza"]
    assert second_entry["options"]["layout"] == "panels"
    assert second_entry["options"]["years"] == [2022, 2024]
    assert second_entry["title"] == "One disease view"
    copies = [item["copy_label"] for item in doc["blocks"]
              if item["block"] == "series-collection"]
    assert sorted(copies, key=lambda value: value or "") == [None, "Copy 2"]
    stored = draft_recipe(site)
    assert len([item for item in stored["blocks"] if item["block"] == "series-collection"]) == 2
    workbench.open_draft(site.drafts_root / "custom" / "researcher")


def test_section_summaries_follow_the_effective_settings(custom):
    _, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection = by_block(doc, "series-collection")["instance_id"]
    summary = by_block(doc, "series-collection")["summary"]
    assert "Campylobacteriosis" in summary and "Influenza" in summary
    assert "combined chart" in summary and "cases" in summary
    doc = edit_ok(host, "set-option", collection,
                  {"option": "presentation.layout", "value": "panels"})
    assert "separate charts" in by_block(doc, "series-collection")["summary"]
    doc = edit_ok(host, "set-topics", collection, ["campylobacteriosis"])
    assert "Influenza" not in by_block(doc, "series-collection")["summary"]
    doc = edit_ok(host, "add-block", None, {"block": "reference-comparison",
                                            "options": {"topic": "campylobacteriosis"}})
    reference = by_block(doc, "reference-comparison")["summary"]
    assert "reference year" in reference and "saved percent change" in reference
    doc = edit_ok(host, "add-block", None, {"block": "monitoring-overview"})
    monitoring = by_block(doc, "monitoring-overview")["summary"]
    assert "Latest saved observation per disease" in monitoring


def test_an_excluded_section_keeps_its_title_and_generates(custom):
    site, host = custom
    doc = edit_ok(host, "add-block", None, {"block": "series-collection",
                                            "options": {"measure": "cases"}})
    collection = by_block(doc, "series-collection")["instance_id"]
    edit_ok(host, "set-title", collection, "Focus")
    doc = edit_ok(host, "remove", collection)
    assert doc["ready"] is True                       # the title of an excluded section is not
    assert draft_recipe(site)["titles"] == {collection: "Focus"}   # an invalid reference
    assert by_block(doc, "series-collection")["title"] == "Focus"
    status, job = generate(host)
    assert status == 202, job
    assert wait_for_job(host, job["job_id"])["status"] == "succeeded"
    snapshot = json.loads((site.work_root /
                           json.loads((site.jobs_root / job["job_id"] / "job.json")
                                      .read_text(encoding="utf-8"))["snapshot"]
                           ).read_text(encoding="utf-8"))
    assert "titles" not in snapshot                   # effective composition names only its blocks

    doc = edit_ok(host, "restore", collection)
    assert doc["ready"] is True
    assert by_block(doc, "series-collection")["title"] == "Focus"


# --------------------------------------------------------------------------- context binding

def test_custom_context_resolution_without_a_selector(custom):
    site, _host = custom
    # No draft at all: the selected audience decides, and opening writes nothing.
    assert site.custom_document(selected="public")["context"] == "public"
    assert not (site.drafts_root / "custom").exists()
    # Deterministic without a selection, and an explicit request still wins.
    assert site.custom_document()["context"] == "researcher"
    assert site.custom_document("public")["context"] == "public"
    assert not (site.drafts_root / "custom").exists()


def test_existing_custom_draft_keeps_its_context(custom):
    site, host = custom
    edit_ok(host, "add-block", None, {"block": "coverage-selection"}, context="public")
    # Visiting another audience preset does not move or duplicate the draft.
    assert site.custom_document(selected="researcher")["context"] == "public"
    assert site.custom_document(selected="public")["context"] == "public"
    assert site._custom_draft_contexts() == ["public"]
    assert (site.drafts_root / "custom" / "public" / workbench.DRAFT_RECIPE).is_file()
    assert not (site.drafts_root / "custom" / "researcher").exists()


def test_two_custom_drafts_are_never_merged(custom):
    site, host = custom
    edit_ok(host, "add-block", None, {"block": "coverage-selection"}, context="researcher")
    edit_ok(host, "add-block", None, {"block": "monitoring-overview"}, context="public")
    researcher = site.custom_document(selected="researcher")
    public = site.custom_document(selected="public")
    assert researcher["context"] == "researcher" and public["context"] == "public"
    assert "monitoring-overview" not in [item["block"] for item in researcher["blocks"]]
    assert "coverage-selection" not in [item["block"] for item in public["blocks"]]
    assert site._custom_draft_contexts() == ["researcher", "public"]


def test_opening_the_custom_editor_writes_nothing(custom):
    site, host = custom
    status, _, body = call(host, "GET", "/api/custom?audience=researcher")
    document = json.loads(body)
    assert status == 200 and document["draft"] is False
    assert document["context"] == "researcher"
    assert not (site.drafts_root / "custom").exists()
