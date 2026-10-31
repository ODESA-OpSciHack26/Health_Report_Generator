"""Display settings contract: defaults, validation, selection against a saved analysis."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "health_pipeline"))

import neutral_display as nd  # noqa: E402

ANALYSIS = {
    "row_count": 11,
    "group_count": 3,
    "groups": [
        {"group": "North", "n": 4, "summary": {"n": 4},
         "periods": [{"period": "2021-01-01T00:00:00"}, {"period": "2022-01-01T00:00:00"}]},
        {"group": "South", "n": 4, "summary": {"n": 3},
         "periods": [{"period": "2021-01-01T00:00:00"}, {"period": "2022-01-01T00:00:00"}]},
        {"group": None, "n": 1, "summary": {"n": 1}, "periods": []},
    ],
    "time": {"has_time": True, "period_count": 2,
             "periods": ["2021-01-01T00:00:00", "2022-01-01T00:00:00"]},
}


def test_defaults_are_compact_and_block_specific():
    stats = nd.defaults("values-by-group")
    assert stats["statistics"] == ["n", "median", "middle50", "range"]
    assert stats["precision"] == {"mode": "decimal", "places": 1}
    assert stats["groups"] is None
    assert "periods" not in stats
    time = nd.defaults("values-over-time")
    assert time["axis_labels"] == {"mode": "auto"}
    assert time["layout"] == "chart-and-table"
    assert nd.defaults("intro") == {}


def test_validate_normalises_and_orders_statistics():
    result = nd.validate("values-by-group", {
        "statistics": ["range", "n", "median"], "precision": {"mode": "decimal", "places": 2}})
    assert result["statistics"] == ["n", "median", "range"]
    assert result["precision"]["places"] == 2


@pytest.mark.parametrize("display,message", [
    ({"statistics": ["n", "bogus"]}, "Unknown statistics"),
    ({"layout": "panels"}, "not available"),
    ({"precision": {"mode": "decimal", "places": 9}}, "0 to 6"),
    ({"groups": []}, "at least one group"),
    ({"groups": ["North", "North"]}, "only be shown once"),
    ({"nonsense": True}, "Unsupported display settings"),
])
def test_validate_rejects_invalid_settings(display, message):
    with pytest.raises(nd.DisplayError) as error:
        nd.validate("values-by-group", display)
    assert message in str(error.value)


def test_validate_rejects_capability_mismatch():
    with pytest.raises(nd.DisplayError):
        nd.validate("coverage-over-time", {"layout": "chart"})
    with pytest.raises(nd.DisplayError):
        nd.validate("values-by-group", {"periods": {"mode": "all"}})
    with pytest.raises(nd.DisplayError):
        nd.validate("intro", {"layout": "table"})


def test_period_modes_validate():
    assert nd.validate("values-over-time", {"periods": {"mode": "all"}})["periods"] == {"mode": "all"}
    window = {"mode": "range", "from": "2021-01-01", "to": "2022-01-01"}
    assert nd.validate("values-over-time", {"periods": window})["periods"] == window
    listed = {"mode": "list", "values": ["2021-01-01T00:00:00"]}
    assert nd.validate("values-over-time", {"periods": listed})["periods"] == listed
    with pytest.raises(nd.DisplayError):
        nd.validate("values-over-time", {"periods": {"mode": "range", "from": "2022-01-01",
                                                     "to": "2021-01-01"}})
    with pytest.raises(nd.DisplayError):
        nd.validate("values-over-time", {"periods": {"mode": "list", "values": []}})


def test_axis_label_modes():
    assert nd.validate("values-over-time", {"axis_labels": {"mode": "every_n", "n": 2}})[
        "axis_labels"] == {"mode": "every_n", "n": 2}
    with pytest.raises(nd.DisplayError):
        nd.validate("values-over-time", {"axis_labels": {"mode": "every_n", "n": 1}})


def test_selection_must_exist_in_the_analysis():
    assert nd.selection_problem({"groups": ["North", "missing"]}, ANALYSIS) is None
    assert "not in the saved analysis" in nd.selection_problem({"groups": ["Atlantis"]}, ANALYSIS)
    assert nd.selection_problem({"periods": {"mode": "list",
                                             "values": ["2023-01-01T00:00:00"]}}, ANALYSIS)
    assert nd.selection_problem({"periods": {"mode": "range", "from": "2021-01-01",
                                             "to": "2021-12-31"}}, ANALYSIS) is None
    assert nd.selection_problem({"periods": {"mode": "range", "from": "2019-01-01",
                                             "to": "2019-12-31"}}, ANALYSIS)


def test_blank_group_label_is_stable():
    assert [label for _key, label in nd.group_labels(ANALYSIS)] == ["North", "South", "missing"]
    collision = {"groups": [{"group": "missing", "n": 1, "summary": {"n": 1}, "periods": []},
                            {"group": None, "n": 1, "summary": {"n": 1}, "periods": []}]}
    assert [label for _key, label in nd.group_labels(collision)] == [
        "missing", "missing (blank group)"]


def test_summary_states_displayed_scope():
    display = nd.validate("values-over-time", {"groups": ["North", "South"]})
    text = nd.summary(display, ANALYSIS)
    assert "Showing 2 of 3 analysed groups" in text
    display = nd.validate("values-over-time", {"periods": {"mode": "list",
                                                           "values": ["2021-01-01T00:00:00"]}})
    assert "Showing 1 of 2 analysed periods" in nd.summary(display, ANALYSIS)
