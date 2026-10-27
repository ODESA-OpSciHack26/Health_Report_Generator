# Steward-ready integration handover

## Recorded baseline and scope

This document starts from the M3 integration merge:
`c599ecda95fbaa462605949f8ff3668f11a5d0e4`.
It is a recorded baseline, not a claim that every later commit has been tested.

The working integration line is `integration/steward-ready-v1`.
The original `release/v1.0.0` reference remains separate.
This handover does not authorize promotion to `main`, a new tag or deployment.

## Work completed and evidence

| Work package | Purpose | Evidence |
|---|---|---|
| M0 | Preserve and reproduce the V1 baseline | [M0 record](evidence/m0/README.md) |
| M1 | Provenance and baseline guards | [M1 evidence](evidence/m1/) |
| M2 | Shared-template naming and dependency ownership | [M2 record](evidence/m2/README.md) |
| M3 | Local account-free audience form, backend reuse and date-consistent wording | [M3 record](evidence/m3/README.md) |

The M3 implementation tested by committed local captures is
`cbc856ca9c5367d47b55e6836493bbe259af8e22`.
Its final published feature head, including evidence and scanner review, is
`8b0a08b90bad800e4ad9731fd1d3221abbf018c5`.
These identities must not be replaced with the later integration merge SHA.

The maintainer-reported M3 standard capture passed eleven stages, including
lint, 187 Python tests, fresh rendering, release verification, app smoke tests,
no-op rebuild, analytical baseline comparison and template identity.
Analytical mismatches: none. Six sidecars and three packaged templates
matched the shared source.

The committed adapter capture passed miss/hit/changed-request checks,
parameter and provenance checks, and unchanged-cache-component comparisons.
A real browser check is recorded separately as pre-commit evidence.

At handover preparation, GitHub returned successful `fast`, `secrets`,
`container` and `full` check runs for PR #4. This is PR validation, not a
new execution against the integration merge commit.

The final local M3 feature-history scan covered 231 commits and reported
no leaks with seven reviewed exact-fingerprint cache-digest exceptions.
See [review record](evidence/m3/secret-scan-review.json).
Later commits require their own final scan.

## Supported reporting paths

- Standard release: three audience reports from the shared template; see
  [setup](../GETTING_STARTED.md) and [reproduction](reproduction.md).
- Custom request CLI: existing validated requests and content-addressed cache;
  see the [README](../README.md).
- [Local browser form](local-interface.md): trusted Linux/WSL host, four
  existing audience parameter sets, years within 2021–2025, CHFL geography,
  and existing 2019 comparison/index baselines.
- [GitHub connector](../CONNECTOR_SETUP.md): separate credential-backed
  artifact/Actions route, not required for local reports.

The local form does not add canton or disease selection. Its lock coordinates
adapter submissions only; it is not a public multi-user service.

## Evidence limits and remaining acceptance

Committed records identify local logs/reports by hashes; those files remain
local and git-ignored unless separately distributed. A complete handover must
include any artifacts needed by another person, not only their hashes.

Fresh outputs do not establish cold software caches, network isolation or
byte-identical rendered documents. Automated checks do not establish visual
readability or independent scientific validity. These must not be marked
complete without actual review.

Complete the [release checklist](release-checklist.md) for the chosen candidate.
Keep code, data snapshot, configurations, environment details and verified
outputs together, and record outstanding issues rather than hiding them.
