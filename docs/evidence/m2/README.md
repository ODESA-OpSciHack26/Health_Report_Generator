# M2: repository-contract cleanup

Starting integration commit:
`98828adeb610665a3548e4c58592a61c54fbe90b`.

## Scope

- Correct the current repository clone command and its executable shell syntax.
- Rename the shared template to `report_shared.qmd` without changing its bytes.
- Update current workflow, packaging, provenance, verification and test references.
- Reuse the producer's template-name constant for packaging and verification.
- Preserve historical M0/M1 evidence and saved outputs.
- Pin the two auxiliary Python setup jobs to Ubuntu 22.04, retaining Python
  3.11.6, action SHAs, branch refs and permissions.
- Document dependency ownership without regenerating or deleting locks.
- Test shared pipeline/overlay pins and separate installation paths.

## Observed pre-commit validation

Full Python suite: 162 passed. Pinned Ruff 0.14.0: passed.

The initial dependency-pin test exposed an over-escaped regex in the new
test parser, not an established package conflict. The parser was corrected,
an independent parser regression was added, and the full suite passed.
No dependency versions were changed.

`validation-record.json` identifies the tested source bytes and local logs.
These tests ran against an uncommitted M2 checkout using the existing M1
dependency image. Record generation does not constitute another test run.

## Identity and boundaries

The template rename intentionally changes path-sensitive code/cache identity.
Do not rewrite old cache entries or historical provenance to the new filename.

Lock files, runtime declarations, Dockerfiles, scientific policy and canonical
data are unchanged. The auxiliary workflows were not dispatched; the refresh
workflow can fetch data and push to main. Their main checkout refs remain intact.

Fresh M2 outputs must be generated and verified after the checkpoint commit.
Do not claim old M0/M1 renders are fresh M2 evidence. A fresh output directory
does not imply a cold dependency cache or byte-identical HTML/PDF output.

## Pending

- Committed-checkout M2 validation and fresh output capture.
- Secret scan of final history.
- Remote CI and PR review.
