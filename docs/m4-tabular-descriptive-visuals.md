# Descriptive and visual supplied-table reports

This slice adds actual rendered ggplot2 graphics and saved Python descriptive
results, not another QMD or replacement runtime. All audiences consume the same
analysis.json. Its exact bytes and calculation policy are identified in render
provenance; verification independently reproduces it from captured input rows.

## Policy

Statistics are calculated within each separate category: non-missing count,
unweighted mean, sample SD (n-1), minimum, inclusive-linear quartiles, median and
maximum. No cross-category totals or within-period sums/means are inferred.
Comparisons require caller-selected reference/latest periods and exactly one
non-missing observation at each. A non-positive baseline has no percentage change.
Missing/repeated period observations are not silently pooled. Calendar periods
not represented in a supplied selection may have been intentionally excluded.
Trend lines are segmented at those gaps, not joined or imputed.

Graphics are self-contained rendered PNGs using the existing ggplot2 environment.
They are not Plotly hover/zoom charts. Tables retain search/sort interactivity.
Technical views add distributions, full descriptive tables, comparison eligibility
and coverage. Institutional/public views lead with different explanations and
selected chart panels while retaining the same results/provenance and full rows.
Chart category limits are explicit and do not filter the saved analytical results.

## Request version 2

Version-1 requests still work; they gain row descriptives but no implicit reference
comparison. Version 2 additionally requires a report object. Allowed options are
title, measure_label, unit, geography_label, source_label, reference_period,
latest_period, max_categories and context_notes. Labels are caller-supplied
annotations, not an authenticated publisher statement. Comparison dates are ISO
period starts. Both comparison periods must be supplied together and present.

The one-command entry point passes these options to the renderer. The prepared
bundle remains row-preserving; descriptive results belong to the render layer.
All output artifact sets now include analysis.json. Existing historical outputs
must be verified under their recorded matching source/environment, not silently
relabelled as new outputs.

## Real health-data demonstration

Use the previously verified canonical researcher series.csv directly: retain all
72 records and original identifiers/metadata, map label/value/year, and declare
cases, mandatory reporting, CHFL and the 2019-to-2025 comparison. Confirm these
properties from the actual input before creating the version-2 request. Its
SHA-256 pins the exact source bytes. The supplied selection omits 2020; it must
not be shown as zero or described as a failed source year. Do not sum HIV and
AIDS as independent people. No canton map is inferred from national-only data.

Real Quarto rendering and visual review remain gates. This is not browser,
upload-security, image-rebuild or formal accessibility acceptance.


## Browser-review presentation refinement

Front pages now have distinct structures: researcher statistical audit, institutional
monitoring dashboard, and a public editorial lead with one primary chart and optional
supporting detail. They consume the same saved analysis; presentation does not alter
calculations or select a different analytic population for an audience.

Statistics are formatted for display, usually to one decimal place, with thousands
separators and whole observation counts. Small nonzero values retain significant
digits. Saved analysis/provenance stays full precision. Fractional means, standard
deviations and interpolated quartiles are legitimate summaries, not fractional
individual case records. SD describes between-observation variation, not uncertainty
around an estimated mean.

Navigation appears prominently below the report hero, remains sticky while scrolling,
and is repeated at the footer. Technical details remain accessible in every view.
The duplicate automatic title block is hidden only by styles emitted on the tabular
path, which supplies its own visible heading; the browser title is retained.

Header text has explicit opaque foreground/background colors. White on #173f63
has a computed contrast ratio above 10:1, but this is not a full accessibility audit.
Coverage is described as selection context rather than a failure banner. Annual
labels show years instead of raw ISO timestamps. No unrepresented period is imputed
or described as an established source-data failure.
