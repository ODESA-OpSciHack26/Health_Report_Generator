"""Batch D rework: trend-chart title wrapping, annual ticks and sparse-series copy."""
import re
from datetime import datetime

import pytest

import pilot_charts

LONG = "Über-Ärztliche-Überwachungsstelle-für-sehr-lange-Bezeichnungen"


def _row(category, year, value=1, segment="s", line_allowed=True):
    return {"category": category, "period": f"{year}-01-01", "value": value,
            "segment": f"{category}-{segment}", "line_allowed": line_allowed,
            "source_row": 1}


def _analysis(rows):
    return {"parameters": {"measure_label": "Observed value", "unit": "not specified"},
            "plot_rows": rows}


def test_long_and_special_titles_are_wrapped_without_loss():
    for label in (LONG, "中文类别", '<script>alert(1)</script>', 'A & B "quoted"'):
        lines = pilot_charts._wrap_title(label)
        assert all(len(line) <= pilot_charts.TITLE_WIDTH for line in lines)
        assert re.sub(r"\s+", "", "\n".join(lines)) == re.sub(r"\s+", "", label)


def test_annual_ticks_are_unique_integer_years_and_bounded():
    dates = [datetime(year, 1, 1) for year in range(2015, 2026)]
    ticks = pilot_charts._year_ticks(dates)
    assert ticks == sorted(set(ticks))
    assert len(ticks) <= pilot_charts.MAX_YEAR_TICKS
    assert all(isinstance(year, int) for year in ticks)
    assert pilot_charts._year_ticks([datetime(2021, 1, 1)]) == [2021]


def test_all_sparse_panels_get_value_only_copy_and_neutral_heading():
    rows = [_row("A", 2021), _row("B", 2022)]
    plan = pilot_charts._trend_plan(_analysis(rows), period="year")
    assert plan["all_sparse"] is True and plan["mixed"] is False
    assert plan["title"] == "Observed values over the supplied periods"
    assert plan["figure_title"] == "Observed values in the supplied periods"
    assert "fewer than two observed periods" in plan["note"]
    assert "temporal development cannot be assessed" in plan["note"]
    assert "Separate vertical scales" in plan["note"]
    assert "compare shape" not in plan["note"]


def test_mixed_panels_distinguish_sparse_from_observed_change():
    rows = [_row("Sparse", 2021), _row("Series", 2021), _row("Series", 2022)]
    plan = pilot_charts._trend_plan(_analysis(rows), period="year")
    assert plan["mixed"] is True and plan["all_sparse"] is False
    assert "Panels with fewer than two observed periods" in plan["note"]
    assert "panels with two or more show observed change" in plan["note"]
    assert "Separate vertical scales" in plan["note"]
    assert plan["title"] == "How have the supplied series developed?"


def test_panels_with_enough_observations_keep_existing_shape_guidance():
    rows = [_row("A", 2021), _row("A", 2022), _row("B", 2021), _row("B", 2022)]
    plan = pilot_charts._trend_plan(_analysis(rows), period="year")
    assert plan["all_sparse"] is False and plan["mixed"] is False
    assert plan["note"].startswith("Dots are observed values.")
    assert "compare shape within a panel" in plan["note"]


def test_non_annual_period_keeps_non_annual_path():
    rows = [{"category": "A", "period": "2023-01-01", "value": 1,
             "segment": "A-s0", "line_allowed": True},
            {"category": "A", "period": "2023-02-01", "value": 2,
             "segment": "A-s0", "line_allowed": True}]
    plan = pilot_charts._trend_plan(_analysis(rows), period="month")
    assert plan["annual"] is False
    assert plan["tick_years"] is None
    assert plan["mixed"] is False


def test_missing_periods_are_not_invented_as_observations():
    rows = [_row("A", 2021), _row("A", 2023)]
    plan = pilot_charts._trend_plan(_analysis(rows), period="year")
    assert plan["counts"] == {"A": 2}
    assert plan["tick_years"] == [2021, 2023]
    assert 2022 not in plan["tick_years"]


def test_rendered_document_has_sparse_caption_alt_and_methods_link():
    pytest.importorskip("matplotlib", reason="requires the frozen pilot environment")
    import tabular_python
    import tabular_render
    import tabular_run
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "tabular"
    request = tabular_run.load_request(root / "f5_labels.request.json")
    prepared = tabular_run.prepare_payload(
        (root / "f5_labels.csv").read_bytes(), source_filename="f5_labels.csv",
        mapping=request["mapping"], mode=request["mode"], period=request["period"])
    context = tabular_render._context(prepared, tabular_render._profile("researcher"),
                                      request.get("report"))
    context["audience"] = "researcher"
    html = tabular_python.document_html(context, "report")
    assert "Each panel has fewer than two observed periods" in html
    assert 'alt="Observed values in the supplied periods"' in html
    assert "Observed values and coverage" in html
    assert "Series development and coverage" not in html
    assert "methods.html#statistics" in html
