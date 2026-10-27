# Combined donor integration plan

Status: authoritative forward plan; implementation pending. Prepared from accepted baseline `fe5fb8ed1ab5f4bf94cc10da1637b82b539692ec`. Working branch: `integration/steward-ready-v1`. This plan supersedes the uncommitted design-only M4 / separate CSV M5 / surveillance M6 proposal. No release or deployment is authorised.

## 1. Product outcome

Deliver one local reporting product: choose IDD or CSV/TSV, choose or create a stakeholder profile, inspect the interpreted input, choose supported sections and graphs, preview, save an executable request, and render interactive reports with matching data, methods, limitations and provenance. A saved batch request generates at least three stakeholder reports from one shared report source with one command. A fourth stakeholder composed of existing capabilities requires configuration, not source edits.

M4 delivers the combined product. M5 extends it with validated surveillance analyses. Small PRs are delivery increments, not permission to declare isolated features the completed integration.

## 2. Sources and disposition

| Source | Pinned identity | Reuse/adapt |
|---|---|---|
| Accepted integration | `fe5fb8ed1ab5f4bf94cc10da1637b82b539692ec` | IDD calculations, blocking QC, snapshots, lineage, shared-template contract, provenance, cache behaviour, verification and regression tests |
| v2 repair donor | `6cbe222eb7edefe353d7370168c974c43b1a5350` | `src/ui.py`, `scripts/health_pipeline/ingest_tabular.py`, `generic_report.py`, relevant rendering fixes and tests |
| Nisha design donor | `a1cba89bbb5e37b20b48e2df8b334aa4ba7d250b` | `reports/researcher.qmd`, `reports/public_health.qmd`, shared assets and useful generic-report presentation |

Do not wholesale merge donor deletions, dependency files or alternative renderers. Maintain a donor manifest identifying each source path/commit, destination, reuse/adapt/reject decision, attribution, reason and validating test. Preserve existing licences and contributor attribution. Rejection requires an explicit reason, not silent omission.

## 3. Work packages and dependencies

### WP0: donor compatibility baseline

Run donor IDD, CSV snapshot, CSV time-series and malformed-input examples in isolated output directories. Inventory dependencies, runtime differences, test coverage and known defects. Compare actual behaviour with documentation. Produce the donor manifest and a field-by-field compatibility matrix. Source inspection is not runtime acceptance. Gate: no component chosen for porting without identified inputs, outputs, tests and dependency effects.

### WP1: shared contracts and registries

Specify versioned input, request, profile, analysis-bundle and component contracts before porting execution. Separate dataset semantics from stakeholder communication. Establish validated profile discovery and explicit publication selection. Define capability declarations and unavailable states. Gate: equivalent UI/CLI requests resolve to the same effective settings; unknown fields, unsafe references and unsupported component bindings fail clearly. See [contracts](integration-contracts.md).

### WP2: unify local execution and run lifecycle

Adapt v2's source-selection journey and current submission/cache safeguards into one local route. Use collision-resistant run IDs, safe paths, isolated inputs, explicit job states, bounded resource use and atomic publication of successful outputs. Do not expose the Docker socket to the browser container merely to preserve the host adapter. Prefer the report-capable container as the local execution environment; prove UI/report dependency compatibility or document a separately isolated worker. Choose the smallest tested topology in an architecture decision. Retain the accepted host adapter until the replacement passes parity tests, then deprecate it explicitly. Gate: failed or interrupted runs cannot appear successful, overwrite a prior accepted run or expose unredacted errors in the UI.

### WP3: integrate existing CSV/TSV implementation

Reuse the v2 importer and descriptive-report logic, correcting identified seams. The importer currently validates/interprets data but the renderer rereads the raw file; replace this with one recorded interpretation consumed by analysis. Support snapshot and time-series examples without requiring a hand-written mapping file for unambiguous inputs. Show inferred roles and aggregation; require correction/confirmation for ambiguity and allow a saved mapping. Do not silently sum rates, treat numeric IDs as measures, or interpret calendar years as epoch timestamps. Keep uploads separate from committed IDD data. Gate: report values independently match fixture calculations, and saved input plus interpretation reproduces the result.

### WP4: integrate Nisha's presentation

Build reusable cards, tables, charts, layout and narrative components behind the shared report entry point. Map every donor element to a verified bundle field or defer it to M5 with a reason. Preserve distinct researcher, institutional and public purposes; the public-health-official donor is not automatically a public-facing design. Use neutral descriptions until surveillance semantics are validated. No epidemiological calculation belongs in the renderer. Gate: unchanged IDD analytical settings preserve accepted values; all supported data routes render through the shared source, with honest unavailable sections and no duplicate audience engines.

### WP5: steward report builder and graph library

Expose source preview, role correction, profile cloning, section ordering, graph selection, filters, dynamic wording, preview and saved recipes through the unified UI. Discover profiles and component choices from registries, not duplicated allowlists. Provide starter recipes and contextual explanations rather than requiring JSON editing for routine work. Keep machine-readable configuration editable and portable. Gate: a steward creates an additional stakeholder from existing components without editing pipeline, template, adapter or UI code. See [workspace specification](steward-workspace.md).

### WP6: provenance, caching and exports

Carry the source digest, interpretation, transformations, quality findings, effective profile, visual specification, analytical method, template and environment identity through the full run. Reuse cache entries only after manifest validation; distinguish analytical cache identity from render identity. Export complete reports, methods, permitted data, request, mapping, environment references and verification instructions. Gate: changed input/mapping/profile/graph options invalidate the appropriate cache layer, and another checkout can replay the saved request.

### WP7: combined M4 acceptance

Run all routes as one product, not separate demonstrations. Complete fixture, security, browser, HTML/PDF, accessibility and reproducibility checks. Test one-command three-audience generation for IDD and a general table, plus a new configured stakeholder. Record exact commits, logs and limitations. Only then retire redundant supported UI/rendering paths. No broad test deletion to make the merge pass.

## 4. Sequencing

WP0 -> WP1 -> WP2/WP3. WP4 can begin after WP1 using accepted fixture bundles. WP5 depends on the registry and execution boundaries. WP6 is developed alongside WP2-WP5, not bolted on afterward. WP7 closes M4. Each PR lists dependencies, source/donor identities, changed contracts, migration/backout steps and evidence. Keep the standard IDD route runnable throughout; temporary donor adapters must be labelled and removed or explicitly retained before acceptance.

## 5. M5: surveillance extension

Reuse and validate donor surveillance helpers rather than rewrite by default. Add canton maps, seasonal windows and status classification through M4's capability/component interfaces. Specify geographic identifiers, boundary assets/licences, denominators, units, periods, completeness rules, comparison-year selection, publisher versus computed baselines, inclusion of current observations, small-number handling, threshold versions and unknown/insufficient-data states. Add related recent-period and year-to-date analyses only with agreed definitions. Generic CSV input is eligible only when the requisite semantic contract is satisfied. No unavailable baseline may become normal/low; descriptive statuses must not imply clinical risk or significance.

## 6. Preservation and completion

The accepted baseline is retained, not relabelled as completion of the combined scope. Main, original release references and existing version tags are untouched. M4/M5 capabilities are planned until their gates pass. Final product acceptance requires transferable artifacts and independent replay, not just local file hashes. A release remains a separate maintainer decision. Historical records stay available; competing conversational milestone sequences are superseded by this document.
