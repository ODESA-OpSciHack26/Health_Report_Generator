# Track B branch notes: parameterised report composer

Status: approved direction; implementation not started by this document.
Date: 27 October 2026.
Branch: `m5/report-composer`.
Parent branch: `m4/frozen-descriptive-reports`.
Exact parent commit: `c72bd54f69300b8e79bb967c201529d48625ae45`.
Repository: `ODESA-OpSciHack26/Health_Report_Generator`.

## 1. Branch contract

Track A is finalized and accepted locally. Its source, three stakeholder reports, descriptive calculations, graphs, provenance and reproduction workflow are the stable baseline. Track B must not move the frozen reference or modify its historical evidence.

This branch is a daughter of the exact frozen commit, not of remote main or the older 28edd82 checkpoint. Its first commit contains only these notes. Functional changes follow as small, testable increments.

The user authorized continuing Track B after confirming all final Track A checks passed. Remote publication, tags, releases and protection settings are separate actions. Creating this branch does not publish local evidence or introduce a composer UI.

## 2. Product goal

Replace hardcoded stakeholder page-building branches with a common, validated library of reusable report blocks. The researcher, health-institution and public reports become three deliberately different default presets.

A steward can start from a preset, add/remove/duplicate/configure blocks, choose their order, save a custom composition and reproduce it through a command. Adding a stakeholder using existing blocks means adding configuration, not another QMD or audience-specific implementation branch.

A new block type or analytical method still requires developer implementation, versioning and tests. Configuration must not execute arbitrary user code.

## 3. Existing baseline and boundaries

Track B inherits source inspection and preparation, explicit mappings, temporal settings, captured source bytes, independent replay, shared-source rendering, staged no-replace publication, descriptive results, source-row references, static ggplot2 PNGs and interactive tables.

The baseline passed 353 full-suite tests, pinned lint, one-command example verification, canonical build/release checks, Shiny/dashboard smoke checks and a no-op rebuild. The final real-data reports were verified under the clean commit, retained identical analytical results and received user browser acceptance. Preserve the actual evidence records; this document does not replace them or claim a fresh container image build.

Keep these invariants:

- Missing values remain missing, not zero.
- Presentation changes do not silently change the analysis population.
- Saved full-precision results do not change when display precision changes.
- Repeated category-period observations are not silently aggregated for comparisons.
- Percentage changes require eligible periods and a positive reference value.
- Different disease counts are not casually summed into independent people.
- Unrepresented selected years are not inferred as zero or established publisher failures.
- Mandatory machine-readable provenance and material interpretation context remain present.
- Existing output directories are never overwritten by a new render.
- The default command still produces three established stakeholder outputs.

## 4. Separate three configuration layers

### 4.1 Data selection

Defines source identity, mappings, measure/unit, geography, periods, selected series and exclusions. A selection change invalidates affected analysis. National-only data cannot support a canton-specific label or map.

### 4.2 Analysis plan

Defines grouping, descriptive metrics, reference/latest periods, estimators, missingness policy and any explicitly supported test/model. Choosing a new baseline or test is an analytical change, not a chart option.

### 4.3 Composition and display

Defines block instances, order, headings, detail, disclosure, visible metrics, display precision, chart layout and theme. Hiding a mean column does not remove the saved mean. Limiting displayed series does not remove complete saved results.

Version one uses a report-global analytical scope. Block-local display subsets are allowed and labelled. Different analytical populations in different blocks are an advanced feature requiring separate scope/result identities; do not smuggle this into ordinary display filtering.

## 5. Block contracts

Each registered type declares a stable type/version, name/category, description, validated options, required source fields/results, eligibility/dependencies, supported formats/interactivity, renderer, tests and empty/failure behavior.

Each block instance declares a unique instance identity, type/version, resolved settings, heading, placement, order and initial disclosure state. Duplicated blocks need different identities and DOM anchors.

Results are calculated in the analysis layer and reused. Renderers may format/sort for display but must not independently recompute already saved statistics. Adding a chart must not secretly choose periods or impute observations.

Initial registry status must distinguish:

- Available: implemented and eligible.
- Configuration required: implemented but incomplete settings.
- Unavailable: missing data/design requirements, with a reason.
- Planned: not implemented, never an active feature toggle.

## 6. Catalogue: introduction and orientation

Candidate blocks:

- Report identity: title, subtitle, institution, author, audience and reporting cycle.
- Scope: source, measure, units, geography, selected periods and series.
- Research question/objective.
- Executive summary based on saved results, linked to supporting evidence.
- How to read: terminology, navigation and interpretation.
- Comparison context: explicit baseline/latest periods and eligibility.
- Steward interpretation with attributed author/date.
- Responsible institution/contact.

Separate generated statements from authored commentary. A human action note must not look like an automatically established public-health conclusion.

## 7. Catalogue: precise tables and audit

| Block | Options and requirements |
|---|---|
| Prepared observations | Column selection/order, initial sort, page length, friendly or exact labels |
| Original source records | Original columns only under an explicit disclosure/export policy |
| Descriptive-results table | Selected metrics and metric-column order, grouping labels |
| Comparison table | Reference/latest, absolute/relative difference, eligibility and notes |
| Coverage table | Represented periods, first/last period, valid/missing counts |
| Data dictionary | Variable meaning, units, coding, missing-value definitions |
| Exclusion log | Excluded rows/series and justified reasons; extend generic support if needed |
| Calculation trace | Result identity, contributing source rows, checksum and method |
| Full-precision audit | Exact values/technical identifiers, distinct from reader-facing rounding |

Existing rows/results can be extracted into blocks; an original-source table or dictionary is not automatically an implemented feature. Reader and audit modes should coexist without forcing raw floating-point output onto the front page.

## 8. Catalogue: descriptive statistics

Support one configurable statistics table and separate statistic cards. The same saved value can appear in both without recalculation.

| Group | Metrics | Initial capability |
|---|---|---|
| Counts | Supplied rows, valid values, missing values | Existing results |
| Central tendency | Mean, median | Existing results |
| Spread | Sample SD, minimum, maximum, quartiles | Existing results |
| Additional spread | Range, IQR, variance, median absolute deviation | New calculations/tests where not already saved |
| Position | Explicit percentiles | Extend quantile contract |
| Relative variation | Coefficient of variation | Conditional extension; handle unsuitable or near-zero means |
| Coverage | Represented periods, first/last, missing calendar periods | Existing bounded coverage policy |
| Comparison | Absolute and percentage change | Existing explicit eligibility rules |

State scope and valid count: for example, mean of the supplied annual observations within one series. Record quantile convention, SD degrees of freedom and missingness policy. SD across annual values is not automatically uncertainty around an estimated population mean. Do not provide an ambiguous plus/minus-error toggle.

## 9. Catalogue: future statistical tests/models

These are candidates for a separately reviewed advanced library, not version-one promises.

| Question | Candidate method families |
|---|---|
| Independent-group comparison | Welch t-test; justified rank-based alternative |
| Paired comparison | Paired t-test; Wilcoxon signed-rank |
| Several groups | ANOVA/Welch ANOVA; Kruskal-Wallis |
| Categorical association | Chi-square; Fisher exact when appropriate |
| Association | Pearson/Spearman |
| Count modelling | Poisson/negative-binomial family with justified exposure/design |
| Temporal modelling | Suitable time-series/trend methods with diagnostics |
| Uncertainty | Estimator/design-specific confidence intervals |

Require the question, outcome, unit of analysis, groups/pairs, design assumptions, effect estimate, uncertainty method, diagnostics and multiplicity policy. Structural validation cannot prove scientific appropriateness.

The current 72 annual-series rows are not 72 independent patients. Temporal dependence and selected years must not be ignored. A method must not become available solely because a column is numeric. Do not display a p-value or significance badge without effect/uncertainty/context. Unsupported methods remain unavailable with explanations; no silent method substitution.

## 10. Catalogue: charts

- Time: separate-series trends and small multiples, initially static PNG.
- Comparison: latest-period bars, absolute/percentage change, reference/latest pairs.
- Distribution: existing histogram/points; additional box/range representations only after tested implementation.
- Quality: missingness panels, coverage matrix, represented-period timeline.
- Relationships: scatter or fitted relationship only with compatible mappings and requested analysis.
- Geography: maps only with supported real geography.
- Uncertainty: intervals only from justified saved calculations.
- Interactive exploration: hover/zoom/series toggling is a separate backend capability, not supplied by current PNGs.

Settings may include displayed series/order, panel layout, size, caption, unit, scale and disclosure. Explicit chart limits preserve complete analytical results. Common versus separate scales must be visible. Count bars should not default to misleading truncated baselines. Log scales require compatible values and clear labels.

## 11. Catalogue: quality, interpretation and provenance

Quality blocks include missingness, repeated-period diagnostics, coverage, comparison eligibility, source revisions/definition changes, exclusions, small-number cautions under a defined policy, limitations and what the dataset cannot answer.

Editorial blocks include three things to know, explain this chart, glossary, compare supported findings, steward interpretation/action, methodology context, highlighted caveat, further questions and contact.

Provenance blocks include source summary, data version/checksum, filters, calculation policy, code/software identity, reproduction instructions, permitted downloads, source-row trace and composition history.

Detailed sections can be optional/collapsible. Machine-readable provenance and material caveats cannot disappear. Active validation failures remain blocking even when the quality block is hidden.

## 12. Initial delivery: approximately fifteen block types

1. Identity/scope.
2. Lead summary.
3. Overview cards.
4. Prepared observations table.
5. Configurable descriptive table.
6. Individual descriptive cards.
7. Comparison/eligibility table.
8. Series trend chart.
9. Latest-period chart.
10. Reference-change chart.
11. Distribution diagnostic.
12. Quality/missingness summary.
13. Coverage/selection explanation.
14. Attributed interpretation/context.
15. Provenance/downloads/reproduction.

Implement these using existing calculations first. Do not announce inference, maps, forecasts or new interactive backends as working features.

## 13. Distinct default presets

### Researcher

Question/scope -> quality/coverage -> statistical overview -> trend/distribution diagnostics -> comparison eligibility -> detailed rows -> methods/reproduction. Preserve precise definitions, audit access and complete results.

### Health institution

Monitoring scope -> changes to review -> latest values/reference comparison -> eligibility/quality -> optional trends -> attributed operational context -> evidence. Do not invent institution-specific geography, thresholds or alerts.

### Public

Plain-language main message -> one main chart -> interpretation/limits -> reachable supporting counts -> concise selection explanation -> source/methods. Do not simply hide technical columns while retaining an overwhelming technical page.

### Custom

Start from a named preset or a blank layout with protected minimum context. Label the result custom and record its origin and resolved composition. Saving a custom report does not modify defaults. Historical custom reports do not silently change when a preset is updated.

## 14. Ordering and placement

Support add/remove/move/duplicate/configure, move-up/down plus optional dragging, appendix placement, initial disclosure and explicit restore-defaults.

Use sensible zones: identity/lead, main content, supporting detail and methods/appendix. Body order is flexible; identity/evidence access and material caveats remain protected.

Regenerate navigation/captions/cross-references from stable instance IDs. Reordering must not break links, duplicate anchors or leave references to removed figures. An essential explanation travels with its dependent chart/claim.

## 15. Composer interface

Left: searchable block library, categories, eligibility and reasons.

Centre: ordered outline plus actual report preview, not a fake design surface. Show type/title, disclosure and move/configure/duplicate/remove controls.

Right: selected-block options. A statistics block offers metrics/column order, inherited grouping/scope, cards/table, display precision, audit labels, heading and placement.

Clearly distinguish analysis edits from presentation edits. A drag must not unpredictably trigger an expensive model. Use an explicit validation/render step when calculations change.

Provide keyboard reordering and non-drag controls, visible focus, meaningful labels, reorder announcements, readable contrast and narrow-screen behavior. Preserve the improved header/navigation; automated colour checks alone do not establish complete accessibility acceptance.

## 16. Architecture and dependencies

Pipeline:

Captured source -> validated selection/preparation -> validated analysis plan -> saved results/lineage -> resolved composition -> shared-source block renderers -> staged verified publication.

Separate adapters, analysis planner/execution, registry, preset resolver, composition validator, render dispatch and publication verification. Retain the shared QMD entry point and companion methods view rather than one QMD per stakeholder.

Dependencies must explain missing configuration. A reference-change block needs explicit periods and eligible results. A map needs actual geography. An uncertainty block needs a valid implemented method. A source table needs export permission.

The resolver must not silently choose baselines, pair observations, impute, run tests or alter scope. Unresolved required blocks prevent publication. An optional omission policy must be explicit and recorded, not silently hide meaningful evidence.

## 17. Safety and privacy

Keep source identity, essential scope/units, material caveats, missing/unavailable meaning, methods access and machine provenance across compositions.

Sanitize limited authored content; do not execute arbitrary HTML/scripts or user formulas. Hiding a table or download link does not remove original bytes from a bundle. Future private-data support requires actual artifact-level disclosure policy and separate internal/public packaging. Version one is not an arbitrary patient-data hosting service.

## 18. Configuration, versioning and caching

Record author request plus fully resolved configuration: schema version, source/selection identity, analysis methods/results, preset/version, ordered block instances/versions/settings, theme/output, validation/omission decisions, software/code identity and generation time.

Do not resolve old reports against whichever preset is newest. Use explicit migration rules and preserve historical effective configuration.

Selection or method changes invalidate analysis. Reordering/rounding invalidate rendering but not numerical results. Renderer/theme changes affect presentation identity. Cache by effective settings and relevant identities, not a report name. Isolate temporary outputs and retain staged no-replace publication.

Do not promise byte-identical forced HTML across timestamps/engines; retain the actual verified numerical and provenance contracts.

## 19. Work packages and checkpoints

### C0: create branch and commit notes

Only this Markdown is committed. Verify its parent is the freeze SHA and the frozen branch remains unchanged. Export selected committed source for inspection; do not alter application behavior.

### C1: inspect current code and define contracts

Read actual source before editing. Map existing saved result keys, renderer functions, audience validation, request schema, provenance and verifier expectations. Produce a concrete block/result dependency inventory. Define a strict versioned composition contract and tests without enabling incomplete rendering or changing existing request meaning.

### C2: extract renderers

Register reusable existing content incrementally, preserving calculation identities and output verification. No duplicated statistics and no fourth hardcoded layout.

### C3: declarative presets

Express the three accepted information architectures in configuration. Keep default commands and source/shared-template behavior working. Test structural stakeholder distinction.

### C4: saved custom compositions

Add validated command-line load/export and explicit block order/settings. Test addition/removal/duplication and effective provenance. New analytical semantics require explicit schema decisions.

### C5: graphical composer

Choose an integration approach after code inspection. Implement library/outline/settings/preview with accessible controls. Do not migrate the UI framework by default.

### C6: advanced analysis

Separate method/scientific review, results schemas, tests and eligibility. Not a prerequisite for an excellent descriptive composer.

### C7: release/handover

Clean source, complete tests/lint, canonical regression, default/custom reproduction, verified artifacts and actual browser acceptance. Protect the Track A boundary.

## 20. Acceptance tests

Composition: stable identities/order; reject unknown settings/types/versions, duplicate IDs, missing dependencies and invalid removal of protected context. Explain unavailable blocks.

Numerical invariance: reorder, round or hide blocks without changing saved numbers or population. Display limits retain complete results. Actual data/method changes alter the appropriate identity.

Rendering: no broken links, duplicate anchors, stale captions or uncontrolled side effects; preserve distinct default opening structures, readable precision, header/navigation and mobile layouts.

Integrity: effective configuration matches embedded/sidecar provenance; reject missing/extra/unsafe artifacts and false/rehashed results through independent replay where supported. Preserve atomic no-replace publication.

Interaction: test actual keyboard/pointer controls, focus, table operations, offline claims and author/data-label sanitization. Do not call unit tests a completed browser/accessibility review.

Baseline: frozen ref remains the exact accepted SHA, no evidence overwritten, old workflow independently available.

## 21. Definition of done for version one

Three defaults use registered blocks and parameterized presets. A steward can save/reopen/reproduce custom content/order/options. Only implemented eligible blocks are active. Analysis/display separation, protected context, full effective provenance and safe publication are enforced. Documentation, clean regression and browser acceptance cover both default and custom reports. Unsupported inferential/privacy/clinical capabilities are stated honestly.

## 22. Open decisions after inspection

Assign product/scientific reviewers; settle initial mandatory context and supported blocks; choose initial CLI-first versus minimal UI scope; integrate with the existing interface; define permitted placement/disclosure; attribution review; supported formats; custom-only versus default-plus-custom output; schema compatibility/migration; and historical evidence/source access.

The first functional change should be selected from actual source inspection, not from assumptions about functions or result keys. This branch starts with documentation and a clean boundary, not a speculative large renderer replacement.
