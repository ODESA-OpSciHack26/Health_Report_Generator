# Combined integration acceptance and delivery

Status: planned gates, not passing results. Governing [plan](integration-plan.md); [workspace](steward-workspace.md); [contracts](integration-contracts.md).

## Baseline evidence retained

The accepted candidate is `fe5fb8ed1ab5f4bf94cc10da1637b82b539692ec`. The maintainer supplied a clean fresh-clone capture beginning 2026-10-27T02:36:53Z: eleven stages passed, 18 selected artifacts hashed, analytical mismatches none, six sidecars and three packaged templates matched. That clone's scan reported 114 commits/no leaks; earlier original-checkout scans have different scope. The user reported all three audiences, navigation/downloads and PDFs visually passed. This is baseline-only maintainer/user-reported evidence, not independent scientific validation, an attached artifact bundle, or acceptance of redesigned reports. Do not overwrite old identities or files.

## Required test matrix

| Layer | M4 gate |
|---|---|
| Donor reconnaissance | Representative donor runs, dependency comparison and reuse/adapt/reject manifest |
| Input | Valid IDD, CSV snapshot/time series, malformed/ragged/empty files, duplicate headers, ambiguous dates, numeric IDs, leading zeros, missing and mixed-unit cases |
| Interpretation | UI/CLI agree; confirmed mapping is consumed exactly once; independent expected summaries; no invented observation date or inappropriate aggregation |
| Stakeholder | Add a genuinely new profile without runtime edits; discovery, safe identifiers, invalid profiles, precedence, migrations and explicit batch inclusion |
| Components | Binding/units/capability checks, unknown/unavailable behaviour, supported chart families, escaped labels and safe static fallback |
| Domain regression | Accepted IDD values unchanged for unchanged analytical parameters; explain any intentional contract/data change separately |
| Execution | Isolation, path traversal/symlinks, filename handling, collisions, limits, interrupted jobs, atomic publication, safe errors and concurrency |
| Cache | Identical request hit; changed data/mapping/filter/profile/chart/template invalidation; tampered/missing entry rejection; original render time retained |
| Provenance | Embedded equals sidecar; source/mapping/effective parameters/methods/template/environment/scope verified, privacy-safe exports |
| End-to-end | IDD and generic CSV -> three profiles from the shared source, CLI batch and actual local browser; no GitHub token needed |
| Presentation | Distinct audience purposes; HTML navigation, controls and downloads; PDF/static behaviour; keyboard access, contrast, labels and non-colour cues |
| Reproduction | Another checkout replays saved input/mapping/request; complete export manifest, source/environment instructions and missing-private-data limits |

Carry useful donor regression tests forward and add tests for gaps. Do not satisfy a gate by deleting incompatible tests without an explicit superseded-contract decision. Tests may not equate three different titles with three adequate stakeholder reports.

## Evidence package per PR and milestone

Record candidate/base/donor commits; initial/final worktree state; commands and exits; package/runtime/image identities; inputs, configuration and output hashes; fixture expectations; test logs; browser actions; review scope; unresolved issues and limitations. Distinguish pre-commit, committed feature, merge candidate and released identities. Evidence recording is not a re-execution of tests. Do not duplicate anonymous 64-hex strings with misleading credential labels; review scanner matches by recomputing documented digests and use only justified exact exceptions.

A PR includes path-level donor decisions, changed contracts, migration/backout instructions, tests and screenshots or structured visual findings where appropriate. Local previews and cached outputs are never silently labelled a fresh render. CI must check documentation links, schemas, lint, analysis and container/end-to-end behaviour. Add the new route to output/release verification rather than bypassing verification for CSV.

## Human review

Record reviewer, time, candidate, dataset/profile IDs, documents tested, devices/formats, findings and pass/issue/not-reviewed status. Scientific review covers interpretation/aggregation and uncertainty separately from visual usability. A partial review cannot become a blanket pass. User text containing a general pass is recorded as supplied, with its actual candidate and scope.

## M5 additional gates

Independently checked maps/geographic joins and denominators; frequency/period alignment; baseline completeness and current-period inclusion; unknown states; small-number behaviour; threshold definitions/versioning; partial latest periods; zero/missing denominators; comparable source streams; and no unreviewed clinical-risk or significance claims. Compare donor helper outputs on fixtures before retaining them.

## Completion and publication

M4 closes only after source selection, CSV integration, redesigned reports, configuration-only stakeholder creation and common provenance/replay work together. M5 closes only after the agreed surveillance methods and displays pass their gates. Final acceptance includes transferable source/environment/input/report evidence and explicit private-data exclusions. Do not start an endless evidence-only PR cycle: one milestone record identifies the tested implementation, and a small evidence-only follow-up does not relabel that identity or require scientific recalculation by default.

No plan approval authorises promotion to main, moving release references, replacing existing tags, deploying a server or uploading user data. Maintainer approval and the [release checklist](release-checklist.md) govern publication separately.
