"""Batch G: neutral copy, conditional comparison framing and narrow chart variants."""
import base64
import struct

import pytest

import pilot_document as doc
import tabular_python

BASE_PARAMETERS = {
    "title": "Supplied observations", "measure_label": "Observed value",
    "unit": "not specified", "geography_label": "not specified",
    "source_label": "Reader-supplied table", "reference_period": None,
    "latest_period": None, "max_categories": 24, "context_notes": [],
}


def _analysis(comparisons=None):
    return {
        "schema": "health-report/tabular-analysis/1",
        "parameters": dict(BASE_PARAMETERS),
        "overview": {"rows": 4, "categories": 2, "periods": 1, "missing_values": 0},
        "category_statistics": [{"category": "A", "n": 2, "mean": 1.5, "median": 1.5,
                                 "sd": 0.7, "min": 1, "q1": 1, "q3": 2, "max": 2,
                                 "missing_values": 0, "missing_dates": 0, "rows": 2,
                                 "periods": 2, "first_period": "2021-01-01",
                                 "last_period": "2022-01-01"}],
        "comparisons": comparisons or [],
        "chart_categories": ["A"],
        "plot_rows": [], "histogram": [], "periods": ["2021-01-01"],
        "unrepresented_calendar_periods": [],
    }


def _context(layout, analysis, audience="researcher"):
    return {"analysis": analysis,
            "profile": {"layout": layout, "display_name": layout.title()},
            "rows_html": "<div>rows</div>", "parameters": {"period": "year"},
            "audience": audience}


@pytest.fixture
def no_charts(monkeypatch):
    monkeypatch.setattr(tabular_python.pilot_charts, "graphs",
                        lambda analysis, technical, period=None: [])


@pytest.mark.usefixtures("no_charts")
def test_generic_report_uses_neutral_category_wording():
    analysis = _analysis()
    pages = " ".join(
        tabular_python.document_html(_context(layout, analysis), document)
        for layout in ("technical", "dashboard", "editorial")
        for document in ("report", "methods"))
    assert "Each disease" not in pages
    assert "disease surveillance" not in pages
    assert "recorded notifications" not in pages
    assert "different disease series" not in pages
    assert "Each category is shown separately" in pages
    assert "underlying data collection" in pages
    assert "recorded values" in pages


@pytest.mark.usefixtures("no_charts")
def test_disease_wording_only_when_metadata_declares_it():
    analysis = _analysis()
    analysis["parameters"]["source_label"] = "Notifiable disease surveillance export"
    html = tabular_python.document_html(_context("editorial", analysis), "report")
    assert "Each disease is shown separately" in html
    assert "recorded notifications" in html
    assert "disease surveillance" in html


@pytest.mark.usefixtures("no_charts")
def test_no_comparison_removes_change_framing():
    analysis = _analysis()
    public = tabular_python.document_html(_context("editorial", analysis), "report")
    dashboard = tabular_python.document_html(_context("dashboard", analysis), "report")
    assert "What the supplied values show" in public
    assert "What changed in the reported numbers?" not in public
    assert "The main finding" not in public
    assert "How the series compare" not in public
    assert "percentage change" not in public
    assert "No reference-period comparison has been inferred." in public
    assert "Comparison availability" in dashboard
    assert "Changes to review" not in dashboard
    assert "Change against the reference" not in dashboard
    assert "reference-change" not in dashboard
    assert "latest-values" not in dashboard


@pytest.mark.usefixtures("no_charts")
def test_available_comparison_keeps_change_framing():
    comparison = {"category": "A", "baseline": 10, "latest": 12, "difference": 2,
                  "percent": 20.0, "note": "Comparable single observations"}
    analysis = _analysis([comparison])
    public = tabular_python.document_html(_context("editorial", analysis), "report")
    dashboard = tabular_python.document_html(_context("dashboard", analysis), "report")
    assert "What changed in the reported numbers?" in public
    assert "How the series compare" in public
    assert "percentage change" in public
    assert "Changes to review" in dashboard
    assert "Change against the reference" in dashboard


GENERIC_FORBIDDEN = (
    "distinct people", "different people", "clinical severity", "clinical importance",
    "outbreak", "severity", "health outcomes", "case counts", "population",
    "national observations",
)


@pytest.mark.usefixtures("no_charts")
def test_generic_copy_has_no_health_or_person_framing():
    comparison = {"category": "A", "baseline": 10, "latest": 12, "difference": 2,
                  "percent": 20.0, "note": "Comparable single observations"}
    for analysis in (_analysis(), _analysis([comparison])):
        pages = " ".join(
            tabular_python.document_html(_context(layout, analysis), document)
            for layout in ("technical", "dashboard", "editorial")
            for document in ("report", "methods"))
        for phrase in GENERIC_FORBIDDEN:
            assert phrase not in pages, phrase


@pytest.mark.usefixtures("no_charts")
def test_generic_copy_keeps_uncertainty_disclosures():
    pages = " ".join(
        tabular_python.document_html(_context(layout, _analysis()), document)
        for layout in ("technical", "dashboard", "editorial")
        for document in ("report", "methods"))
    assert "not evidence of causes or statistical significance" in pages
    assert "Missing values are not counted as zero" in pages
    assert "No total across different series" in pages
    assert "not filled in" in pages


def test_narrow_trend_margins_reserve_year_labels_and_footnote():
    rows = [{"category": name, "period": f"{year}-01-01", "value": year - 2020,
             "segment": f"{name}-s", "line_allowed": True, "source_row": index + 1}
            for index, (name, year) in enumerate([("Alpha", 2021), ("Alpha", 2022),
                                                  ("Beta", 2021), ("Beta", 2022)])]
    analysis = _analysis()
    analysis["plot_rows"] = rows
    plan = tabular_python.pilot_charts._trend_plan(analysis, "year", narrow=True)
    title_lines = tabular_python.pilot_charts._wrap_title(plan["title"], 32)
    foot_lines = tabular_python.pilot_charts._wrap_title(
        "Separate vertical scales. Gaps are not zero; lines do not bridge absent periods.", 48)
    height = plan["height"] + 0.32 * (len(title_lines) - 1)
    top, bottom = tabular_python.pilot_charts._narrow_margins(
        height, title_lines, foot_lines)
    assert top * height >= 0.55 + 0.30 * len(title_lines)
    assert bottom * height >= 0.32 + 0.20 * len(foot_lines)


def test_figure_emits_narrow_source_and_keeps_alt_text():
    markup = doc.figure(b"wide", "Chart title", "Note", narrow_png=b"narrow")
    assert '<picture><source media="(max-width: 800px)"' in markup
    assert 'alt="Chart title"' in markup
    assert markup.count("data:image/png;base64,") == 2
    assert base64.b64encode(b"narrow").decode() in markup
    plain = doc.figure(b"wide", "Chart title", "Note")
    assert "<picture>" not in plain


def test_charts_expose_a_narrow_variant_that_is_narrower():
    plt = pytest.importorskip("matplotlib.pyplot", reason="requires the pilot environment")
    rows = [{"category": name, "period": f"{year}-01-01", "value": year - 2020,
             "segment": f"{name}-s", "line_allowed": True, "source_row": index + 1}
            for index, (name, year) in enumerate([("A", 2021), ("A", 2022),
                                                  ("B", 2021), ("B", 2022)])]
    analysis = _analysis()
    analysis["plot_rows"] = rows
    plots = tabular_python.pilot_charts.graphs(analysis, False, period="year")
    assert plots
    for plot in plots:
        assert plot.get("narrow_png")
        wide = struct.unpack(">II", plot["png"][16:24])[0]
        narrow = struct.unpack(">II", plot["narrow_png"][16:24])[0]
        assert narrow < wide
    plt.close("all")
