# M1: provenance and baseline regression evidence

Starting integration commit:
`7e34cc8e95856bb0b7fa2a8adf909e30e69ae1c3`.

## Demonstrated defect and repair

Before repair, nine negative tests accepted false effective parameters,
filters or audience identity across three audiences. Ten controls passed.

The release verifier now compares claims against saved stakeholder parameters,
reusing the producer's filter-key list. Existing release hashes, bundle hashes,
parameter hashes, template hashes and embedded-record checks remain enabled.
The older minimal CI fixture was updated to contain consistent claims;
no test assertions were removed.

After repair, all 19 focused probes passed.

## Extended coverage and observed results

- Full extended Python suite: 153 passed.
- Missing reference/current rows and null counts: affected series excluded.
- Zero reference count with a separate positive index baseline:
  relative change unavailable.
- Positive reference count: expected percentage preserved.
- Zero latest count with positive reference: minus 100 percent.
- Existing nonpositive index-baseline regression remains in the full suite.
- R checks: unavailable, zero and minus 100 percent remain distinct;
  institution table labels undefined change as Not available.
- Pinned Ruff 0.14.0 passed again after the extended test additions.
- Stricter verifier accepted the preserved rendered M0 release.

## Evidence identity and limitations

`validation-record.json` records local log hashes and tested source-file hashes.
The record is generated from existing maintainer logs; generation is not
test re-execution. Tests ran against an uncommitted M1 checkout, not a new M1
commit. The log files remain under `reproduced/m1-probes/evidence/`, git-ignored.

The provenance fixtures use synthetic HTML, not Quarto renders. The R check
uses an in-memory modification of a real verified bundle. The real-output
compatibility check uses M0 artifacts generated at `963d19f`, not fresh M1
outputs. It does not relabel their provenance as M1.

Committed-checkout validation, fresh M1 workflow evidence, and
remote CI remain pending. No scientific policy, canonical data, analysis
formula, dependency lock file, authorship metadata, or release reference
was changed by this repair.
