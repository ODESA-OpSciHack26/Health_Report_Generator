# G0 status record, composer isolated integration lane

Status: documentation and evidence record only. **G0 is not closed.** Nothing here is
product implementation, independent verification, human visual acceptance or an
archived-input replay. Written 28 October 2026 against `build/composer` at
`72b80d95703159d3102d7021b14a598adac4d72e`.

Governing documents remain [HANDOFF.md](HANDOFF.md) and [requirements.json](requirements.json),
with [integration-acceptance.md](../../integration-acceptance.md) and
[b0-conflict-dispositions.md](../../b0-conflict-dispositions.md).

## 1. Environment and lane state verified

| Item | Observed |
|---|---|
| User | `builder` |
| Repository | `/home/builder/composer-sandbox` |
| Branch | `build/composer`, tracking `origin/build/composer` |
| HEAD | `72b80d95703159d3102d7021b14a598adac4d72e` |
| Worktree at the pre-patch anchor | clean (`git status --porcelain` empty) |

That clean state is the pre-edit anchor only, observed before any change in this turn.
The current candidate is an **uncommitted** documentation diff on `72b80d9`: two
modified files (`data/README.md`, `docs/build/composer/requirements.json`) plus one new
file (`docs/build/composer/G0-STATUS.md`). It is not a clean worktree and not a new
commit.

## 2. Baseline evidence recorded, not rerun

Two bootstrap runs already exist outside the repository. Their metadata was read from
the recorded files; the runs themselves were **not** executed by this session. Both ran
on bootstrap commit `72b80d9`, which is not seed `0cb8dd095a29760ca7b0dc45167538b938b3a6c7`,
and both used container image
`sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8`.

- `EV-BOOT-001`, `/home/builder/.local/state/composer-bootstrap/checks-opWZHBjo`,
  2026-10-28T03:30:32Z to 03:30:59Z, exit 0: pytest JUnit report records 353 tests,
  log records "353 passed in 22.02s"; worktree clean afterwards.
- `EV-BOOT-002`, `/home/builder/.local/state/composer-bootstrap/baseline-lJXSvvGc`,
  2026-10-28T03:33:00Z to 03:34:32Z, exit 0: 17 of 17 workflow steps, "Audience outputs
  and provenance verified", "Shiny server outputs passed" for the researcher app, and
  expected artifacts present for researcher, health_institution and public.
  `release.json` records `git_commit` 72b80d9 and an empty `git_status`.

Recorded detail, including per-run inspected files and non-rerun lists, is in
`evidence_records` of [requirements.json](requirements.json).

Explicitly not claimed: these are not executions of seed `0cb8dd0`, not independent
verification, not blue-M4 browser acceptance, not an archived-input replay, and not
acceptance of any requirement. One observed detail: the recorded release manifest
reports `tex` as `unavailable`. The earlier toolchain log reports pdfTeX present, and
the canonical workflow generated PDF artifacts. The reason for the unavailable probe
result was not investigated in this session.

## 3. G0 documentation correction applied

[data/README.md](../../../data/README.md) previously stated that the repository had no
project-wide licence and granted no reuse rights, contradicting the tracked MIT
[LICENSE](../../../LICENSE) and the statement in
[release-checklist.md](../../release-checklist.md). Only that "Project licence"
paragraph was rewritten: project software is MIT under `LICENSE`, and source-data terms
remain separate with FOPH attribution still required. `LICENSE`, `CITATION.cff`,
attribution, copyright holders, publisher terms and source data were not changed.

## 4. Unresolved G0/B0 items

1. B0 is not formally closed: [b0-conflict-dispositions.md](../../b0-conflict-dispositions.md)
   still records B0 as unclosed and carries no reviewed-candidate or owner entry.
2. Requirement states R01-R17 are deliberately unchanged; recording baseline evidence
   does not complete R01.
3. Decision-required and optional entries have no disposition yet: R14 generic
   PDF/static parity or explicit deferral, R15 optional format/encoding scope.
4. No cost/time budgets, artifact storage/retention policy or credential boundary is
   recorded, which [HANDOFF.md](HANDOFF.md) requires before unattended execution.
5. No independent verifier and no human visual review are recorded for the baseline.
6. This session validated JSON syntax, changed links and `git diff --check`, and reran
   the documentation tests and the maintained suite inside the recorded image against
   the uncommitted diff. It did not run a canonical release, `verify_release.py`, the
   researcher Shiny smoke test, or any container build.

## 5. Pending human decisions

- Reviewer identity/assignment and file ownership for the first assignment.
- Approval or rejection of the proposed minimal G1 contracts assignment (not approved).
- R14 and R15 dispositions.
- Budget, retention and credential declarations for any runner.
- Any promotion of `build/composer` toward `integration/steward-ready-v1`.

## 6. Canonical reporting route

The canonical reporting entry point is `snakemake --cores 2` via
[Snakefile](../../../Snakefile) with [workflow/config.yaml](../../../workflow/config.yaml),
producing `results/reports/<stakeholder>/` for researcher, health_institution and public
through the shared `scripts/health_pipeline/report_shared.qmd`: `report.html`,
`methods.html`, `report.pdf`, `methods.pdf`, `provenance.json`, `provenance.pdf.json`
and the Shiny `app/` bundle. The supported verifier set is `check_outputs.py` (audience
outputs and provenance) and `verify_release.py` (release hashes, provenance and rendered
links); both exist in `scripts/health_pipeline/` and both are invoked by the CI jobs.
The recorded baseline command for this lane executed `check_outputs.py` and the
researcher Shiny smoke test. It did not execute `verify_release.py`, and no execution
record for that verifier exists in the recorded evidence directories; its availability
is not evidence that it was run.

This route remains the final supported entry point. The future block presentation must
integrate with it: registered blocks and presets render verified results through the
same shared source and entry point, not through a parallel audience or reporting path.

## 7. Checks performed on this candidate

Run against the uncommitted documentation diff based on `72b80d9`. These are regression
checks on a working tree, not results attributable to a commit, and not independent
review.

| Check | Command | Result |
|---|---|---|
| JSON syntax | `python3 -m json.tool docs/build/composer/requirements.json` | exit 0 |
| Changed links and anchors | read-only Python check of `data/README.md` and `docs/build/composer/G0-STATUS.md` using the same regex and slug rule as `tests/test_release_docs.py` | 0 errors, exit 0 |
| Whitespace errors | `git diff --check` | exit 0, no output |
| Documentation tests | `docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD":/app -w /app --user "$(id -u):$(id -g)" composer-report:bootstrap-72b80d9 python -m pytest -q -p no:cacheprovider --basetemp=/tmp/pt-docs tests/test_release_docs.py tests/test_handover_docs.py` | 12 passed in 2.29s, exit 0 |
| Maintained suite | same invocation without the two test paths, `--basetemp=/tmp/pt-full` | 353 passed in 20.56s, exit 0 |

Image: `composer-report:bootstrap-72b80d9`, id
`sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8` — the
recorded baseline image, not a rebuild. The suite result is a documentation-regression
rerun, not a new canonical release and not a new clean commit.

Execution properties of these reruns, recorded separately: CPU, memory and process/PID
limits were not explicitly supplied; network access was not explicitly disabled; the
container user was requested as `1001:1001`; and context selection was implicit, because
no context was named and the effective context was not captured in the execution
records. Nothing here asserts that a rootless daemon was or was not used.

`PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider` were used only to keep the worktree
free of caches, not as isolation. The explicit hardening form for a future rerun is
`docker --context rootless run ...`, where `--context` is a global Docker option rather
than a buildx-only flag. No hardened rerun was attempted here, so that form remains
unexercised for these documentation checks.

After the final wording-only edits in this turn, no container rerun was performed:
`requirements.json` is read by no test, and `G0-STATUS.md` sits outside the `docs/*.md`
glob used by the link test, so only the static checks above were repeated.

These observations are limited to the documentation-candidate reruns in this section.
They say nothing about the earlier bounded bootstrap executions summarised in section 2,
whose recorded properties remain those of `EV-BOOT-001` and `EV-BOOT-002`.

No independent reviewer observed these checks.

## 8. Runtime used for this assessment

Hermes Agent v0.22.5 (2026.9.24), stable, local `bf0203a794a0`
(`bf0203a794a07aac3ff764972ab9087baa4e4f4e`), install directory
`/home/builder/.hermes/hermes-agent`. Its dependency audit is **not** clean: recorded
`npm audit` evidence under `/home/builder/.local/state/composer-bootstrap/hermes-audit-f_gzrhld`
shows exit code 1 for root (1 high: zod), ui-tui and web (1 moderate: jsdom, 1 high:
undici). This installation is therefore not described as vulnerability-free; the audit
findings are unresolved and unrelated to the repository product surface.
