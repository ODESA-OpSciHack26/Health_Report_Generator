# M4 WP0 donor assessment

Status: donor runtime investigation complete; integrated-product acceptance pending.

## Findings

- Pinned v2: 128 tests passed; all three CSV/render probe cases passed.
- Pinned Nisha: 62 tests passed; annual ISO-date rendering failed.
- Adapted Nisha: a numeric-dtype guard fixes the annual-date conversion.
- Four normalization cases passed in both tested environments.
- Snapshot and annual-ISO reports rendered for both Nisha audience views
  under Quarto 1.10.19 and the v2-based Quarto 1.3.353 environment.
- Malformed CSV rejection passed in both adapted trials.
- Original failure evidence is retained, not replaced by successful trials.

## Decision

Reuse components selectively. Preserve the canonical shared report source,
three default audiences, dependency ownership and existing verification gates.
Do not replace the environment or import separate audience report documents.

The first integration slice is isolated CSV validation and temporal
normalization with permanent regression tests. It must not change the default
workflow, introduce implicit upload activation or bypass scientific checks.

## Limitations and evidence

See [the machine-readable assessment](m4-wp0-donor-assessment.json) for
source commits, evidence hashes, adaptation details and acceptance gaps.

Supporting logs and probe outputs are local under `reproduced/`; they are
not made available to a fresh clone merely by recording their hashes.
Archive the reviewed evidence separately for handover.
