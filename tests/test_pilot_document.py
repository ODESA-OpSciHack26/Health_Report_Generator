"""Pilot document helpers that do not require the experimental graphics stack."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import pilot_document as doc
import tabular_python

ROOT = Path(__file__).resolve().parents[1]


def test_display_number_matches_tabular_contract():
    assert doc.display_number(None) == "Not available"
    assert doc.display_number(991.1666666667) == "991.2"
    assert doc.display_number(63.2531949127) == "63.3"
    assert doc.display_number(18496.3) == "18,496.3"
    assert doc.display_number(6, 1, True) == "6"
    assert doc.display_number(-5, 1, True) == "-5"
    assert doc.display_number(0, 1, True) == "0"
    assert doc.display_number(0.0123) == "0.0123"
    assert doc.display_number(float("nan")) == "Not available"


def test_escaping_covers_text_and_attributes():
    assert doc.esc("<script>&\"'") == "&lt;script&gt;&amp;&quot;&#x27;"
    table = doc.html_table([{"category": "<b>&", "value": 1}], ["category", "value"])
    assert "&lt;b&gt;&amp;" in table and "<b>" not in table
    assert 'data-searchable="true"' in table


def test_table_labels_and_missing_values():
    rendered = doc.display_table(
        [{"category": "A", "n": 2, "mean": 1.25, "percent": 12.5, "note": None}],
        ["category", "n", "mean", "percent", "note"], "year")
    assert "Valid observations" in rendered and "Change (%)" in rendered
    assert "+12.5%" in rendered and "Series" in rendered


def test_sections_are_minimal_and_audience_parameterised(monkeypatch):
    monkeypatch.setattr(tabular_python.pilot_charts, "graphs", lambda analysis, technical: [])
    analysis = {
        "schema": "health-report/tabular-analysis/1",
        "parameters": {"title": "T", "measure_label": "Value", "unit": "count",
                       "geography_label": "none", "source_label": "source",
                       "reference_period": "2021-01-01", "latest_period": "2022-01-01",
                       "max_categories": 24, "context_notes": []},
        "overview": {"rows": 2, "categories": 1, "periods": 2, "missing_values": 0},
        "category_statistics": [{"category": "A", "n": 2, "mean": 1.5, "median": 1.5,
                                 "sd": 0.7, "min": 1, "q1": 1, "q3": 2, "max": 2,
                                 "missing_values": 0, "missing_dates": 0, "rows": 2,
                                 "periods": 2, "first_period": "2021-01-01",
                                 "last_period": "2022-01-01"}],
        "comparisons": [], "chart_categories": ["A"], "plot_rows": [], "histogram": [],
        "periods": ["2021-01-01", "2022-01-01"], "unrepresented_calendar_periods": [],
    }
    context = {"analysis": analysis, "profile": {"layout": "technical",
                                                 "display_name": "Researcher"},
               "rows_html": "<div>rows</div>", "parameters": {"period": "year"},
               "audience": "researcher"}
    technical = tabular_python.document_html(context, "report")
    assert 'id="research-statistics"' in technical and 'id="data-quality"' in technical
    assert 'data-tabular-audience="researcher"' in technical
    context["profile"] = {"layout": "editorial", "display_name": "General public"}
    public = tabular_python.document_html(context, "report")
    assert 'id="public-main-chart"' in public and 'id="research-statistics"' not in public
    context["profile"] = {"layout": "dashboard", "display_name": "Public health"}
    dashboard = tabular_python.document_html(context, "report")
    assert 'id="monitoring-priorities"' in dashboard
    methods = tabular_python.document_html(context, "methods")
    assert 'id="statistics"' in methods and 'id="comparison-detail"' in methods


def _analysis():
    return {
        "schema": "health-report/tabular-analysis/1",
        "parameters": {"title": "T", "measure_label": "Value", "unit": "count",
                       "geography_label": "none", "source_label": "source",
                       "reference_period": None, "latest_period": None,
                       "max_categories": 24, "context_notes": []},
        "overview": {"rows": 0, "categories": 0, "periods": 0, "missing_values": 0},
        "category_statistics": [], "comparisons": [], "chart_categories": [],
        "plot_rows": [], "histogram": [], "periods": [],
        "unrepresented_calendar_periods": [],
        "policy": {"scope": "test"},
    }


def test_quarto_document_uses_markdown_engine_and_embeds_provenance():
    analysis = _analysis()
    context = {"analysis": analysis, "profile": {"display_name": "X", "layout": "technical"},
               "rows_html": "", "parameters": {"period": "year"}, "audience": "researcher"}
    rendered = tabular_python.quarto_document(context, "methods",
                                              {"schema": "test", "value": "<tag>"})
    assert "engine: markdown" in rendered
    assert "```{=html}" in rendered
    assert 'id="report-provenance"' in rendered


def test_importing_tabular_render_does_not_require_matplotlib():
    completed = subprocess.run(
        [sys.executable, "-c", "import sys, tabular_render; "
                               "print('matplotlib' in sys.modules)"],
        cwd=ROOT / "scripts" / "health_pipeline", capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False"
