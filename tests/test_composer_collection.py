"""Multi-topic annual series collection over the existing single-topic series core.

Fixtures here are synthetic and labelled as such; zero, gap and single-observation cases are
fixture behaviour, not findings in the retained data.
"""
import csv
import json

import pytest

import publish
from test_composer_series import _render, build_series_bundle, write_recipe, sha256


def collection_entry(instance="collection-0001", **overrides):
    entry = {"block": "series-collection", "instance_id": instance,
             "topics": "eligible", "measure": "cases"}
    entry.update(overrides)
    return entry


def build_collection(bundle, topics="eligible", measure="cases", years=None, presentation=None,
                     instance="collection-0001"):
    return publish.build_series_collection(bundle["bundle"], publish.PROJECT, instance, topics,
                                           measure, years, presentation)


def _exclude_topic(bundle, topic):
    """Mark one saved topic excluded, as a narrowed analysis would."""
    path = bundle["bundle"] / "selection.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for row in rows:
        if row["topic"] == topic:
            row["status"] = "excluded"
            row["reason"] = "excluded by the requested topic scope"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = json.loads((bundle["bundle"] / "bundle.json").read_text())
    manifest["files"]["selection.csv"] = sha256(path)
    (bundle["bundle"] / "bundle.json").write_text(json.dumps(manifest))


def three_topic_bundle(tmp_path, root=None):
    return build_series_bundle(
        tmp_path, root=root,
        extra_topics=(("bacterium", [(2021, "5"), (2022, "6"), (2025, "9")]),
                      ("fungus", [(2021, "3"), (2025, "4")])))


def test_single_explicit_topic_resolves_one_member(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    record = build_collection(bundle, topics=["virus"])
    assert record["status"] == "verified"
    assert len(record["members"]) == 1
    assert record["topics"] == ["virus"]
    assert record["ordering"] == "author"
    assert record["presentation"]["default_topic"] == "virus"


def test_multiple_explicit_topics_keep_author_order(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    record = build_collection(bundle, topics=["fungus", "virus", "bacterium"])
    assert record["status"] == "verified"
    assert record["topics"] == ["fungus", "virus", "bacterium"]
    assert [m["selection"]["topic"] for m in record["members"]] == ["fungus", "virus", "bacterium"]


def test_all_eligible_topics_use_deterministic_order(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    record = build_collection(bundle)
    assert record["status"] == "verified"
    assert record["ordering"] == "eligible-ascending"
    assert record["topics"] == ["bacterium", "fungus", "virus"]
    assert len(record["members"]) == 3


def test_narrowed_scope_resolves_only_included_topics(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    _exclude_topic(bundle, "fungus")
    record = build_collection(bundle)
    assert record["status"] == "verified"
    assert record["topics"] == ["bacterium", "virus"]


def test_explicitly_requested_excluded_topic_fails_the_collection(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    _exclude_topic(bundle, "fungus")
    record = build_collection(bundle, topics=["virus", "fungus"])
    assert record["status"] == "failed"
    assert record["code"] == "selection"
    assert "fungus" in record["detail"]
    assert "members" not in record


def test_unknown_topic_fails_rather_than_being_skipped(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    record = build_collection(bundle, topics=["virus", "smallpox"])
    assert record["status"] == "failed"
    assert record["code"] == "selection"
    assert "smallpox" in record["detail"]


def test_restricted_years_are_honoured_and_wide_years_rejected(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    narrowed = build_collection(bundle, topics=["virus"], years=[2022, 2024])
    assert narrowed["status"] == "verified"
    assert narrowed["periods"]["requested"] == [2022, 2024]
    assert narrowed["periods"]["effective"] == [2022, 2023, 2024]
    outside = build_collection(bundle, topics=["virus"], years=[2019, 2025])
    assert outside["status"] == "failed"
    assert "outside the report window" in outside["detail"]
    unordered = build_collection(bundle, topics=["virus"], years=[2024, 2022])
    assert unordered["status"] == "failed"
    assert "not ordered" in unordered["detail"]


def test_zero_missing_year_and_single_observation_stay_distinct(tmp_path):
    # Fixture: 2021 zero, 2022 absent, 2023 single observation, 2024-2025 present.
    rows = [(2021, "0.0"), (2023, "7.0"), (2024, "9.0")]
    bundle = build_series_bundle(tmp_path, rows=rows)
    record = build_collection(bundle, topics=["virus"])
    member = record["members"][0]
    values = {observation["year"]: observation["value"] for observation in member["observations"]}
    assert values[2021] == "0.0"          # a real zero is kept as zero
    assert 2022 not in values             # a missing year is a gap
    assert member["missing_years"] == [2022, 2025]
    assert values[2023] == "7.0"          # single observation remains an observation
    assert len(member["observations"]) == 3


def test_default_topic_must_belong_to_the_resolved_topics(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    bad = build_collection(bundle, topics=["virus"], presentation={"default_topic": "fungus"})
    assert bad["status"] == "failed"
    assert bad["code"] == "presentation"
    ok = build_collection(bundle, topics=["virus", "fungus"],
                          presentation={"default_topic": "fungus"})
    assert ok["status"] == "verified"
    assert ok["presentation"]["default_topic"] == "fungus"


def test_recipe_validation_is_closed(tmp_path):
    good = collection_entry(presentation={"style": "compact", "default_topic": "virus"})
    write_recipe(tmp_path, [good], name="good.json")
    assert publish.load_composition(tmp_path / "good.json")["blocks"][0]["topics"] == "eligible"

    bad_entries = [
        collection_entry(extra="x"),                                  # unknown key
        collection_entry(topics=[]),                                  # empty list
        collection_entry(topics=["virus", "virus"]),                  # duplicate
        collection_entry(topics="all"),                               # unsupported keyword
        collection_entry(topics=[1]),                                 # wrong type
        collection_entry(measure="CASES"),                            # measure id
        collection_entry(years=[2025, 2021]),                         # unordered years
        collection_entry(presentation={"style": "fancy"}),            # unknown style
        collection_entry(presentation={"default_topic": "Not A Topic"}),
        collection_entry(topics=["virus"], presentation={"default_topic": "fungus"}),
        collection_entry(presentation={"theme": "dark"}),             # unknown option
    ]
    for index, entry in enumerate(bad_entries):
        path = write_recipe(tmp_path, [entry], name=f"bad-{index}.json")
        with pytest.raises(ValueError):
            publish.load_composition(path)


def test_recipe_rejects_repeated_or_mixed_series_blocks(tmp_path):
    two = write_recipe(tmp_path, [collection_entry("c-1"), collection_entry("c-2")], name="two.json")
    with pytest.raises(ValueError, match="Repeated series-collection"):
        publish.load_composition(two)
    mixed = write_recipe(tmp_path, [
        collection_entry("c-1"),
        {"block": "series-trend", "instance_id": "s-1", "topic": "virus", "measure": "cases"},
    ], name="mixed.json")
    with pytest.raises(ValueError, match="cannot combine"):
        publish.load_composition(mixed)


def test_series_collection_requires_v2(tmp_path):
    path = write_recipe(tmp_path, [collection_entry()], contract=publish.COMPOSITION_CONTRACT,
                        name="v1.json")
    with pytest.raises(ValueError, match="requires composition contract"):
        publish.load_composition(path)


def test_member_ids_are_bounded_deterministic_and_unique(tmp_path):
    long_topic = "verylongdiseasetopicname_that_exceeds_the_limit_easily"
    short_topic = "virus"
    bundle = build_series_bundle(tmp_path, topic=short_topic, label="Virus",
                                 extra_topics=((long_topic, [(2021, "2"), (2025, "3")]),))
    record = build_collection(bundle)
    assert record["status"] == "verified"
    ids = [member["instance_id"] for member in record["members"]]
    assert len(ids) == len(set(ids))
    assert all(len(identifier) <= 40 for identifier in ids)
    assert all(publish.IDENTIFIER_RE.fullmatch(identifier) for identifier in ids)
    again = build_collection(bundle)
    assert [member["instance_id"] for member in again["members"]] == ids
    # Derivation depends only on collection instance and topic, not on position.
    reversed_ids = [member["instance_id"] for member in build_collection(
        bundle, topics=list(reversed(record["topics"])))["members"]]
    assert reversed_ids == list(reversed(ids))


def test_member_identities_survive_reordering_and_default_changes(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    first = build_collection(bundle, topics=["virus", "fungus", "bacterium"],
                             presentation={"default_topic": "virus"})
    reordered = build_collection(bundle, topics=["bacterium", "fungus", "virus"],
                                 presentation={"default_topic": "virus"})
    by_topic = {member["selection"]["topic"]: member["identities"] for member in reordered["members"]}
    for member in first["members"]:
        assert by_topic[member["selection"]["topic"]] == member["identities"]
    assert first["identities"]["collection"] != reordered["identities"]["collection"]

    same_order_new_default = build_collection(
        bundle, topics=["virus", "fungus", "bacterium"],
        presentation={"default_topic": "fungus"})
    assert same_order_new_default["identities"]["collection"] != first["identities"]["collection"]
    by_topic_default = {member["selection"]["topic"]: member["identities"]
                        for member in same_order_new_default["members"]}
    for member in first["members"]:
        assert by_topic_default[member["selection"]["topic"]] == member["identities"]


def test_style_changes_collection_identity_only(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    standard = build_collection(bundle, topics=["virus", "fungus"])
    compact = build_collection(bundle, topics=["virus", "fungus"],
                               presentation={"style": "compact"})
    assert standard["identities"]["collection"] != compact["identities"]["collection"]
    # Style is a documented presentation input of the member instance identity; the saved-row
    # and analytical identities must not move.
    for before, after in zip(standard["members"], compact["members"]):
        assert before["identities"]["analytical"] == after["identities"]["analytical"]
        assert before["identities"]["rows"] == after["identities"]["rows"]
        assert before["observations"] == after["observations"]


def test_topic_record_mismatch_fails_the_collection(tmp_path, monkeypatch):
    bundle = three_topic_bundle(tmp_path)
    original = publish.build_series_block

    def swapped(bundle_path, project_root, instance_id, topic, measure, years=None,
                presentation=None):
        wrong = "fungus" if topic == "virus" else "virus"
        return original(bundle_path, project_root, instance_id, wrong, measure, years,
                        presentation)

    monkeypatch.setattr(publish, "build_series_block", swapped)
    record = build_collection(bundle, topics=["virus"])
    assert record["status"] == "failed"
    assert record["code"] == "member_mismatch"


def test_render_records_scope_provenance_and_collection_identity(tmp_path, monkeypatch):
    bundle = three_topic_bundle(tmp_path)
    sidecar = _render(tmp_path, monkeypatch, bundle, [
        {"block": "intro", "instance_id": "intro-0001"},
        collection_entry("research-collection", topics=["virus", "fungus"],
                         presentation={"style": "standard", "default_topic": "fungus"}),
    ])
    scope = sidecar["composition"]["display_scope"]
    assert scope["collection_topics"] == ["fungus", "virus"]
    assert scope["collection_default_topic"] == "fungus"
    assert scope["displayed_topics"] == ["fungus", "virus"]
    instance = next(item for item in sidecar["composition"]["instances"]
                    if item["instance_id"] == "research-collection")
    assert instance["topics"] == ["virus", "fungus"]
    assert instance["presentation"]["default_topic"] == "fungus"
    assert instance["contract"] == publish.COLLECTION_CONTRACT
    assert instance["contract_status"] == "verified"
    assert instance["collection_identity"] == next(
        block for block in sidecar["blocks"]
        if block["instance_id"] == "research-collection")["identities"]["collection"]
    assert len(instance["member_instance_ids"]) == 2
    title = sidecar["composition"]["effective_title"]
    assert "2 notifiable diseases" in title
    assert "Virus, Fungus" not in title      # member names are not joined into the title


def test_failed_collection_fails_the_composed_render(tmp_path, monkeypatch):
    bundle = three_topic_bundle(tmp_path)
    _exclude_topic(bundle, "fungus")
    with pytest.raises(ValueError, match="failed series collection binding"):
        _render(tmp_path, monkeypatch, bundle, [
            {"block": "intro", "instance_id": "intro-0001"},
            collection_entry("research-collection", topics=["virus", "fungus"]),
        ])


def test_collection_cannot_be_silently_partial(tmp_path):
    bundle = three_topic_bundle(tmp_path)
    _exclude_topic(bundle, "fungus")
    record = build_collection(bundle)
    assert record["status"] == "verified"                    # eligible set excludes fungus
    assert record["topics"] == ["bacterium", "virus"]
    explicit = build_collection(bundle, topics=["virus", "fungus"])
    assert explicit["status"] == "failed"                    # explicit request is all-or-nothing
    assert "members" not in explicit
