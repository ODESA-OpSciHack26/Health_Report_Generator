# Decision: inspectable analytical blocks

Status: approved design direction; implementation pending. Prepared 28 October 2026. Integration home: `integration/steward-ready-v1`; preparation branch: `feature/b0-plan-b-readiness`, rooted at `eb392370852992b8cd5794ea90548c36ebae47f7`. Frozen Track A remains `c72bd54f69300b8e79bb967c201529d48625ae45`.

## Decision and reader experience

Every analytical graph, table or card carries a common evidence inspector immediately beside or below the result. Independent disclosures expose data used, calculation/assumptions, analysis code, rendering code and reproduction details. The result remains primary; scope, units and material caveats stay visible. A report-level expand/collapse control may complement, not replace, per-block controls.

The inspector follows the instance when moved, duplicated or placed in an appendix. Wide layouts may use an adjacent panel; narrow layouts expand underneath. Controls require meaningful labels, keyboard operation, visible focus, expanded state and unique identities. Opening evidence reads saved artifacts, never reruns analysis or fetches a moving remote source.

This is part of the block contract from B1, not global methods text or Quarto code folding alone. Committing this decision does not implement it.

## Evidence layers

| Layer | Required content |
|---|---|
| Source | Captured content identity/version, attribution and permitted reference |
| Interpretation | Confirmed mapping, parsing/frequency/units/missingness policies |
| Analysis input | Exact relevant typed rows/columns and stable original source-record identities |
| Selection/eligibility | Actual scope/predicates, counts, relevant exclusions and reasons |
| Method | Method/version, resolved invocation parameters, definitions and assumptions |
| Results | Full-precision saved outputs, availability and lineage |
| Plotted data | Exact selected result rows/coordinates, bins or series supplied to rendering |
| Implementation | Retained analysis/render source, helpers and dependency identities |
| Reproduction | Compatible environment, entry point, identity checks and permitted downloads |

An aggregated plotted table is not a substitute for contributing observations. Bounded previews state total rows and link to permitted complete artifacts or explain withholding. Large inputs use scalable source-record sets/references, not a complete data copy in every block.

## Evidence contract

B1 fixes final schemas/field names. Each block instance references its registered type/version, analytical scope/result, input/plotted-data identities, source records, method/parameters, implementation/environment references, initial disclosures and distribution policy. Store shared artifacts once and reference them from several blocks. Save original author settings and fully resolved effective settings.

Generated evidence must match actual data flow. Record effective method/invocation metadata at the execution boundary. A generated replay recipe is labelled as a recipe, not a captured trace. Do not claim instrumentation before it exists. Hashes support content integrity, not source authenticity or proof of every interpreter/library binary loaded.

## Code source

Analysis code and rendering code are separate panels: current numerical descriptives are Python and presentation is R. Showing only a Quarto wrapper or R plotting call is insufficient. Show useful implementation excerpts with retained complete project files, revision/content identity, relevant helpers and resolved parameters. Third-party package versions/locks and reproducibility limits remain explicit; do not claim all dependency source is embedded.

Retain actual versioned implementation, not illustrative generated code. Source capture uses an explicit reviewed list; never copy arbitrary repository files, environment variables, tokens or private paths. Escape code/labels as content; settings cannot execute uploaded Python/R/JavaScript/Quarto fragments.

## Calculation panel

Generate explanations from the method contract and saved results. For reference 900 and latest 1,048: absolute difference is 148; percentage is 100 times (1,048 minus 900) divided by 900, approximately 16.4 percent. Show real periods, units, scope, contributors, missingness and display-versus-full precision.

The current comparison requires one non-missing observation at each requested period. A non-positive baseline makes percentage unavailable while an otherwise eligible absolute difference can remain available. Repeated/missing inputs remain explicit; unavailable is not zero. Current rejection of an absent requested period is preserved unless a versioned change is approved. Descriptive change is not significance, cause, severity or an outbreak.

Statistics additionally show valid n and conventions such as SD/quantiles. Future inference needs separately reviewed assumptions, diagnostics, effect and uncertainty contracts; this decision introduces no new test.

## Identity and interaction

Reordering preserves instance/evidence links. Duplication creates a new display identity and can reuse the same analysis. A display subset exposes its exact plotted rows without changing the analytical population. Table sorting/search is view-only. A real analytical change creates a new analysis identity. Record initial visual settings separately from ephemeral reader interactions; exporting changed settings is explicit. Removing a view does not delete evidence still used elsewhere.

Initial custom analytical scope is report-global. Block-local analytical populations require separate identities/contracts later; they are not ordinary display filters.

## Privacy and artifact policy

Reader expansion, steward initial-state settings and distribution permission are different controls. Collapsed HTML still contains bytes. Restricted rows/source literals must be absent from public HTML, script data, downloads, manifests and linked source artifacts, not merely hidden. No public link may traverse into private retained evidence.

Keep the fuller private run under its actual policy; a restricted export has its own manifest, omission reasons and replay limits. Unexpected missing/inconsistent required evidence blocks publication. An intentional withheld state is recorded honestly, not presented as a complete public audit. No private-data security/de-identification claim is implied.

## Step-by-step implementation

| Slice | Placement | Deliverable and gate |
|---|---|---|
| E0 | B0 | Align this decision with plan/contracts/workspace/acceptance; no runtime change |
| E1 | B1 | Strict component/evidence/reference/disclosure schemas and deterministic resolution; reject unknown fields, unsafe paths, duplicate IDs and incompatible bindings |
| E2 | Early B2 | Capture inputs, effective method/parameters, saved outputs and approved source for existing reference comparison; numerical parity |
| E3 | B2 | Reusable accessible inspector beside that graph; real data, formula, source and reproduction panels; runtime plus browser review |
| E4 | B2-B3 | Extend to descriptive tables/cards, trends, histogram bins and CSV interpretations; IDD adapter retains domain lineage |
| E5 | B4 | Version manifests and independent verification together; check exact source/input/result/plotted/effective settings and reject tampering |
| E6 | B5-B6 | Composer disclosure controls, deduplicated artifacts, bounded previews, caching and actual restricted-export omission |
| E7 | B7 | IDD/general inputs, three presets and new custom composition; end-to-end replay and actual interaction review |

The first vertical slice traces captured bytes -> prepared relevant source records -> existing comparison -> full-precision result -> plotted subset -> graph -> retained analysis/render implementations. It does not calculate replacement statistics in R or JavaScript. Pass verified saved results to presentation/provenance assembly; independent recalculation remains an intentional verifier operation.

## Required tests and completion

Verify that displayed code matches retained source; parameters match recorded method execution/configuration; relevant rows and exclusions match calculation; plotted data matches visible series/bins; reorder/duplicate preserves links/unique DOM IDs; rounding preserves numbers; missing/non-positive/repeated cases remain correct; expansion performs no computation/network fetch; formulas agree with saved values; false/rehashed evidence is rejected; restricted bytes are really omitted; and historical schemas retain explicit compatible verification.

Pure-Python contracts run in fast; actual R execution runs in the locked report runtime. Human review covers keyboard/focus/state, narrow layouts, tables, downloads and code readability, with candidate and artifact identity recorded. Unit tests do not constitute accessibility/scientific acceptance.

Done means every available initial analytical block has truthful data/method/implementation bindings, independently operable disclosures, safe distribution, matching provenance and supported reproduction. Shared evidence supports several audiences without duplicate calculation. Frozen references, releases and deployment are outside this change.
