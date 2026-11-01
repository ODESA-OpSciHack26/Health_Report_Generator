"""Supplied-table HTML adapter for the pilot renderer.

Consumes the saved prepared bundle context and analysis record. It performs no analytical
recalculation; every value comes from analysis.json/table.json content prepared by Python.
"""
from __future__ import annotations

import pilot_charts
import pilot_document as doc


def date_label(period, value):
    if value is None:
        return "Not selected"
    return str(value)[:4 if period == "year" else 10]


def _comparisons(analysis):
    rows = [row for row in analysis.get("comparisons") or [] if row.get("difference") is not None]
    return sorted(rows, key=lambda row: abs(float(row["difference"])), reverse=True)


def _has_comparison(analysis) -> bool:
    """A comparison is available only when a saved reference/latest pair exists."""
    return any(row.get("difference") is not None
               for row in analysis.get("comparisons") or [])


def _disease_context(parameters) -> bool:
    """Disease-specific wording only when reader-supplied metadata declares it.

    The request schema carries no domain field, so the supplied annotations
    (title, measure, source, geography, unit, context notes) are the only
    metadata a generic reader could use to establish that context.
    """
    values = [parameters.get(key) for key in
              ("title", "measure_label", "source_label", "geography_label", "unit")]
    values += list(parameters.get("context_notes") or [])
    text = " ".join(str(value).lower() for value in values if value)
    return any(token in text for token in
               ("disease", "surveillance", "notification", "outbreak", "epidemi"))


def _brief(analysis, parameters, period):
    comparisons = _comparisons(analysis)
    if not comparisons:
        return "<p>No eligible reference-period comparison was requested or available.</p>"
    items = []
    for row in comparisons[:3]:
        percent = row.get("percent")
        detail = (" · percentage unavailable" if percent is None else
                  f" · {'+' if float(percent) > 0 else ''}{doc.display_number(percent, 1)}%")
        items.append(
            f"<li><strong>{doc.esc(row.get('category'))}</strong><br>"
            f"{doc.display_number(row.get('baseline'), 1, True)} → "
            f"{doc.display_number(row.get('latest'), 1, True)} {doc.esc(parameters.get('unit'))}"
            f"{detail}</li>")
    return ('<ul class="priority-list">' + "".join(items) + "</ul>"
            '<p class="chart-note">Selected by largest absolute change among comparable '
            "series—not importance. "
            f"{doc.esc(date_label(period, parameters.get('reference_period')))}"
            " versus "
            f"{doc.esc(date_label(period, parameters.get('latest_period')))}."
            "</p>")


def _plot_html(plots, kind, figures=None):
    wanted = {
        "trend": ("Development over the supplied periods",
                  "Observed values in the supplied periods", "Supplied observations"),
        "latest": ("Latest selected period",),
        "change": ("Within-category change",),
        "distribution": ("Distribution diagnostic",),
    }[kind]
    item = next((plot for plot in plots if plot["title"] in wanted), None)
    if item is None:
        return ""
    return doc.figure(item["png"], item["title"], item["note"], registry=figures,
                      narrow_png=item.get("narrow_png"))


def document_html(context: dict, document: str = "report", figures=None,
                  tables=None) -> str:
    if document not in ("report", "methods"):
        raise doc.PilotDocumentError("Unsupported tabular document")
    analysis = context["analysis"]
    parameters = analysis["parameters"]
    profile = context["profile"]
    audience = analysis.get("audience") or context.get("audience")
    layout = profile["layout"]
    technical = layout == "technical"
    public = layout == "editorial"
    period = context["parameters"].get("period")
    trend_all_sparse = False
    if document == "report" and any(row.get("value") is not None and row.get("period")
                                    for row in analysis.get("plot_rows") or []):
        trend_all_sparse = pilot_charts._trend_plan(analysis, period)["all_sparse"]

    overview = analysis["overview"]
    coverage_dates = [date_label(period, value) for value in analysis.get("periods") or []]
    coverage = ("Selected periods: " + ", ".join(coverage_dates) if coverage_dates
                else "Snapshot: no observation dates were supplied.")
    gaps = [date_label(period, value)
            for value in analysis.get("unrepresented_calendar_periods") or []]
    gap_note = ("Not represented in this supplied selection: " + ", ".join(gaps) +
                ". No value is assigned to those periods; they are not displayed as zero."
                if gaps else "")
    disease = _disease_context(parameters)
    comparable = _has_comparison(analysis)
    quality = (f"<p>{doc.display_number(overview.get('missing_values'), 0)} missing numeric "
               f"values in {doc.display_number(overview.get('rows'), 0)} supplied observations. "
               + ("This describes completeness of the supplied table, not completeness of disease "
                  "surveillance.</p>" if disease else
                  "This describes completeness of the supplied table, not completeness of the "
                  "underlying data collection.</p>"))
    limitations = ("<p>These are descriptive observations; they are not evidence of causes "
                   "or statistical significance. "
                   + ("Testing, surveillance and reporting can affect recorded notifications. "
                      "No cross-disease total is presented as a count of distinct people.</p>"
                      if disease else
                      "What is counted, tested and reported can affect the recorded values. "
                      "No total across different series is presented as a single combined "
                      "count.</p>"))
    stats_note = ("<p class=\"chart-note\">Statistics summarize the available observations in each "
                  "separate series. A mean can be fractional even when the underlying "
                  "observations are whole numbers. SD describes variation between observations, "
                  "not uncertainty around the mean. Quartiles may lie between observed values. "
                  "Missing and unselected years are not filled in.</p>")
    shows = ("Data & charts" if technical else
             "Main findings" if public else "Monitoring brief")
    navigation = ('<nav class="report-tabs" aria-label="Report views">' +
                  doc.link("report.html", shows, document == "report") +
                  doc.link("methods.html", "Methods & detailed statistics",
                           document == "methods") +
                  doc.link("#provenance", "Source & downloads") + "</nav>")
    if document == "methods":
        heading = "Methods & detailed statistics"
    elif technical:
        heading = "Data explorer & statistical audit"
    elif public:
        heading = ("What changed in the reported numbers?" if comparable
                   else "What the supplied values show")
    else:
        heading = "Monitoring briefing"
    plots = pilot_charts.graphs(analysis, technical, period=period) if document == "report" else []
    parts = [doc.STYLE,
             f'<div class="dashboard tabular-enriched audience-{doc.esc(layout)}" '
             f'data-tabular-audience="{doc.esc(audience)}">',
             '<header class="report-hero"><div class="audience-kicker">'
             f'{doc.esc(profile.get("display_name"))}</div><h1>{doc.esc(heading)}</h1>'
             f'<p>{doc.esc(parameters.get("title"))}</p>'
             f'<p>{doc.esc(parameters.get("geography_label"))} · '
             f'{doc.esc(parameters.get("measure_label"))} · unit: '
             f'{doc.esc(parameters.get("unit"))}</p>'
             f'<p>{doc.esc(parameters.get("source_label"))}</p></header>',
             navigation, "<main>"]
    table = lambda rows, columns: doc.display_table(rows, columns, period,
                                                    registry=tables)
    if document == "methods":
        parts += [
            doc.section("statistics", "Descriptive statistics for each series",
                        table(analysis.get("category_statistics"),
                              ["category", "n", "missing_values", "mean", "sd", "min", "q1",
                               "median", "q3", "max"]) + stats_note),
            doc.section("coverage", "Coverage of the supplied selection",
                        f'<p class="coverage-inline">{doc.esc(coverage)}</p>' +
                        (f"<p>{doc.esc(gap_note)}</p>" if gap_note else "") +
                        table(analysis.get("category_statistics"),
                              ["category", "rows", "periods", "first_period", "last_period",
                               "missing_dates"])),
            doc.section("comparison-detail", "Reference-period comparisons",
                        table(analysis.get("comparisons"),
                              ["category", "baseline", "latest", "difference", "percent",
                               "note"])),
            doc.section("parameters", "Calculation policy",
                        "<p>Statistics give each available row equal weight within its category. "
                        "Quartiles use inclusive linear interpolation; SD uses n−1. No "
                        "category-period observations or different series are pooled. "
                        "Comparisons require exactly one non-missing observation at each "
                        "explicitly selected period.</p><p>Percentage change = 100 × "
                        "(latest − reference) ÷ reference. It is unavailable for non-positive "
                        "baselines. Trend lines stop at absent periods. Display rounding does not "
                        "change the full-precision saved results.</p>"),
        ]
        if parameters.get("context_notes"):
            parts.append(doc.section(
                "source-context", "Source interpretation notes",
                "<ul>" + "".join(f"<li>{doc.esc(note)}</li>"
                                 for note in parameters["context_notes"]) + "</ul>"))
    elif technical:
        parts += [
            doc.section("overview", "Research overview",
                        doc.cards([overview.get("rows"), overview.get("categories"),
                                   overview.get("periods"), overview.get("missing_values")],
                                  ["Retained observations", "Separate series",
                                   "Selected periods", "Missing values"]) +
                        "<p>Inspect the saved values, their coverage and descriptive variation "
                        "before reusing them in scientific work.</p>"
                        '<p><a class="report-cta" href="methods.html#statistics">Open quartiles, '
                        "ranges and full statistical methods</a></p>"),
            doc.section("research-statistics", "Statistical overview",
                        table(analysis.get("category_statistics"),
                              ["category", "n", "mean", "median", "sd"]) + stats_note),
            doc.section("data-quality", "Selection and missingness",
                        quality + f'<p class="coverage-inline">{doc.esc(coverage)}</p>' +
                        (doc.disclosure("Coverage note", f"<p>{doc.esc(gap_note)}</p>")
                         if gap_note else "")),
            doc.section("series-trends",
                        "Observed values and coverage" if trend_all_sparse
                        else "Series development and coverage",
                        _plot_html(plots, "trend", figures)),
            doc.section("distribution", "Row-value distribution diagnostic",
                        _plot_html(plots, "distribution", figures)),
        ]
        if comparable:
            parts.append(doc.disclosure(
                "Inspect latest values and reference-period changes",
                _plot_html(plots, "latest", figures) + _plot_html(plots, "change", figures)))
    elif not public:
        parts += [
            doc.section("overview", "Monitoring scope",
                        doc.cards([date_label(period, parameters.get("reference_period")),
                                   date_label(period, parameters.get("latest_period")),
                                   overview.get("categories"), overview.get("missing_values")],
                                  ["Reference period", "Latest selected period",
                                   "Series in the file", "Missing numeric values"]) +
                        "<p>This is a descriptive review of supplied observations—not "
                        "a classification or a recommendation to act.</p>"),
            doc.section("monitoring-priorities",
                        "Changes to review" if comparable else "Comparison availability",
                        _brief(analysis, parameters, period)),
        ]
        if comparable:
            parts += [
                '<div class="monitor-grid">',
                doc.section("latest-values", "Latest selected values",
                            _plot_html(plots, "latest", figures)),
                doc.section("reference-change", "Change against the reference",
                            _plot_html(plots, "change", figures)),
                "</div>",
                doc.section("comparison-values", "Counts and comparison eligibility",
                            table(analysis.get("comparisons"),
                                  ["category", "baseline", "latest", "difference", "percent",
                                   "note"])),
            ]
        parts += [
            doc.section("data-quality", "Quality and scope before interpretation",
                        quality + doc.disclosure(
                            "Which periods are included?",
                            f"<p>{doc.esc(coverage)}</p><p>{doc.esc(gap_note)}</p>")),
        ]
        if comparable:
            parts.append(doc.disclosure(
                "Inspect observed values over time" if trend_all_sparse
                else "Inspect development over time",
                _plot_html(plots, "trend", figures)))
        else:
            parts.append(doc.section(
                "series-trends",
                "Observed values and coverage" if trend_all_sparse
                else "Series development and coverage",
                _plot_html(plots, "trend", figures)))
    else:
        comparisons = _comparisons(analysis)
        if comparisons:
            row = comparisons[0]
            lead = (f'<p class="story-lead"><strong>{doc.esc(row.get("category"))}</strong> has '
                    "the largest absolute change among the comparable series: "
                    f'{doc.display_number(row.get("baseline"), 1, True)} → '
                    f'{doc.display_number(row.get("latest"), 1, True)} '
                    f'{doc.esc(parameters.get("unit"))}. That does not mean it is the most '
                    "important series.</p>")
        else:
            lead = ('<p class="story-lead">Explore the observations supplied for this report. '
                    "No reference-period comparison has been inferred.</p>")
        main_chart = _plot_html(plots, "change", figures) or _plot_html(plots, "trend", figures)
        cause = ("Recorded numbers can change because disease occurrence, testing and reporting "
                 "change." if disease else
                 "Recorded values can change because what is counted, tested and reported can "
                 "change.")
        read_note = ("<p>Read a percentage change alongside the original counts. A large "
                     "percentage can start from a small number.</p>" if comparisons else
                     "<p>Read each series separately: the panels use separate vertical scales, "
                     "and only supplied observations are shown.</p>")
        how_to_read = ("<p>Each disease is shown separately. The report does not add different "
                       "diseases together as if they were different people. " if disease else
                       "<p>Each category is shown separately. The report does not add different "
                       "series into a single combined total. ")
        how_to_read += ("Missing values are not counted as zero, and no outbreak or severity "
                        "threshold is calculated.</p>" if disease else
                        "Missing values are not counted as zero, and no threshold is "
                        "calculated.</p>")
        how_to_read += ('<p><a class="report-cta primary" href="methods.html">See the source, '
                        "detailed statistics and explanations</a></p>")
        parts += [
            doc.section("overview",
                        "The main finding" if comparisons else "What the values show",
                        lead + f"<p>{cause} These data alone do not establish the cause.</p>"),
            doc.section("public-main-chart",
                        "How the series compare" if comparisons else "The observed series",
                        main_chart + read_note),
            doc.section("how-to-read", "What these figures can and cannot tell us", how_to_read),
        ]
        if comparisons:
            parts.append(doc.disclosure(
                "See the counts behind the comparison",
                table(analysis.get("comparisons"),
                      ["category", "baseline", "latest", "percent", "note"])))
            parts.append(doc.disclosure("Explore the separate series over time",
                                        _plot_html(plots, "trend", figures)))
        parts.append(doc.section(
            "data-quality", "What is missing?",
            quality + doc.disclosure(
                "About the selected years",
                f"<p>{doc.esc(coverage)}</p><p>{doc.esc(gap_note)}</p>")))
    if document == "report":
        rows_html = doc.defer_table(context["rows_html"], tables)
        parts.append(doc.section(
            "observations", "Original observations",
            doc.disclosure(
                "Open the searchable and sortable observation table",
                "<p>Filtering and sorting change only the view, not the saved results. "
                "“Missing” marks an absent field.</p>" + rows_html)))
        if len(analysis.get("category_statistics") or []) > len(
                analysis.get("chart_categories") or []):
            parts.append(
                f'<p class="coverage-inline">Charts show the first '
                f'{len(analysis.get("chart_categories") or [])} categories in source order. All '
                "categories remain in the saved results and tables.</p>")
    parts += [
        doc.section("limitations", "Interpretation and uncertainty", limitations),
        doc.section("provenance", "Source and downloadable evidence",
                    '<p><a href="provenance.json" download>Render provenance</a> · '
                    '<a href="../analysis.json" download>Full-precision statistics and row '
                    "references</a> · "
                    '<a href="../bundle/manifest.json" download>Prepared bundle manifest</a> · '
                    '<a href="../bundle/provenance.json" download>Preparation provenance</a></p>'
                    "<p>Source labels and units are supplied annotations. The same verified rows "
                    "and saved results support all three audience views.</p>"),
        '</main><footer class="report-footer">' + doc.link("report.html", shows) +
        ' · <a class="report-cta" href="methods.html">Methods & detailed statistics</a></footer></div>',
    ]
    return "\n".join(parts)


def quarto_document(context: dict, document: str, record: dict, figures=None,
                    tables=None) -> str:
    """Wrap the HTML body in a Quarto markdown document with no execution engine."""
    parameters = context["analysis"]["parameters"]
    profile = context["profile"]
    title = f'{parameters.get("title")} | {profile.get("display_name")}'
    body = document_html(context, document, figures=figures, tables=tables)
    return ("---\n"
            f"title: {doc.esc(title)}\n"
            "format:\n"
            "  html:\n"
            "    embed-resources: true\n"
            "    toc: false\n"
            "    page-layout: full\n"
            "    css: dashboard.css\n"
            "    section-divs: false\n"
            "    format-links: false\n"
            "engine: markdown\n"
            "---\n\n"
            "```{=html}\n"
            f"{body}\n"
            f"{doc.provenance_script(record)}\n"
            f"{doc.INTERACTIVE_TABLES_SCRIPT}\n"
            "```\n")
