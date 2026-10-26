# M0 evidence: preserve and reproduce V1

Milestone M0 of the steward-ready integration proposal. This folder records
what was actually executed against the unmodified V1 release. No V1 code or
data is changed in this milestone; the only additions are this evidence and
`scripts/evidence/m0_capture.sh`.

## Baseline identity

| Item | Value |
|---|---|
| Repository | `ODESA-OpSciHack26/Health_Report_Generator` |
| Baseline | `release/v1.0.0` at `7253baebde65c21d350ab392fe55264585391822` |
| Integration branch | `integration/steward-ready-v1`, created at the baseline commit |
| Worktree before run | clean (0 changed files) |
| Data snapshot id | `d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee` (168 files from `data/reference/`) |
| Pinned toolchain (`workflow/toolchain.json`) | Python 3.11.6, R 4.3.2, Quarto 1.3.353, TinyTeX 2026.10, uv 0.8.14 |

Donor heads verified on 2026-10-26: `dev_nisha` `a1cba89b…`,
`fix/v2-report-rendering-and-ui` `6cbe222e…` (unchanged from the proposal).

## Run 1: sandbox, native Python (2026-10-26)

Environment: Linux x86_64 sandbox, Python 3.11.6 installed with uv, packages
from `scripts/health_pipeline/requirements.lock.txt` and
`scripts/ci/requirements-lint.txt`. Docker, R and Quarto were not available.
This is not a reference platform. Machine-readable record: `sandbox-run.json`.

Commands:

```sh
uv venv --python 3.11.6 .venv && . .venv/bin/activate
uv pip install -r scripts/health_pipeline/requirements.lock.txt -r scripts/ci/requirements-lint.txt
ruff check .
python -m pytest -q
snakemake --dry-run --cores 1 --config out=reproduced/m0-native-tables
snakemake tables --cores 2 --config out=reproduced/m0-native-tables
snakemake tables --cores 2 --config out=reproduced/m0-native-tables-rerun
```

| Check | Status | Detail |
|---|---|---|
| Ruff lint | passed | All checks passed |
| Unit, schema and contract tests | passed | 131 passed, 0 skipped (`pytest.txt`) |
| Snakemake dry run, full target | passed | 17 jobs planned (`dryrun.txt`) |
| Analytical stages (inventory, harmonise, validate, analyse x3) | passed | 7/7 steps |
| Fresh-folder rerun | passed | snapshot, harmonised data, checks and all bundle tables byte-identical |
| Cross-audience agreement | passed | `metrics.csv` identical for researcher, health_institution, public (296 metrics each) |
| Quality checks | recorded | 774 PASS, 76 SKIP, 3 WARN, 0 FAIL |
| HTML/PDF rendering, Shiny packages, `release.json` | environment-blocked | needs the report container |
| `check_outputs.py`, `verify_release.py`, Shiny/dashboard smoke, no-op rebuild | environment-blocked | depends on full render |
| Secret scan | not run | CI job; outside the M0 gate |

The three standard audiences currently share identical analytical settings
(years 2021–2025, reference and index base year 2019, geography CHFL), so
identical metrics are expected here; this does not yet test differing requests.

## Run 2: container on the maintainer machine (pending)

```sh
bash scripts/evidence/m0_capture.sh
```

The script builds `Dockerfile.report` for linux/amd64, runs the full workflow
into the fresh, git-ignored folder `reproduced/m0-container/`, runs the
output, release, Shiny and no-op checks, and compares the snapshot id,
intermediate tables and every bundle table with the hashes in
`sandbox-run.json`. It writes logs, environment details, the base-image
digest, `release.json` and rendered-artifact hashes to
`reproduced/m0-container/evidence/` and prints a summary block. It refuses
to run if the output folder already exists and never touches `results/`.

The M0 gate is met only after Run 2 reports all steps passing, or after any
failure is recorded here as failed or environment-blocked with its log.

## Observations for later milestones

These are inventory notes, not fixes made in M0.

1. The single shared template is
   `scripts/health_pipeline/report_public_health_expert.qmd`, copied to
   `report.qmd` at render time. The filename suggests an audience-specific
   template although it is shared by all audiences (M2 naming).
2. `config/stakeholders/public_health_expert.json` exists but is not listed in
   `workflow/config.yaml`; a candidate for the M3 fourth-audience test.
3. V1 already embeds primary provenance via `audience_reports.R`
   (`id="report-provenance"`), and `check_outputs.py` checks for it. Donor
   commit `82d4a9f` fixed this for v2's separate templates; whether any part
   applies to V1 is decided in M1 from Run 2 output, not assumed.
   Donor commit `d4db2e9` mainly edits `reports/shared/*`, which does not exist
   in V1.
4. V1's institution view (`monitoring_table`, `monitoring_summary`) ranks raw
   differences and has no normal/low status classification, so the v2
   unknown-baseline defect is not present in that form. Behaviour with a
   missing reference-year count (NA) is untested and is an M1 item.
   `analyse.py` already fails on a nonpositive index baseline.
5. Four Python/R lock files (`requirements.lock.txt`,
   `requirements.ui.lock.txt`, `uv.lock`, `renv.lock`) and two Dockerfiles
   need an ownership decision (M2).
6. The optional Marimo interface depends on a GitHub token and Actions,
   which conflicts with the local, account-free goal (M3).
7. The README clone URL points to `LarsEBaumann/Health_Report_Generator`,
   and the README links `docs/history.md`, which does not exist (M2).
