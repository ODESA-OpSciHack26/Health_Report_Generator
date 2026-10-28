# Technical data workflow: source to inspectable reports

Status: target specification, not shipped functionality. Updated 28 October 2026. Governed by [the integration plan](integration-plan.md), [contracts](integration-contracts.md), [workspace](steward-workspace.md) and [inspectable blocks](decisions/inspectable-blocks.md).

## 1. End-to-end experience

Choose a captured reference dataset or upload a table -> inspect structure and proposed interpretation -> accept or correct interpretation -> choose analytical scope and audiences -> preview -> configure blocks if needed -> render and verify -> save/replay a recipe and export approved artifacts.

Clear inputs should need a compact confirmation, not a handwritten mapping file or long wizard. Ambiguous or consequential choices expand the relevant controls. Keep an advanced configuration view, but do not require it for routine use. Preview and final publication are distinct states.

## 2. Current baseline versus target

The implemented supplied-table route accepts explicitly mapped UTF-8 comma CSV/tab TSV with category, one measure and optional time, and creates three verified HTML views from checksum-pinned requests. It preserves captured bytes and has no implicit aggregation. Existing request versions 1/2 retain their meanings.

Target extensions include role suggestions/review, actual year/group selection, multiple measures, multiple grouping candidates and explicit ungrouped or row-count modes. These need new validated interpretation/result contracts; documenting them does not enable them. Parquet, additional delimiters/encodings/locales and wide-to-long conversion are separately evaluated compatibility extensions, not claimed baseline support. Unsupported shapes receive actionable explanations rather than an arbitrary report.

## 3. Capture and structural inspection

Capture uploaded bytes once, record the full content digest and retain the original under the distribution policy. Enforce byte/row/column/resource limits and safe path rules before expensive processing. Do not hash one read and analyze a later changed file.

Inspect headers, record widths, quoting, missingness and candidate formats. Preserve original values/identifier strings while proposing types. Parsing suggestions include delimiter, encoding, decimal/thousands conventions, time format/frequency and missing sentinels. Ambiguity requires explicit resolution. Record each accepted conversion and invalid-value outcome; do not silently coerce unreadable values into unexplained missingness.

Import time is not observation time. Numeric identifiers and leading-zero codes are not measures merely because they can be parsed as numbers. Frequency normalization does not perform a date-window filter.

## 4. Interpretation review

Show a compact summary of proposed time, measure, group and identifier roles, units, parsing rules, missingness and proposed operations. Offer Accept interpretation and Edit controls. Clear cases may use one confirmation; uncertain cases require field-level decisions. Save proposed, confirmed and overridden settings distinctly with the inference method/version.

Support separate declared measures and group candidates without silently mixing units. An ungrouped table can have a dataset-level descriptive view under an explicit contract; do not fabricate a meaningful category. If row counting is selected for text-only data, label it as number of records, never people, cases or events without a supported definition.

Do not default every quantity to sum or mean solely from its name. Offer no aggregation, supported summaries, or a justified grouped operation. Require a declared measure meaning and recorded operation. Rates, percentages, medians and already aggregated values need appropriate treatment; unavailable denominators do not become invented weights.

A table resembling a domain schema is a compatibility candidate, not proof of publisher authenticity or scientific eligibility. Validate the domain contract before offering domain-specific blocks. General tables never inherit disease, incidence or alert semantics automatically.

## 5. Selection and preview

Offer supported years/ranges, groups, measures and audiences after interpretation. Distinguish report-global analytical selection from chart/table display subsets. Record predicates, before/after counts and exclusion reasons while retaining immutable original source-record identities.

A partial group menu must not silently exclude unlisted groups. Provide search/pagination or an explicit selected-subset policy. Automatic time coarsening or aggregation requires a visible supported setting, not an invisible change because the series is long.

Show a prompt bounded structural preview. An automatic report preview based on proposed settings is clearly marked draft/unconfirmed; it cannot be mistaken for a verified accepted report. After confirmation, retain low-friction generation and clear progress rather than adding unnecessary forms.

## 6. Analysis and report generation

UI and CLI submit the same validated effective request. Reuse current preparation, quality gates, verified bundles and shared report source. Compute supported results outside presentation and record their actual method/parameters. No renderer rereads an unvalidated original or substitutes a new calculation.

Standard publication remains three distinct presets, with extra profiles explicitly selected. The composer configures registered blocks rather than creating another audience QMD. Each analytical block links exact relevant data, calculation, results, plotted rows, analysis/render source and reproduction details.

For multiple measures, record separate units, scopes and method identities. New grouping/selection behavior must have independent expected-result fixtures and a migration/version decision before activation.

## 7. Outputs, cache and disclosure

Offer complete report output, readable methods, full-precision statistics, permitted contributing data, resolved interpretation/request and machine-readable provenance. Preserve original source separately from prepared, selected and plotted data. Block previews state total rows and any withholding.

Use validated source/interpretation/analysis/render identities, not filename, modification time or the existence of an HTML file as proof of a valid cache hit. Check full identities/manifests despite shortened display labels. Preserve original render time separately from a new submission/retrieval. Failed runs do not replace accepted runs.

Public export governs actual artifacts. Collapsed sections are not privacy controls. Do not embed or link restricted rows, source literals, credentials or private paths. Record intentional omissions and reproduction limits in an export-specific manifest. No arbitrary patient-data security acceptance is implied.

## 8. Implementation and acceptance

B1 defines strict interpretation/selection/result/evidence contracts while preserving old request behavior. B2 proves an existing comparison block and inspector. B3 adds guided interpretation, bounded uploads and tested supported selection; broaden to multi-measure, grouping and ungrouped/count modes only through explicit fixtures/contracts. B4 versions publication and verification together. B5 exposes the complete low-friction UI. B6 develops integrity/cache/export throughout. B7 verifies the integrated journey.

Fixtures cover snapshots; calendar years and ISO dates; monthly/weekly/day inputs; ambiguous numerics; leading zeros; blanks versus declared sentinels; invalid conversions; repeated periods; negative/zero values; counts versus rates; ungrouped/text-only tables; mixed units; group-menu limits; malformed/oversized input; and escaped labels. Optional format/locale extensions have separate gates.

A release claim requires saved-request replay, independently checked calculations, three audience outputs plus a genuinely new profile, matching evidence/provenance and actual browser review. Source inspection is not runtime or scientific validation.
