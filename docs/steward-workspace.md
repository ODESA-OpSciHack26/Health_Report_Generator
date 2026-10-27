# Steward workspace, report vault and authoring experience

Status: target specification for M4, not shipped features. The word vault means a portable reporting workspace, not an encrypted secret store or an Obsidian requirement. The default interface is local and intended for a trusted single steward. See [plan](integration-plan.md) and [contracts](integration-contracts.md).

## 1. Steward journey

1. Create/open a workspace. Show tool/schema versions, storage location and local-only scope. Never initialise over an existing workspace without explicit confirmation.
2. Choose committed IDD data or upload CSV/TSV. Display source attribution, source identity, preview, dimensions, missingness and QC. Do not imply that uploaded data are FOPH data.
3. Review the interpretation. Suggest time, category, measure, unit and identifier roles. Distinguish calendar years from timestamps, rates from counts and category codes from values. Use clear explanations and editable choices; save the effective interpretation.
4. Choose a stakeholder starter or clone a profile. Ask what decision/question the report supports, who will read it, the required detail and the intended distribution. Avoid audience labels as the sole design input.
5. Assemble sections from a component catalogue. Reorder, hide optional sections, choose graph variants, configure bindings and add editorial notes. Mandatory source, methods, uncertainty and limitations information cannot be suppressed.
6. Preview validation and a low-cost rendering. Clearly label previews and sampled data; a preview is not a verified final report. Explain disabled components and how to supply missing prerequisites.
7. Render and verify. Show queued/running/failed/succeeded states, progress, safe errors and local diagnostic references. A previously successful report remains accessible after a failed new run.
8. Save the request and export a report package. Repeat the saved recipe in the UI or through the same CLI/batch mechanism. Cache reuse displays the original render time and the new retrieval/submission time separately.

## 2. Proposed vault layout

This is the target workspace layout, not a request to move current production directories immediately. Implement migration/adapter steps in small reversible changes.

```text
report-vault/
  workspace.json                 # schema version, defaults, project identity
  catalog/
    datasets/*.json              # source identities, capabilities, terms
    stakeholders/*.json          # validated communication profiles
    mappings/*.json              # saved input interpretations
    recipes/*.json               # replayable single-report requests
    batches/*.json               # ordered report sets and publication selection
    charts/*.json                # named configurations of trusted chart types
    themes/*.json                # supported design tokens, not arbitrary scripts
  inputs/
    originals/<content-id>/      # immutable uploaded bytes; private by default
    snapshots/<snapshot-id>/     # retained analysis inputs/manifests
  work/<run-id>/                 # incomplete intermediates; never published
  runs/<run-id>/
    request.json                 # resolved request and selected versions
    interpretation.json
    qc.json
    analysis/                    # verified tables and lineage
    reports/<stakeholder-id>/    # complete HTML/PDF/assets/data/provenance
    manifest.json
    logs/                        # local diagnostics; access controlled
  cache/analysis/                # disposable verified computations
  cache/render/                  # disposable verified presentation results
  reviews/<run-id>/              # visual/scientific review, reviewer, scope/time
  exports/<export-id>/           # explicitly approved transferable bundles
```

The repository retains application code, schemas, component implementations, default profiles, public test fixtures and documentation. A vault holds steward-owned requests/data/results and may live outside the repository. Runtime originals, private profiles, logs and exports are not automatically committed or synchronised. `.gitignore` is not access control. Profile recipes should use portable dataset IDs/relative references; external paths require explicit local binding and must not escape the workspace through symlinks or traversal.

## 3. What a steward can change without coding

- Clone/name a profile; choose purpose, language/detail, section order and labels.
- Select supported filters, baselines and time ranges when the data contract permits them.
- Choose among registered graph types and bind eligible columns/verified tables.
- Set safe titles, explanatory text, units, rounding, category ordering, axes and reference annotations.
- Create a batch for recurring reporting and select its audience profiles.
- Save a chart configuration for reuse across reports.

No-code means combinations of existing capabilities. A new scientific measure or executable chart implementation remains developer work. Do not allow uploaded Python/R/JavaScript, arbitrary Quarto fragments, raw SQL or executable expressions in profiles. Editorial text is escaped/sanitised and is distinct from computed findings.

## 4. Graph catalogue and guidance

| Registered family | Suitable request | Mandatory checks |
|---|---|---|
| Line/point trend | Comparable measure over ordered time | frequency, gaps, units, group identities; do not join incompatible series |
| Bar/dot ranking | Measure by category | aggregation, sort, negative values, denominators; disclose top-N exclusions |
| Histogram | Distribution of observations | numeric role, bin policy, sample size, missingness |
| Box plot | Grouped distributions | observation-level data, sample sizes, small groups; no invented uncertainty |
| Scatter | Relationship between two measures | row alignment, units, missingness; no causal wording |
| Table/KPI card | Verified value/summary | value definition, period, unit, comparison scope, missing states |
| Heatmap | Valid time/category matrix | aggregation, comparability, missing-cell legend, accessible fallback |
| Map and surveillance band/status | M5 capability | disabled until validated geographic/baseline contracts exist |

M4 initially implements only the families needed by supported donor examples and the acceptance set; record shipped versus deferred catalogue entries explicitly. Avoid pie/stacked/dual-axis defaults unless their semantics and accessibility have been reviewed. A type recommendation is advisory, not an invisible statistical decision. If no safe recommendation exists, provide a table and explanation.

A steward adds a named graph by configuring an existing trusted family. A developer adds a new family through a versioned registration including required inputs/capabilities, option schema, renderer, static fallback, provenance fields, accessibility behaviour and fixture tests. Adding a family must not require another audience-specific report template.

## 5. Helpful builder features and priorities

M4 required: clone-profile wizard; schema-backed forms; source preview; inferred-role review; graph compatibility explanations; section ordering; dynamic titles/questions; field-level validation; save/replay recipe; batch generation; cache explanation; complete export; visible limitations; profile discovery in UI and CLI.

M4 usability improvements when core gates are secure: compare draft with previous accepted report; show exactly which data/settings/design fields changed; saved favourites; restore defaults; undo unsaved edits; reusable chart presets; copy a successful run as a new draft; concise guided mode plus advanced configuration view. None may bypass QC or conceal an inferred choice.

Later optional enhancements: scheduled local batches, translation workflows, collaboration/approval roles and remote deployment. They are not promised as M4 features. Scheduling must preserve a frozen request and show source refresh versus report regeneration separately.

## 6. Privacy, review and sharing

Default upload/export policy is private local use. Enforce configurable upload/row/column/resource limits, safe filenames, path containment, bounded previews, HTML escaping and safe download handling. Warn about potential identifiers and health information; do not claim automatic detection anonymises data. Raw-data and lineage downloads may require de-identification or explicit exclusion from public exports. Preserve the fuller private run when a redacted export is created; give the export its own manifest and reproducibility limitations.

Do not silently include absolute home paths, environment variables, tokens, diagnostic dumps or raw uploads in shareable provenance. Record portable identities and controlled references instead. Retention/deletion is explicit: originals and accepted runs are not cache; cache deletion must not delete source data. Provide disk usage and export previews, and require confirmation for destructive cleanup. A vault is not encrypted unless encryption is separately implemented and documented.

## 7. Extensibility demonstration

Acceptance exercise: a steward clones a starter into a new stakeholder ID, changes purpose/wording, selects sections, switches one supported graph family, changes a permitted filter, saves a recipe, and generates it through both UI and CLI without changing runtime source. It appears in profile discovery but is not silently added to the standard published batch. Repeat with a generic CSV and record capability-dependent differences. Verify that removed/renamed profiles and upgraded schemas produce actionable migration errors rather than fallback to another audience.
