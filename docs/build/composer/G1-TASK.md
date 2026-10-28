# G1 task: strict contract and resolver for the existing reference comparison

Status: experimental implementation candidate, written 28 October 2026 and left
uncommitted for review. Implemented and author-run tested only. **G0 remains open. No
requirement is completed, verified or accepted by this task.** Independent verification
and human acceptance are pending, and no production renderer is enabled.

## Base and ownership

- Branch: `design/contracts`, created from `build/composer` at
  `0b9975fca19f762bec2566588495c974d7cab674` (clean worktree, no other branch reused).
- Primary writer: this Hermes session only.
- Reviewer/verifier: not assigned; review findings must record the actual reviewer when
  review occurs. The author is not the independent verifier.

## Allowed paths (all new; no existing file modified)

- `scripts/health_pipeline/composer_contracts.py`
- `scripts/health_pipeline/config/composer/component-contract/1.json`
- `tests/test_composer_contracts.py`
- `tests/fixtures/composer/` (compact JSON fixtures)
- `docs/build/composer/G1-TASK.md` (this record)

Explicitly untouched: analysis (`analyse.py`, `harmonise.py`, `checks.py`,
`inventory.py`), presentation (`publish.py`, `render_selected.py`, `report_shared.qmd`,
`templates/`), `Snakefile`, `workflow/`, request v1/v2 (`tabular_run.py` and the
`health-report/tabular-request/1|2` implementation), locks, CI workflows, source data
and the requirements ledger.

## Objective

One strict, deterministic contract and resolver for the comparison that already exists,
so the first comparison block and its adjacent evidence inspector can consume retained
identities without the presentation layer re-deriving anything.

## Chosen comparison (precisely)

Disease-level reference change, **not** the group-level index family:

- metric type `reference_change`, formula `percent_change`, unit `percent`
- metric id shape `<topic>:reference_change`, e.g. `virus:reference_change`
- inputs recorded in `metrics.csv` `inputs_json`: `<topic>:<reference_year>:count` and
  `<topic>:<latest_year>:count`
- produced by `analyse.analyse()` (`scripts/health_pipeline/analyse.py:155-159`); group
  rows (`<class>:main:<year>:total`, `group_index`, `<class>:main:reference_change`) are
  deliberately out of scope for this contract version.

Preserved behaviour, owned by the analysis stage and only re-read here:

- zero reference count makes the percentage unavailable (`value` empty, never `0`)
- zero latest count stays `-100.0`
- missing/ineligible periods, populations or completeness still fail the canonical run;
  this task does not convert a failed run into an "excluded" success

Immediate G2 consumer: the presentation inspector beside the change/findings view —
`findings_html()`/`friendly_changes()` in
`scripts/health_pipeline/templates/report_helpers.R`, which currently recompose metric
ids as strings and re-derive the trace formula. G2 wiring reads the resolved instance and
evidence documents instead. Nothing in this task renders or is imported by the workflow.

## Interface decisions

Contract ids `health-report/composer-component/1` (instance),
`health-report/composer-evidence/1` (evidence) and
`health-report/composer-composition/1` (composition), validated against one JSON Schema
(draft 2020-12, `additionalProperties: false` throughout).

Layer separation, enforced by API shape:

1. `validate_instance` / `validate_evidence` / `validate_composition` — structural only,
   no caller I/O; the only file read is the bundled schema itself, cached and not
   caller-controlled.
2. `resolve_instance` / `resolve_composition` — pure: no clock, network, environment or
   writes. Fills defaults with a resolution trace.
3. `load_document` / `load_bundle` — read-only filesystem loaders.
4. `verify_references` / `check_block` — read-only cross-checks against a loaded bundle,
   with two explicit trusted roots: `bundle_root` for saved artifacts and
   `project_root` for implementation code. An optional `results_root` resolves archived
   source files named by lineage.

Settings precedence is author > profile > component default, traced per field. The
submitted instance and evidence are deep-copied before use; the caller's objects are
never mutated. Structure is preserved, **not** bytes: formatting and key order of the
submitted file are not retained.

Identities are separate and content-derived:

- analytical: snapshot id + validated analytical scope + method/version + parameters
- result: analytical + result metric id + saved value + unit + formula + inputs
- instance/display: component type/version + instance id + result + plotted row keys +
  effective presentation/disclosure
- composition: ordered list of (instance id, instance identity)

Reordering keeps instance/result identities and changes the composition identity;
duplication mints a new instance id and display identity while sharing the result
identity. Precision, disclosure state and cosmetic labels never enter numerical
identity, and a presentation-bearing stakeholder document is never hashed wholesale into
it.

## Known limit, stated deliberately

Matching digests, references and lineage establish internal **consistency, not numerical
truth**. A party that rewrites `metrics.csv` and recomputes `bundle.json` plus every
recorded digest satisfies this contract. Independent recomputation from captured inputs
remains separate work (`design/verification`, E5 of the inspectable-blocks decision) and
is not implemented or claimed here. No protection is claimed against hostile concurrent
filesystem mutation during a check.

## Pending review

- Reviewer identity, findings and disposition.
- Field naming/versioning authority (B1) — this is a proposal.
- Whether the canonical bundle should emit these documents, or G2 wiring should call the
  resolver; this task defers emission and leaves the canonical route untouched.
- Whether an absolute-difference metric is required for the calculation panel; that is an
  analysis change needing separate approval and a parity fixture, not part of G1.
- Disclosure defaults, distribution policy, PDF/static and optional-format decisions.

## Progress and checks (author-run, not independent verification)

Implemented in this candidate:

- `scripts/health_pipeline/composer_contracts.py` — structural validation against the
  bundled schema, strict JSON parsing (duplicate keys, `NaN`/`Infinity` rejected), pure
  default resolution with a per-field trace, four identities, read-only bundle loader and
  read-only reference resolution with two trusted roots plus an optional archive root.
- `scripts/health_pipeline/config/composer/component-contract/1.json` — one draft
  2020-12 schema, `additionalProperties: false` throughout.
- `tests/test_composer_contracts.py` — 65 tests: the original structural/consistency set
  plus 17 R1–R7 regression cases. Structural fixtures (placeholder digests) are kept
  apart from generated bundles that carry real digests.
- `tests/fixtures/composer/{valid,invalid}` — seven compact documents: instance, evidence,
  evidence-unavailable, composition, unknown-field, unsupported contract, unsupported
  component.

Checks actually run, all with `docker --context rootless run` on image
`sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8`, `--pull never`,
`--user 0:0`, `--network none`, `--cpus 2 --memory 4g --memory-swap 5g`,
`--pids-limit 512`, `PYTHONDONTWRITEBYTECODE=1`,
`python -m pytest -q -p no:cacheprovider` with an explicit `--basetemp` inside the
container. Resource meaning: `--cpus 2` allows two CPUs, `--memory 4g` is 4 GiB of RAM,
and `--memory-swap 5g` is a 5 GiB **combined RAM-plus-swap** limit (1 GiB of swap above
the 4 GiB RAM), not 5 GiB of swap on its own. `--pids-limit 512` caps processes.

| Run | Target | Result | Exit | Log |
|---|---|---|---|---|
| Original focused, first attempt | `tests/test_composer_contracts.py` | 1 failed, 47 passed (1.79s) | 1 | `~/.local/state/composer-bootstrap/g1-checks-20261028T053650/focused.log` |
| Original focused, after one test-side repair | same | 48 passed (1.86s) | 0 | `~/.local/state/composer-bootstrap/g1-checks-20261028T053650/focused-2.log` |
| Original maintained suite | whole `tests/` | 401 passed (22.03s) | 0 | `~/.local/state/composer-bootstrap/g1-checks-20261028T053650/maintained-suite.log` |
| Regression suite before fixes (R1–R7 tests added, implementation unchanged) | `tests/test_composer_contracts.py` | 15 failed, 48 passed (2.25s) | 1 | `~/.local/state/composer-bootstrap/g1-checks-20261028T055132/regressions-before-fix.log` |
| Focused after first repair pass | same | 4 failed, 61 passed (2.09s) | 1 | `~/.local/state/composer-bootstrap/g1-checks-20261028T055433/focused-after-repair.log` |
| Focused after second repair pass | same | 65 passed (1.99s) | 0 | `~/.local/state/composer-bootstrap/g1-checks-20261028T055433/focused-after-repair-2.log` |
| Maintained suite after repairs | whole `tests/` | 418 passed (25.21s) | 0 | `~/.local/state/composer-bootstrap/g1-checks-20261028T055433/maintained-suite.log` |

The 401/48/47 rows are the historical pre-repair results and are preserved as such. The
15-before-fix run is the evidence that the R1–R7 counterexamples were real: every one of
those 15 cases failed against the unmodified candidate.

Of the 17 R1–R7 regression cases, only **15** were demonstrated failing in that original
before-fix run. The two additional R1 safety cases (unsafe *unlisted* consumed artifact;
symlinked or unsafe `bundle.json`) were written afterwards with the second repair pass:
the unlisted-artifact case failed in the intermediate run (one of its 4 failures), while
the `bundle.json` case passed on its first run because that safety check already existed
from the first repair pass. They are not claimed to have failed before any repair.

The pre-repair failure in `focused.log` was a test-side assertion: an "available" claim
that still carried `unavailable_reason` was rejected by `validate_evidence` (code
`availability`) earlier than the test expected. The repair cleared the reason in the test
patch so the reference-level `availability_disagreement` path is exercised; no
implementation behaviour was changed to obtain green tests.

Review inputs versus execution: the R1–R7 findings came from a source review in chat that
included isolated command-line path probes (symlinks, manifest digests, fixture counts).
Those review inputs are not execution of the full suite or of any verification step, and
none of this document claims completed independent verification or acceptance.

Scope note on plotted rows: the rule that `plotted.file` is `series.csv` and that the rows
are exactly the two bound endpoints applies **only to this component version**
(`reference-comparison/1`). It is not a general rule for later trend, small-multiple or
chart components, which will declare their own plotted subsets.

Not run, and not claimed: ruff/lint (not installed and not installed here), any container
rebuild, any Snakemake dry-run, the canonical release, browser review, independent
verification, or G2 wiring. Because `release.py` hashes
`scripts/health_pipeline/*.py`, this new module will add one entry to `release.json`'s
`code` map the next time a release is generated; a dry-run would not prove runtime
compatibility, so none of this is described as proven.

Remaining limitations: consistency is not numerical truth (see above); the archive check
is optional and structural; no protection is claimed against hostile concurrent
filesystem mutation during a check; the schema-only fixtures must not be cited as verified
bundles; no requirement is accepted and G0 remains open.

## Second review round: targeted counterexamples (author-run)

A targeted execution of the uploaded module produced further counterexamples inside the
same review IDs. Eight regression cases were written and shown failing before the
corresponding checks existed:

- R1: `test_r1_extra_manifest_entry_with_stale_digest_is_reported`,
  `test_r1_unsafe_extra_manifest_entry_is_not_read`
- R2: `test_r2_symlinked_snapshot_ancestor_is_rejected`
- R3: `test_r3_series_value_must_match_the_bound_count`,
  `test_r3_series_measure_and_geography_must_match_the_scope`
- R6: `test_r6_unknown_profile_section_is_rejected`
- R7: `test_r7_self_referencing_count_lineage_is_rejected`,
  `test_r7_mutually_referencing_counts_without_raw_provenance_are_rejected`

A ninth case, `test_r7_monthly_raw_rows_for_one_annual_count_remain_valid`, passed before
and after: legitimate multiple raw rows for one annual count are still accepted.

| Run | Target | Result | Exit | Log |
|---|---|---|---|---|
| Round-2 regressions before fixes | `tests/test_composer_contracts.py` | 8 failed, 66 passed (2.41s) | 1 | `~/.local/state/composer-bootstrap/g1-checks-20261028T061049/round2-before-fix.log` |
| Focused after round-2 repairs | same | 74 passed (2.46s) | 0 | `~/.local/state/composer-bootstrap/g1-checks-20261028T061049/focused-after-fix.log` |
| Maintained suite after round-2 repairs | whole `tests/` | 427 passed (25.61s) | 0 | `~/.local/state/composer-bootstrap/g1-checks-20261028T061049/maintained-suite.log` |

Repairs in this round, all read-only consistency checks with no recalculation:

- R1: declared manifest entries outside the consumed set are now path-checked, bounded to
  a regular file inside the bundle, and digest-verified; unsafe entries are never read.
- R2: every component of `snapshot_path` is walked from `results_root` and a symlinked
  ancestor is rejected, because checking only the archive directory itself was
  insufficient.
- R3: saved series endpoint values are compared directly with the bound count values, and
  the series measure/geography are compared with the bound unit and saved scope. No
  percentage is recomputed.
- R6: unknown top-level profile-default sections (including typos) are rejected; precedence
  remains author > profile > component and the defaults remain cosmetic-only.
- R7: metric-derived lineage for a bound raw_sum count is rejected as unsupported, which
  covers self-reference and mutually referencing count pairs without adding a recursive
  resolver; legitimate multiple raw rows are preserved.

Review/probe scope: both review rounds were source reviews in chat plus isolated
command-line probes (symlinked paths, stale manifest digests, fixture counts, targeted
module execution). They are review inputs and targeted checks, not a full independent
verification, not browser acceptance, and not completion of any requirement.
