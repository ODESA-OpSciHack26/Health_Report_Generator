# Track B integrated acceptance and delivery

Status: planned gates, not passing results. Updated 28 October 2026. Governed by [plan](integration-plan.md), [contracts](integration-contracts.md), [workspace](steward-workspace.md) and [inspectable-block decision](decisions/inspectable-blocks.md).

## Preserve evidence identities

Historical baseline `fe5fb8ed1ab5f4bf94cc10da1637b82b539692ec` retains the maintainer-reported fresh-checkout capture beginning 2026-10-27T02:36:53Z: eleven stages, 18 selected artifact hashes, unchanged analyses, six sidecars and three packaged templates. Its scan scope was 114 commits/no leaks. User-reported browser/PDF acceptance belongs to that baseline. Preserve original records and limitations.

Track A is frozen at `c72bd54f69300b8e79bb967c201529d48625ae45`. User-supplied evidence reported 353 tests, clean-release/canonical checks, verified real-data reports and browser acceptance. Later PR #6 checked the CI correction. Neither earlier evidence nor this documentation commit is a new execution against the current integration revision. A source branch is not an archive of ignored inputs, reports or logs.

## Required matrix

| Layer | Gate |
|---|---|
| Input | IDD and supported CSV snapshot/time-series; malformed/ragged/empty/duplicate headers; ambiguous roles, IDs/leading zeros, missingness, units and enforced limits |
| Interpretation/selection | Confirmed mapping consumed from captured bytes; UI/CLI agree; no invented dates/aggregation; stable original row identity after selection |
| Components/profiles | Strict schema/version/options; safe unique IDs; capability/format bindings; new configured stakeholder; discovery separate from batch |
| Analysis | Hand-calculated fixture results and accepted IDD parity for unchanged analytical scope; explicit migration for intentional changes |
| Inspector | Exact relevant inputs/results/plotted data; truthful method/parameters/source; no recomputation on expansion; stable reorder/duplicate links |
| Execution | Safe paths, symlinks, limits, isolation, interrupted runs, concurrency, safe errors and complete no-replace publication |
| Cache | Correct layer invalidation, manifest validation, tamper rejection and original render time retained |
| Provenance | Original/effective request, interpretation, scope, methods, component/code/environment identities, embedded/sidecar agreement |
| Disclosure | Restricted bytes absent from public HTML/scripts/downloads/source; own export manifest and replay limitations |
| Presentation | Distinct purposes; readable rounding; navigation/tables/downloads; keyboard expansion/focus/state, narrow layout, non-colour cues and accessible descriptions |
| Reproduction | Another clean compatible checkout replays approved retained inputs/recipe without undeclared network or private-data assumptions |
| End-to-end | One-command three defaults for IDD, general snapshot and general time-series; genuinely new stakeholder; actual local UI and CLI |

Initial composer delivery is HTML-first. Preserve canonical PDF/apps; test generic static/PDF representations or explicitly approve deferral before claiming combined-format completion. Do not silently remove existing acceptance obligations.

## First vertical slice

Use the existing reference-change comparison, not a new statistical test. Check ordinary positive baseline; non-positive baseline with unavailable percent; missing/repeated observations; current rejection of absent requested periods; malicious labels; display subset; reorder/duplicate. Trace captured source -> relevant typed records -> existing method -> full-precision result -> plotted rows -> chart -> retained analysis/render source.

Require tamper tests for false/rehashed inputs, results, method parameters, source snapshots and evidence references. Exact artifact verification must grow with a versioned format, not become a wildcard. Historical verification uses the matching old source/schema.

## CI and human review

Pure-Python contracts run in fast. Actual R presentation tests run with the complete suite in the locked report runtime; the Python-only job must not accidentally depend on runner R packages. Unit tests/source inspection are not browser acceptance. Record reviewer, candidate, dataset/profile, documents, browser/device/format, actions and pass/issue/not-reviewed scope. Scientific interpretation review is distinct from usability and is not inferred from a blanket visual pass.

Each PR records dependencies, changed contracts, donor decisions when applicable, migration/backout, commands/exits and applicable tests. Preserve licences and original evidence. Do not delete tests just to make integration pass; superseded contracts need explicit decisions.

## B0 and completion

B0 closes only when active guidance agrees on branch, scope, statuses and inspector requirements, links are valid and remaining conflicts have explicit disposition. The initial alignment commit alone does not close B0.

Track B closes after source choice, interpretation, composition, publication, inspectors and replay work together. Surveillance has separate geographic/baseline/completeness/threshold/unknown-state gates. Release, deployment, branch protection, tags and data distribution remain separate maintainer decisions under the release checklist. Avoid endless evidence-only cycles: record the actual tested implementation once and never relabel older runs as new executions.
