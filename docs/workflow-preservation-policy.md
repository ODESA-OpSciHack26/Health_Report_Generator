# Mandatory data-workflow preservation policy

Status: normative change and review policy for Track B; not a claim of implemented enforcement or passing tests. Applies throughout B0-B7 and subsequent maintenance.

## Governing rule

Every change MUST preserve the supported end-to-end data workflow, its scientific semantics and its reproduction path. Preservation means maintaining traceable, independently verifiable behavior, not freezing all implementation forever. An intentional change requires explicit approval, versioned contracts, migration and rollback evidence before the affected route can be retired. A documentation statement alone cannot establish runtime preservation.

Read this policy with the [technical workflow](data-workflow.md), [scientific policy](scientific-policy.md), [contracts](integration-contracts.md), [acceptance](integration-acceptance.md) and [conflict dispositions](b0-conflict-dispositions.md). Requirements apply to each relevant PR, not only final acceptance.

## Required invariants

1. Capture and retain original input bytes and metadata under their actual distribution policy. Record content identity, source attribution, retrieval/version information and original record identity. Never hash one read and analyze a later changed file. Do not delete/deduplicate by filename alone.
2. Keep acquisition separate from regeneration. Reproduction uses the recorded captured inputs; refreshes are explicit new inputs, not hidden network substitutions.
3. Preserve the route-specific preparation, interpretation, selection and blocking quality gates. Target generic interpretation must be confirmed before verified publication. Record effective mappings, conversions, units, missingness, predicates, exclusions and before/after counts. Labels and period normalization are not filters.
4. Preserve numerical/scientific semantics: missing is not zero; unavailable is not normal or low risk; identifiers are not measures; rates and percentages are not silently summed; repeated observations are not silently aggregated. Do not invent dates, denominators, baselines or clinical conclusions.
5. Calculate scientific results in the analysis layer and pass saved verified results to presentation. Preserve full precision and lineage. Reordering, rounding, disclosure and display subsets MUST NOT change analytical population or numerical-result identity. Composite serialized files may change when display metadata changes; do not promise whole-file invariance.
6. Preserve shared-source, parameterised reporting and the established three-audience command. Keep IDD-specific and general-table scientific logic distinct. A configured stakeholder uses trusted implemented capabilities, not executable user expressions.
7. Preserve original and effective requests, source/interpretation/selection, method/result, code/environment and presentation identities, embedded/sidecar agreement, render timestamps and exact version-compatible verification. Extend generation and independent verification together; rehashing a false result is not validation.
8. Validate cache entries and relevant identities; retain original render time separately from retrieval/submission time. Never treat an HTML file's existence as a valid cache entry.
9. Preserve existing accepted outputs during development and failed runs. New unified publication MUST use isolated work and complete no-replace publication. The legacy custom CLI currently replaces its --out destination; use a disposable new destination or preserve the earlier output first. Do not claim that legacy behavior has already migrated.
10. Keep material scope, units, caveats, provenance and evidence access in every audience. Public artifacts MUST actually omit restricted bytes, including scripts/downloads/source literals; collapsed sections are not access control. Record permitted omissions and replay limits.
11. Preserve frozen Track A at c72bd54f69300b8e79bb967c201529d48625ae45, original release references, attribution, licences and historical evidence identities. Historical passes do not validate a new candidate.

## Required workflow-preservation section in every PR

- Change class and affected routes/stages: documentation, acquisition, interpretation, selection, analysis, presentation, cache, publication, export or environment.
- Exact base and candidate identities; retained input/config/environment references; commands, exits and applicable CI identities.
- For behavior changes: pre/post expected results and lineage, hand-calculated fixtures where relevant, unchanged-scope numerical parity, exact verification and saved-request replay. Explain intentional differences rather than weakening tests.
- Compatibility with existing tabular requests v1/v2, standard IDD outputs and supported local/connector paths, as applicable.
- Failure/interruption/tamper and cache invalidation checks for affected boundaries; actual UI/browser review when interactions change.
- Migration/backout and preservation of previous accepted inputs/results; explicit unavailable/deferred capabilities and reviewer decisions.

Documentation-only PRs MUST state that runtime code, data, calculations and dependencies are unchanged, check changed links/status claims and report unrun tests honestly. This does not waive runtime tests for later implementation PRs.

## Change and acceptance gates

An affected workflow change MUST NOT be accepted with unexplained numerical drift, broken replay, lost source records, weakened verification, undisclosed data replacement or leaked restricted bytes. Approve intentional analytical/schema changes explicitly with versioning, old-request compatibility or migration, expected fixtures, scientific review where relevant and rollback. Retire an old supported route only after its replacement passes applicable parity gates.

B1 fixes concrete strict schemas and tests; this policy does not release a schema. B2 starts with the existing reference-change comparison and its full evidence chain. B3 extensions to multiple measures/group candidates/ungrouped/count modes require explicit contracts and fixtures; extra formats/locales remain separately gated. B6 obligations apply throughout B1-B5. B7 requires combined clean replay and runtime/browser evidence. Generic HTML support does not imply PDF/static parity; implement it or explicitly approve deferral.

Enforcement initially relies on PR review and applicable existing tests. New machine-enforced checks must be implemented and tested separately; do not describe this document as a CI gate already installed. Release, deployment, tags, branch protection and data distribution remain separate maintainer decisions.
