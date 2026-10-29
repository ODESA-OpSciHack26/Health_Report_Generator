# Block catalogue and reader experience (design capture)

Status: design capture for review, written 28 October 2026. This document defines the
intended reader experience, parameters, evidence, failure behaviour and current status of
each report block. It is **not** a schema, an acceptance ledger, an execution log or a
replacement for the contracts and tests in the repository. Proposed items are marked as
proposed; nothing here authorizes implementation beyond the separately approved gates.

Governing material remains [HANDOFF.md](HANDOFF.md), [G1-TASK.md](G1-TASK.md),
[requirements.json](requirements.json), [REVIEW_AND_RESUME.md](REVIEW_AND_RESUME.md),
the [plan](../../integration-plan.md), [contracts](../../integration-contracts.md),
[presentation adaptation](../../presentation-adaptation.md), the
[inspectable-block decision](../../decisions/inspectable-blocks.md) and
[audiences](../../audiences.md). Where this catalogue and those documents disagree, the
existing authorities and recorded decisions win.

## 1. Design intent

- A report visibly consists of purposeful blocks. It is not the old dashboard with panels
  appended. The block shell, block navigation and per-block disclosure are the reader
  experience.
- Each block has a concise main message and expandable, block-specific evidence. Evidence
  includes explanations a reader can understand, not only hashes or JSON.
- Graphs appear where they answer a useful question (magnitude, trend, coverage, paired
  specifications). A block without a chart is normal.
- Reader controls must have a stated purpose and work. A control that filters already
  generated rows is not an analytical filter.
- Exact-value tables and direct artifact downloads remain part of the evidence, not a
  fallback for a broken chart.
- Audience presets guide composition and language. They are not separate templates and not
  rigid access restrictions; every audience retains access to the shared evidence.
- Custom stakeholders should eventually select, order and configure compatible blocks
  before a report run is generated. File-based recipes are the current interface.
- Functionality and scientific honesty take priority over cosmetic polish.
- Arbitrary CSV support, drag-and-drop editing and composed PDF are **not** existing
  functionality and are out of scope here.

## 2. Three configuration layers (do not merge)

| Layer | Meaning | Current local implementation | Proposed change |
|---|---|---|---|
| A. Analytical scope | Topics, reporting window, reference/index requirements, geography, measures, source and eligibility policy | Stakeholder settings validated by `workflow/config.schema.json` and `analyse.load_config`; selection decisions in `selection.csv`; saved results in the analysis bundle | Gate A/B1 added optional `include_topics` / `exclude_topics` (commit `181f206`); canonical configs keep the historical default |
| B. Composition and block bindings | Enabled blocks, order, instance IDs, selected saved results | `health-report/composition-recipe/2` in `scripts/health_pipeline/config/composer/compositions/`, validated by `publish.load_composition`; reference-comparison requires `topic`; deterministic v1 remains readable | Per-block period/measure parameters only when a block needs them; no general options framework |
| C. Reader interaction | Expansion, navigation, exact-value inspection, filtering of already generated content | Block navigation, `<details>` inspectors, methods quality filters, artifact downloads | Keep; do not present it as analysis |

Consequences that must stay explicit in the product:

- A table search does not change analytical scope.
- Selecting a topic for a block is a binding to a saved result; it is not a new analysis.
  If the requested topic is absent from the saved bundle, the block/report fails rather
  than triggering an analysis.
- Changing a recipe cannot broaden saved-data scope. A recipe only chooses among results
  already produced for the report's scope.
- A scope change requires a new analysis bundle; a different block/order uses the same
  bundle.

Gate status: Gate A/B1 (explicit topic scope, recipe v2 explicit reference-comparison
binding) is a completed implementation checkpoint at `181f206382f8c71a6a58f912ef02b507b0dd1280`
with its documented limitations and scoped review. Gate B2 (saved annual series contract and
one researcher trend instance) is implemented as an **uncommitted candidate** on
`design/contracts` based on `29f44f4f772107d8e25880ea657cbcd7b66b9303`; automated checks
and rendered-package checks pass, but it is not accepted, independently reviewed or
visually reviewed, and institutional/public trend variants remain unimplemented.

## 3. Snapshot types and intended flow

| Snapshot type | What it is | Current identifiers / location |
|---|---|---|
| Source-data snapshot | Preserved captured inputs | `snapshots/<snapshot_id>/`, `snapshot.json`, `harmonised_snapshot.json` |
| Analysis bundle | Saved results for one explicit analytical scope and method set | `reports/<audience>/data/` with `bundle.json`, `metrics.csv`, `series.csv`, `selection.csv`, `lineage.csv`, `checks.csv`, `stakeholder.json` |
| Report-run package | Frozen rendered output plus effective recipe, provenance and companion evidence | `<report>/report.html`, `methods.html`, `provenance.json`, `data/` |

Intended flow:

    choose source snapshot
    → configure analytical scope
    → choose audience/presentation preset
    → select/order/configure supported blocks
    → validate capabilities and resolve effective settings
    → reuse or generate required saved analysis
    → render and verify
    → freeze the report package and provenance

Block order changes do not trigger a new source download. Analytical scope changes may
require a new analysis bundle. Rendering a retained bundle is **not** proof of full
end-to-end reproduction, and this catalogue does not claim otherwise.

## 4. How to read the entries

Every block entry uses the same compact fields:

- **Identity and status** — proposed/current block type, state, existing source paths and
  contracts, and what review actually happened.
- **Reader purpose** — the exact question, audiences and why the block is not redundant.
- **Inputs and parameters** — saved inputs, supported parameters/defaults, period handling,
  compatibility and unavailable-input behaviour, and whether a change needs analysis.
- **Main presentation** — heading/message, values/units, graph (only when justified),
  exact-value alternative, audience depth and interpretation limits.
- **Expandable evidence** — the consistent “Inspect this block” concept; subsections that
  apply.
- **Interaction** — control purpose, default state, keyboard/no-JavaScript expectations,
  no network fetch/recalculation on open.
- **Provenance and failure** — saved-record bindings, instance versus shared evidence,
  unavailable/failed states, consistency tests and open human/visual questions.

Status vocabulary:

- **Implemented** — source and execution tests exist; the block renders in at least one
  route. Visual/accessibility/scientific acceptance is still separate.
- **Partially implemented** — the saved data or a legacy presentation exists, but there is
  no composed block or not all required semantics are present.
- **Proposed** — design intent only; no current block, contract or renderer.

Shared evidence rules (not repeated in every entry):

- Displayed values must bind to saved records and artifact identities. Opening evidence
  performs no calculation and no network fetch.
- Instance identity is distinct from shared evidence (snapshot, scope, method). Reusing a
  series or quality record in several blocks does not duplicate its evidence.
- Unavailable, unknown or failed states are shown explicitly. No first-row/alphabetic
  substitute and no invented zero.
- “Passing automated checks” is not proof of completeness or scientific correctness.
- Visual, accessibility, keyboard and browser interaction review is recorded separately
  from implementation. At the time of writing, no comprehensive browser review exists;
  the narrowed methods output has scoped user review only.

## 5. Shared analytical cores and presentation variants

A catalogue block is a reader-facing capability, not necessarily a new contract or
calculation.

| Shared core | Components / variants | Status |
|---|---|---|
| Reference comparison | `composer_contracts` instance/evidence + `publish.build_block` + R `reference_block`; public magnitude explanation is a presentation variant of the same checked result | Implemented core; v2 topic binding |
| Annual series | `health-report/series-component/1` saved-row binding + `series-trend` block; researcher standard, institution compact, public standard | Implemented core in all three recipes (uncommitted candidate); visual review pending |
| Selection / coverage | `analyse.select_series`, `selection.csv`; coverage and readiness blocks are composites of this saved record plus source metadata | Implemented `coverage-selection` (researcher; no year matrix); readiness still proposed |
| Quality and provenance services | `checks.csv`, `provenance.json`, methods `#quality-checks`, “Report settings and source files” | Implemented shared services |
| Sensitivity | Saved `:main` / `:sensitivity` metrics and group inputs | Implemented `sensitivity-comparison` composite (researcher) |

Rules:

- The reference comparison and public finding must consume the same checked result. Do not
  create a second percentage calculation for public language.
- The series core, if approved, should be one saved-row binding used by trend, sparkline
  and public variants.
- Coverage/readiness must not fabricate year-level detail from dataset-level decisions.
- Quality diagnostics are rendered from one prepared record; do not copy inconsistent
  per-block diagnostics.

## 6. Block catalogue

### 6.1 Context / scope summary

- **Identity and status.** Current composed block type `intro`; implemented as the composed
  introduction in all three recipes (`scripts/health_pipeline/templates/report_helpers.R`,
  `selection_intro`).
  Contract: composition recipe v2. Execution tests: composition smoke tests. Visual review:
  not comprehensively reviewed.
- **Reader purpose.** Answers “What data, question and scope does this report cover?”
  Primary audiences: all. It prevents the reader from reading the finding without knowing
  the selected diseases, geography, measure and years.
- **Inputs and parameters.** Saved `stakeholder.json` (audience title/question, scope,
  presentation) and the analysis bundle. No block-specific parameters. It must show the
  requested/effective topic scope and reference versus reporting years separately. A scope
  change needs analysis; wording-only changes are presentation.
- **Main presentation.** Audience title/question, selected topics, geography, measure,
  reporting window, reference/index years separately, snapshot date context. Usually no
  graph. Exact scope is repeated in the provenance/evidence panel.
- **Expandable evidence.** Requested versus effective scope; reasons for exclusions or
  unavailable topics; exact saved parameters and recipe; original-source information. The
  current implementation exposes this through report settings/provenance rather than a
  dedicated intro inspector.
- **Interaction.** No controls. Navigation to other blocks only.
- **Provenance and failure.** Scope values come from the saved settings, not display text.
  Do not imply national data is institution/canton-specific, and do not present build-machine
  paths as reader-accessible locations.

### 6.2 Reference comparison

- **Identity and status.** Block type `reference-comparison`; implemented. Sources:
  `scripts/health_pipeline/composer_contracts.py`, `publish.build_block` and
  `scripts/health_pipeline/templates/report_helpers.R`
  (`reference_block`), recipes v2. Execution tests: contract, render-block, composition and
  R smoke suites. Visual review: scoped user feedback on inspected output only; not a
  comprehensive visual/accessibility review.
- **Reader purpose.** Answers “How does the selected saved observation differ from the
  reference?” Primary audiences: all (the public magnitude explanation is the same result
  with plainer language). It is the primary quantitative block.
- **Inputs and parameters.** Saved `reference_change` metric, its two saved count metrics
  and the saved scope. Required v2 parameter: `topic`; instance ID; years/unit come from
  the saved scope/result. Reject a topic that is not included, has no saved result or has
  ambiguous bindings; no fallback. Analysis required for a new scope or metric.
- **Main presentation.** Subject, reference and latest periods, exact count pair, saved
  percentage and unit, concise descriptive caveat. An optional two-bar/paired-value view
  may be added only if it improves magnitude comparison. No person icons or unsupported
  interpretation. Exact counts are always present.
- **Expandable evidence.** Data and scope; bound metric IDs and inputs; formula/availability;
  snapshot and source rows; applicable quality context (with relevance limits); analysis and
  render implementation identities; reproduction entry point and lineage record.
- **Interaction.** “Inspect this block” native disclosure, collapsed by default; no
  calculation on open.
- **Provenance and failure.** The checked instance identity binds the displayed subject and
  counts. A failed contract/evidence check shows an explicit unavailable block and, for an
  explicit v2 binding, fails the report/batch rather than silently succeeding. Absolute
  difference requires a saved/validated result path; renderer arithmetic is not authorized.
  Current implementation is health-specific; neutral numerical rendering and domain copy
  are not yet fully separated. No generic CSV or repeated-instance claim.

### 6.3 Saved annual series / time trend

- **Identity and status.** Block type `series-trend`, contract
  `health-report/series-component/1`, schema
  `scripts/health_pipeline/config/composer/series-contract/1.json`; implemented on
  `design/contracts` (base `29f44f4`, uncommitted) and wired into all three persistent
  recipes: researcher standard, health institution compact, public standard. Execution
  tests: `tests/test_composer_series.py` and `tests/r_series_smoke.R`; rendered-package
  checks in `~/.local/state/composer-bootstrap/g2-batch-20261029T020755`. Not independently
  or visually reviewed; the compact variant has structural assertions only. Saved annual
  `series.csv` rows exist for the current scope (12 topics × 2019, 2021–2025 in the retained
  bundle; no 2020).
- **Reader purpose.** Answers “What happened across the available selected periods?”
  Audiences: researcher default; institutional overview and public longer view are variants
  of the same series core.
- **Inputs and parameters.** Saved series rows for one topic and measure; display years
  within the report window (default the window); instance ID; audience detail. The current
  recipe entry is `{block: series-trend, instance_id, topic, measure, years?}`, valid only
  under `health-report/composition-recipe/2` and limited to one instance per recipe; `years`
  is an inclusive `[start, end]` inside the reporting window and defaults to that window.
  Reference or base years outside the window are separate observations, not part of the
  connected trend. Requested topics/periods must exist in the saved bundle; no first-topic
  fallback. A new scope needs analysis; a new time granularity is not supported by current
  saved data.
- **Main presentation.** Subject, measure, unit, geography and actual period range; annual
  chart with truthful gaps; exact-value table; descriptive, audience-appropriate text.
  Line segments only where continuity is justified. Do not connect an isolated 2019
  reference through missing 2020 into 2021–2025 without explicit separation. No smoothing,
  forecasting, significance tests or uncertainty bands.
- **Expandable evidence.** Selected series rows and count-metric bindings; period coverage;
  artifact digest; implementation identities; quality linkage level and limits.
- **Interaction.** No analytical filter. A display-range control, if added, is presentation
  only and must be reflected in the rendered record/provenance.
- **Provenance and failure.** Implemented as a separate contract rather than an extension of
  the percentage comparison: one checked document per instance, R selects it by
  `instance_id` and expected component type, and a failed check renders an unavailable state
  and fails the report/batch. Validation re-reads saved rows and metrics (unique topic/year
  rows, one included dataset/source, metric subject/year/unit/value agreement, requested
  window, artifact digest) without recomputing a count. Gap and malformed-row cases are
  labelled synthetic fixtures, not findings in the retained data. Missing years are gaps, not
  zero. A snapshot hash beside a chart does not prove row selection.

### 6.3a Multi-topic annual series collection

- **Identity and status.** Block type `series-collection`, implementation on top of
  `health-report/series-component/1`; implemented in all three persistent recipes
  (researcher standard, institution compact, public standard). One collection per recipe;
  a recipe cannot combine it with a standalone `series-trend` block.
- **Reader purpose.** Answers “What happened for each selected disease?” without implying a
  cross-disease comparison. Researcher default; institution temporal context behind the
  monitoring table; public default topic with clearly labelled exploration.
- **Inputs and parameters.** `{topics: "eligible" | [{topic}], measure, years?, presentation?:
  {style, default_topic?}}`. `eligible` resolves the saved bundle's included topics in
  ascending topic order; an explicit list keeps author order and must resolve completely.
  One measure per collection; `years` is an inclusive range inside the reporting window;
  defaults are style `standard` and the first resolved topic.
- **Main presentation.** One native disclosure panel per topic, default topic open, each with
  its own heading, chart, exact-value table and inspector. Independent panels; no shared
  axis, overlay, normalisation or index. Collection inspector lists members, member ids and
  the collection identity.
- **Expandable evidence.** Per-member saved-row bindings, gaps, artifact digest, snapshot,
  quality context and identities; collection-level measure, periods, ordering and
  `series-collection-identity/1`.
- **Interaction.** Native `<details>`/`<summary>`; all panels work without JavaScript; no
  selector, filter or recalculation. Opening a panel performs no calculation.
- **Provenance and failure.** Each member is separately checked; a mismatch between the
  requested topic and the checked record fails the collection, and any failed member fails
  the composed report rather than leaving a partial set. `display_scope` reports
  `collection_topics` and `collection_default_topic` separately from standalone and
  monitoring topics.

### 6.4 Analytical population / coverage and selection

- **Identity and status.** Implemented composite `coverage-selection` (uncommitted,
  `design/contracts`) in the researcher and narrowed recipes. It reads saved `selection.csv`,
  `sources.csv` and `series.csv`, distinguishes datasets, topics and saved observations, and
  takes “displayed topics” from the resolved recipe bindings. No year-level completeness
  matrix exists: the block states that the saved bundle records dataset/topic decisions, not
  per-year coverage.
- **Reader purpose.** Answers “What entered the analysis, and what was unavailable or
  excluded?” Researcher default; institution monitoring coverage; public short inclusion
  statement with expandable detail.
- **Inputs and parameters.** Saved selection decisions, source rows, scope and required
  years. No invented per-year coverage: the saved bundle records topic-level decisions and
  reasons, not a full per-year completeness matrix. A detailed matrix would require an
  upstream saved artifact; do not infer it.
- **Main presentation.** Requested → eligible → displayed reconciliation; topic-by-year
  matrix only where saved records support it; distinguish missing, excluded, eligible and
  outside-window periods. A labelled matrix is useful; never rely on colour alone.
- **Expandable evidence.** Dataset/topic IDs, exact selection decisions and reasons,
  required-year/completeness rules, source-priority resolution.
- **Interaction.** Row filtering is reader interaction only, not scope change.
- **Provenance and failure.** Do not fabricate year-level coverage from a dataset-level
  exclusion. If coverage is unavailable, say so and name the upstream requirement.

### 6.5 Sensitivity / alternative specifications

- **Identity and status.** Implemented composite `sensitivity-comparison` (uncommitted,
  `design/contracts`) in the researcher recipe. It binds the saved `<class>:main` and
  `<class>:sensitivity` group totals, reference changes and member metric lists; member
  differences are derived from those saved lists. No dedicated contract was needed: the
  comparison is a presentation of saved metrics.
- **Reader purpose.** Answers “How dependent is the saved comparison on an explicit
  analytical choice?” Researcher default; optional for institution/public with simpler text.
- **Inputs and parameters.** Both saved specifications and their member lists. No new
  alternative is created in presentation; a new exclusion/specification requires analysis.
- **Main presentation.** Main and alternative specifications with exact values; the
  members/exclusions that differ; paired points, aligned bars or a compact table according
  to scale.
- **Expandable evidence.** Specification parameters, member lists, saved aggregate/result
  bindings, assumptions, method and identities.
- **Interaction.** Disclosure only.
- **Provenance and failure.** Differences are not confidence or uncertainty intervals. Do
  not call a result robust without a defined, supported assessment. Missing alternatives
  show unavailable, not an inferred result.

### 6.6 Monitoring overview

- **Identity and status.** Implemented composite `monitoring-overview` (uncommitted,
  `design/contracts`) in the health-institution recipe. One row per included topic from the
  latest saved annual observation, with each available saved reference or period comparison
  bound separately and its periods shown; percentages and counts are formatted for display
  while exact saved strings stay in evidence. It is descriptive only: no score, ranking,
  threshold or common scale. Per-topic sparklines are deferred.
- **Reader purpose.** Answers “Which selected indicators should an institutional reader
  inspect first?” Institution default; optional elsewhere.
- **Inputs and parameters.** Saved latest counts, comparison values and available historical
  context per topic. No invented priority or risk score.
- **Main presentation.** One row per configured topic with latest saved value, comparison,
  compact historical context, availability/quality status and a link to detailed evidence.
  Sparklines/small multiples only from the shared series core; clear units, no misleading
  common scale.
- **Expandable evidence.** Per-row saved bindings, source and quality context using shared
  inspectors.
- **Interaction.** Topic search/sort only for sufficiently large tables; explicit sort
  criterion.
- **Row navigation (C1, uncommitted candidate).** A row offers “View annual series” only when a
  checked `series-collection` record in the same report has a member with the same topic,
  measure, geography and saved dataset, and the collection's effective years equal the
  monitoring reporting window. The target is that member's rendered panel id, read from the
  checked record; reader-facing labels, saved CSV order and panel order are never used. Rows
  without a compatible member stay plain text with a short reason (this topic, another
  measure/source/period, ambiguous target, collection not checked). The link is a same-page
  anchor, so it works without JavaScript; a small no-library script opens the collapsed panel
  and focuses its summary. Other panels stay independently openable, and link targets are
  presentation metadata that enter no analytical, rows or instance identity.
- **Provenance and failure.** No red/amber/green alerts without approved threshold policy.
  A large percentage change is not an outbreak or recommendation. Annual national data
  supports retrospective national monitoring, not real-time institutional surveillance.

### 6.7 Monitoring readiness / data currency

- **Identity and status.** Partially implemented data (quality checks, publication/retrieval
  dates in provenance); no composed block.
- **Reader purpose.** Answers “Are the selected indicators adequately available and current
  for this use?” Institution default; optional researcher.
- **Inputs and parameters.** Expected versus observed periods only where explicitly known;
  recorded publication/retrieval dates; source completeness metadata; warnings and recorded
  handling. No composite quality score.
- **Main presentation.** Separate availability/coverage, recorded quality findings and
  source/snapshot currency. A compact status/coverage table or timeline where supported.
- **Expandable evidence.** Checks and selection handling, dates, limitations, source metadata.
- **Interaction.** Disclosure only.
- **Provenance and failure.** Retrieval date alone is not reporting timeliness; do not infer
  reporting delays without event/submission/publication timestamps and expected schedules.
  Unknown status is not “good”.

### 6.8 Changes since previous release

- **Identity and status.** Proposed. Requires two identified snapshots/releases and
  comparability checks; unavailable with the single retained snapshot.
- **Reader purpose.** Answers “What changed between two identified reporting cycles?”
  Optional for institution/researcher; public only with a plain-language summary.
- **Inputs and parameters.** Both snapshot/bundle identities and scopes; old/new values and
  bindings; recorded reasons where available. No simulation from one snapshot.
- **Main presentation.** Separate newly available periods, revisions to existing values,
  topics added/removed, and changed source/analytical settings. A revision table or paired
  values may be enough.
- **Expandable evidence.** Both identities, comparability checks and old/new bindings.
- **Interaction.** Disclosure/table inspection only.
- **Provenance and failure.** Do not mistake revised historical counts for new cases; do not
  attribute change to a cause without recorded evidence. Without two comparable snapshots,
  show unavailable.

### 6.9 Public finding / magnitude explanation

- **Identity and status.** Implemented as a presentation variant of the reference comparison
  (editorial audience copy and plain-language-first ordering in
  `scripts/health_pipeline/templates/report_helpers.R`), not as a separate block type or
  calculation, and wired into the public recipe beside the series block.
- **Reader purpose.** Answers “What changed, in understandable numbers and words?” Public
  default; optional for other audiences.
- **Inputs and parameters.** The same checked result as the technical comparison. No second
  calculation.
- **Main presentation.** Short narrative with count pair, periods, percentage and units;
  avoids a percentage-only headline. Optional paired bars or labelled values.
- **Expandable evidence.** Same bindings and identities as the comparison; exact values and
  original artifacts remain accessible.
- **Interaction.** Disclosure only; no simplified/opaque copy.
- **Provenance and failure.** Public language must not change the saved result or scope. If
  the comparison is unavailable, the public text is unavailable too.

### 6.10 Meaning and interpretation limits

- **Identity and status.** Implemented as the composed `limitations` block plus
  audience-specific copy; the legacy methods/report also contain limitation sections.
- **Reader purpose.** Answers “What do these figures tell us, and what should we not
  conclude?” All audiences.
- **Inputs and parameters.** Saved measure/source definitions and applicable interpretation
  notes. No new analysis.
- **Main presentation.** Short “shows / does not establish” text beside the finding; for
  surveillance: notifications are not every infection, descriptive differences do not
  establish cause, counts do not establish individual risk or severity. No chart required.
- **Expandable evidence.** Measure/source definition and interpretation notes; quality
  context where relevant.
- **Interaction.** Disclosure only.
- **Provenance and failure.** Do not apply health-notification caveats to unrelated CSV
  measures. This block may be attached content rather than a standalone card; both placement
  options are acceptable without a new framework.

### 6.11 Topic background / authoritative context

- **Identity and status.** Proposed. No curated topic descriptions or reviewed external
  sources exist in the repository.
- **Reader purpose.** Answers “What does this topic mean, and where can I learn more?”
  Optional all audiences when curated content exists.
- **Inputs and parameters.** Curated description, source, version/date of review. Not derived
  from the analysis CSV.
- **Main presentation.** Short description and authoritative link; no generated prevention
  or treatment advice.
- **Expandable evidence.** Source, review/version/date.
- **Interaction.** Disclosure only.
- **Provenance and failure.** Mark unavailable until curated content exists; keep domain
  information distinct from dataset findings.

### 6.12 Quality summary and detailed check results

- **Identity and status.** Implemented. Concise summary in the composed limitations block;
  detailed section at `methods.html#quality-checks`; data from `checks.csv`, `selection.csv`,
  `sources.csv`; tested in Python and R smoke checks. Scoped user review covered methods
  detail; no comprehensive browser/accessibility review.
- **Reader purpose.** Answers “What was flagged, what was done, and does it affect this
  report?” All audiences; explanation depth varies.
- **Inputs and parameters.** Saved check-result rows, selection and source records. No
  validation rerun in presentation.
- **Main presentation.** Severity/status totals, warning categories, concise relevance
  statement; methods page lists all recorded rows with status/check/dataset filters and
  per-rule explanations. Severity counts and structured tables; usually no graph.
- **Expandable evidence.** Counting definitions, recorded diagnostics, selection handling,
  unknown-rule fallback, exact `checks.csv` download; finding-level relevance is stated as
  unevaluated unless a checked linkage exists.
- **Interaction.** Methods filters/search are scoped to the detailed table and are staging
  controls only; no generic search on short settings tables.
- **Provenance and failure.** Result rows, rule types, datasets, affected records and
  findings are distinct; automated checks are not proof of completeness/accuracy. Avoid
  inconsistent duplicate diagnostics across blocks.

### 6.13 Reproduction / exact artifacts

- **Identity and status.** Implemented in the composed `reproduction` block plus the
  “Report settings and source files” panel; methods cross-links and accompanying `data/`
  folder are published. Tested by rendered-package checks and executed example code.
- **Reader purpose.** Answers “How was this report produced, and can I inspect its saved
  inputs/results?” All audiences.
- **Inputs and parameters.** Provenance, manifest, published artifacts, effective recipe.
- **Main presentation.** Purposeful code disclosure, readable production facts, exact
  artifact actions, report/methods cross-links. No chart.
- **Expandable evidence.** Separate saved-file integrity/inspection, presentation rerender
  and production-analysis reproduction; hashes show identity/integrity, not correctness;
  build-time input paths are not reader paths; the manifest has no invented self-digest.
- **Interaction.** Native disclosures and explicit download/view actions; no inert search
  on short tables.
- **Provenance and failure.** Downloads require the full package, not HTML alone. Composed
  PDF is unsupported unless later work proves otherwise. Missing companion files must fail
  validation rather than leave a success-looking link.

### 6.14 Reusable analytical extract

- **Identity and status.** Partially implemented: exact-value block tables and full saved
  artifact downloads exist; a per-block derived extract is not implemented.
- **Reader purpose.** Answers “Can I obtain precisely the saved observations behind this
  block?” Optional all audiences.
- **Inputs and parameters.** Selected topic/measure/geography/periods and the saved artifact.
- **Main presentation.** Exact-value table and a scoped download description.
- **Expandable evidence.** Scope of the extract, source artifact identity and derivation
  filters/identity.
- **Interaction.** Explicit download only.
- **Provenance and failure.** An extracted subset is a derived artifact, not the original
  `series.csv`; do not claim it exists until implemented and verified. Full saved-artifact
  downloads remain separately available.

## 7. Audience journeys and matrix

Curated defaults, not rigid restrictions. Every audience keeps access to the shared
evidence, quality detail, provenance and reproduction.

- **Researcher:** context/scope → analytical population/coverage → saved annual series →
  explicit comparison → sensitivity where supported → quality/reusable extracts/reproduction.
- **Health institution:** monitoring overview → readiness/currency → selected indicator
  detail → release changes when two snapshots exist → evidence/reproduction.
- **Public:** concise finding with magnitude → longer view → meaning/limits → curated
  topic/source information → expandable methods/evidence.

| Block | Researcher | Health institution | Public | Special inputs |
|---|---|---|---|---|
| Context / scope | default | default | default | — |
| Reference comparison | default | default | default | saved reference result |
| Annual series / trend | default (standard) | default (compact) | default (standard) | saved series rows; `series-component/1` implemented |
| Coverage / selection | default | optional | optional (short) | selection records; year coverage only if saved |
| Sensitivity | default | optional | optional (plain text) | saved alternative specifications |
| Monitoring overview | optional | default | not a default | saved series core |
| Readiness / currency | optional | default | optional | checks, dates, completeness metadata |
| Release changes | optional | optional | optional | two comparable snapshots |
| Public finding / magnitude | optional variant | optional variant | default variant | same checked comparison |
| Meaning / limits | default | default | default | measure definition |
| Topic background | optional | optional | optional | curated reviewed content (proposed) |
| Quality summary/detail | default | default | default (plain summary) | checks/selection/sources |
| Reproduction / artifacts | default | default | default | published package |
| Reusable extract | optional | optional | optional | per-block extract (proposed) |

## 8. Custom stakeholder design

Intended configuration experience (not implemented as a form):

1. Choose a preset.
2. Set supported analytical scope.
3. Select/order compatible blocks.
4. Set block parameters.
5. Review effective scope, required inputs and the report outline.
6. Generate and freeze the report run.

Capability states to show before generation:

- **available** — saved inputs and implementation exist;
- **needs parameters** — the block requires a topic/period/instance choice;
- **needs analysis** — the requested scope/results are not in any saved bundle;
- **unavailable inputs** — required records (for example a second snapshot) do not exist;
- **unsupported implementation** — proposed block or semantic not implemented.

Examples:

- Release-change block with one snapshot → unavailable inputs.
- Series block without a selected saved topic/measure/periods → needs parameters/analysis.
- Sensitivity block without both saved specifications → unavailable inputs.
- Narrowed scope that leaves a required class/variant group empty → analysis failure with
  the class/variant and scope; no synthetic zero or substitute disease.

File-based recipes/configuration are the immediate interface. A future form must emit the
same validated configuration and use the same analysis/render path, not a second scope
engine. Drag-and-drop editing is not authorized.

## 9. Mandatory evidence floor

Customization may change placement and detail but must not erase:

- source/snapshot identity;
- effective analytical scope and recipe;
- relevant limitations;
- quality information and its relevance limits;
- reproduction/provenance access.

These may be shared services/footer/methods rather than large cards in every block.
Omitting a block must not imply an analysis was performed; omitting sensitivity must not
imply robustness; unavailable quality linkage must not appear as “no relevant warnings”.

## 10. Implementation sequence

The current sequence is:

1. Treat Gate A/B1 as a completed implementation checkpoint, retaining its documented
   limitations and scoped review.
2. Gate B2 candidate: the saved-series contract, one researcher trend instance and its
   rendering checks are implemented and uncommitted; acceptance and independent/visual
   review remain pending.
3. The series core is rendered in all three persistent recipes (researcher standard,
   institution compact, public standard); browser review of the compact variant remains.
4. Coverage/selection communication from saved records is implemented for the researcher
   scope; a year-level matrix still requires a saved upstream artifact.
5. The institutional monitoring overview is implemented descriptively; priority ordering and
   alerting remain unauthorised without an approved policy.
6. The sensitivity comparison is implemented from saved metrics, and public interpretation is
   refined through the editorial magnitude variant.
7. Add release comparison only when two snapshots and comparability are available.
8. Build a configurator over stable recipe interfaces.

Full analysis-to-three-composed-output reproduction remains an explicit workflow
integration/acceptance concern. Broader CSV mapping, repeated comparisons, composed PDF and
cosmetic overhaul remain separately scoped.

## 11. Open consequential decisions

- Series contract/identity shape: resolved for this slice as the separate
  `health-report/series-component/1` document with analytical/rows/instance identities;
  whether institutional and public variants reuse this core unchanged is still open.
- Whether year-level coverage can be derived from saved records or needs a new saved
  artifact.
- Whether sensitivity gets a dedicated contract/binding or reads saved metrics through a
  composite.
- Curated topic-background content source, review and versioning.
- Release comparison comparability rules and required dual-snapshot evidence.

These are decisions for their own gates; this catalogue does not resolve them.
