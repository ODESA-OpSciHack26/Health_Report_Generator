# M3 pre-commit validation evidence

M3 adds a host-side local Marimo form and an execution adapter that reuses
the Docker report service, custom request validation, shared template,
and custom-report cache. The existing GitHub connector is unchanged.

The local form offers four existing audience parameter sets and year
ranges within 2021–2025. It does not change the standard three-audience
release configuration or implement disease/canton selection.

## Results supplied by the maintainer

- Targeted Python tests: 25 passed.
- Full Python suite: 187 passed.
- Real browser request: health institution, 2023–2024, cache miss.
- Corrected title/question, effective parameters, filters, shared-template
  identity and embedded HTML provenance: passed.
- An earlier adapter repeat returned a cache hit with four identical
  selected output files; that repeat predates the wording correction.

The initial browser probe exposed a stale 2025-specific source question.
The adapter now regenerates title/question from selected years and
baseline settings without modifying source audience files.

## Evidence identity and limitations

`precommit-validation.json` records the base commit, working-tree source
hashes, corrected browser identity and hashes of local output files.

These checks exercised an uncommitted implementation based on the M2
merge. They must not be represented as a fresh capture of a later commit.
Local evidence hashes identify files but do not provide access to them.

The adapter lock coordinates adapter submissions only. The interface is
for a trusted local Linux/WSL session, not a public multi-user service.
Visual readability, lint, fresh committed-checkout validation, final
secret scanning and remote CI remain separate gates.

## Completed committed-checkout validation

Tested implementation: `cbc856ca9c5367d47b55e6836493bbe259af8e22`.

The standard-release capture began at
`2026-10-27T01:36:24Z` with a clean worktree.
All eleven stages passed, including lint, 187 Python tests, fresh standard
report generation, output/release verification, app smoke tests, no-op
rebuild, analytical baseline comparison, and shared-template identity.

Eighteen selected artifacts were hashed; analytical mismatches: none.
All six provenance sidecars and all three packaged templates matched the
shared source.

The committed adapter capture rendered public-health-expert requests for
2022–2024 and 2023–2024. The first request missed, its identical repeat hit
with four matching output files, and the changed request missed with a
different key. Non-request cache components matched. Commit, snapshot,
parameters, template identity and embedded provenance checks passed.

`container-summary.txt`, `template-identity.txt`, `adapter-capture.json`
and `committed-validation.json` preserve the completed capture records.
Supporting logs and outputs remain local; recorded hashes do not provide
access to those files.

The earlier pre-commit evidence remains historical and is not relabelled
as a committed browser run. The pending-gate statements above describe
the earlier evidence state; lint and committed-checkout captures are now
complete. Final secret scanning, remote CI, PR review, visual readability,
and independent scientific validation are not established by this record.
