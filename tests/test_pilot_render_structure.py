"""Regression tests for the table/disclosure wrapper and distribution-chart defects."""
import html.parser
import shutil
import subprocess
from pathlib import Path

import pytest

import pilot_charts
import pilot_document as doc
import tabular_python

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "tabular"


class _Node:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.parent = parent
        self.children = []

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


class _TreeParser(html.parser.HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = _Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return


def _context(audience="researcher"):
    import tabular_render
    import tabular_run

    request = tabular_run.load_request(FIXTURES / "f1_ordinary.request.json")
    prepared = tabular_run.prepare_payload(
        (FIXTURES / "f1_ordinary.csv").read_bytes(), source_filename="f1_ordinary.csv",
        mapping=request["mapping"], mode=request["mode"], period=request["period"])
    context = tabular_render._context(prepared, tabular_render._profile(audience),
                                      request.get("report"))
    context["audience"] = audience
    return context


def _render(audience, document, tmp_path):
    figures, tables = {}, {}
    qmd = tabular_python.quarto_document(_context(audience), document,
                                         {"schema": "test"}, figures=figures, tables=tables)
    shutil.copyfile(ROOT / "scripts" / "health_pipeline" / "templates" / "dashboard.css",
                    tmp_path / "dashboard.css")
    (tmp_path / f"{document}.qmd").write_text(qmd, encoding="utf-8")
    completed = subprocess.run(["quarto", "render", f"{document}.qmd", "--to", "html",
                                "--output", f"{document}.html"],
                               cwd=tmp_path, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    rendered = (tmp_path / f"{document}.html").read_text(encoding="utf-8")
    rendered = doc.restore_figures(rendered, figures)
    rendered = doc.restore_tables(rendered, tables)
    return qmd, rendered


def _tree(rendered):
    parser = _TreeParser()
    parser.feed(rendered)
    return parser.root


@pytest.mark.quarto_runtime
@pytest.mark.skipif(shutil.which("quarto") is None,
                    reason="real-Quarto structure test requires the B2 image")
@pytest.mark.parametrize("audience,document,expected_details", [
    ("researcher", "report", 2),
    ("public", "report", 4),
])
def test_table_scroll_ends_at_table_and_details_survive(audience, document,
                                                        expected_details, tmp_path):
    qmd, rendered = _render(audience, document, tmp_path)
    assert "data-pilot-table" not in rendered
    assert "data-pilot-figure" not in rendered
    assert qmd.count("<details") == expected_details
    root = _tree(rendered)
    scrolls = [node for node in root.walk()
               if node.tag == "div" and "table-scroll" in node.classes()]
    assert scrolls
    for scroll in scrolls:
        assert sum(1 for node in scroll.walk() if node.tag == "section") == 0
        assert sum(1 for node in scroll.walk() if node.tag == "table") == 1
    details = [node for node in root.walk()
               if node.tag == "details" and "report-disclosure" in node.classes()]
    assert len(details) == expected_details
    summaries = [node for node in root.walk() if node.tag == "summary"]
    assert len(summaries) == expected_details
    if audience == "researcher":
        assert "Inspect latest values and reference-period changes" in rendered
        assert "Open the searchable and sortable observation table" in rendered


@pytest.mark.quarto_runtime
@pytest.mark.skipif(shutil.which("quarto") is None,
                    reason="real-Quarto structure test requires the B2 image")
def test_methods_tables_are_balanced_and_have_no_details(tmp_path):
    qmd, rendered = _render("researcher", "methods", tmp_path)
    assert qmd.count("<details") == 0
    root = _tree(rendered)
    scrolls = [node for node in root.walk()
               if node.tag == "div" and "table-scroll" in node.classes()]
    assert len(scrolls) == 3
    for scroll in scrolls:
        assert sum(1 for node in scroll.walk() if node.tag == "section") == 0
        assert sum(1 for node in scroll.walk() if node.tag == "table") == 1


def test_table_registry_defers_and_restores_exactly_once():
    registry = {}
    markup = doc.html_table([{"category": "A", "value": 1}], ["category", "value"],
                            registry=registry)
    assert markup.startswith('<div data-pilot-table="0">')
    assert "table-scroll" not in markup
    restored = doc.restore_tables(f"<p>before</p>{markup}<p>after</p>", registry)
    assert "data-pilot-table" not in restored
    assert restored.count('<div class="table-scroll">') == 1
    with pytest.raises(doc.PilotDocumentError, match="was not preserved"):
        doc.restore_tables("<p>no placeholder</p>", registry)
    with pytest.raises(doc.PilotDocumentError, match="was not preserved"):
        doc.restore_tables(markup + markup, registry)


def test_histogram_bounds_cover_valid_bins():
    bounds = pilot_charts._histogram_bounds([
        {"left": 10.0, "right": 16.7, "count": 3},
        {"left": 16.7, "right": 23.3, "count": 1},
        {"left": 23.3, "right": 30.0, "count": 2},
    ])
    assert bounds is not None
    assert bounds[0] < 10.0 and bounds[1] > 30.0
    assert bounds[2] == 0.0 and bounds[3] >= 3.3


def test_histogram_bounds_expand_degenerate_and_empty():
    bounds = pilot_charts._histogram_bounds([{"left": 5.0, "right": 5.0, "count": 2}])
    assert bounds[0] < 5.0 < bounds[1]
    assert pilot_charts._histogram_bounds([]) is None


def test_technical_empty_histogram_gets_an_explicit_panel():
    pytest.importorskip("matplotlib", reason="requires the frozen pilot environment")
    analysis = {"parameters": {"measure_label": "Observed value", "unit": "count"},
                "plot_rows": [], "comparisons": [], "histogram": []}
    plots = pilot_charts.graphs(analysis, technical=True)
    item = next(plot for plot in plots if plot["title"] == "Distribution diagnostic")
    assert "No populated row-value bins" in item["note"]
    assert item["png"]
