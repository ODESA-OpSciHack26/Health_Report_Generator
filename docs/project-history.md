# Project History and Release Evidence

> Historical record only. This document describes the original release and earlier repository phases. It is not the current user guide for `develop/v2.0.0`. See [docs/guide.md](guide.md) for the current workflow.

**Authors:** ODESA OpSciHack26 project team and contributors  
**Created:** 2026-10-18  
**Last updated:** 2026-10-18  
**Purpose:** Preserve release decisions, audits, and validation evidence in one place.


## Original record: docs/phase-0-baseline.md

# Phase 0 baseline — 2026-10-08

This document records the repository baseline before any cleanup, renaming, data migration, deduplication, or deletion.

## Source state

- Repository: `LarsEBaumann/Health_Report_Generator`
- Baseline branch: `chore/phase-0-baseline`
- Baseline commit: `4ce483491ac7891ed04acc2b1f89917f93af3880`
- Baseline commit message: `Update IDD reference data`
- Tracked files: 325
- Working tree after checkout: clean

## Commands executed

```sh
python -m pip install -r scripts/health_pipeline/requirements.lock.txt
python -m pytest -q
snakemake --dry-run --cores 1 --config data_root=Data
snakemake --cores 2 --config data_root=Data --printshellcmds
snakemake tables --cores 2 --config out=baseline_reference
```

The local inspection environment provided Python 3.12.8 but did not provide R, Quarto, TinyTeX, or Docker. Therefore the complete HTML/PDF/Shiny build could not be validated locally; CI remains the authoritative complete-build environment for this baseline.

## Test and workflow results

- Python tests: **PASS**, 44 tests passed in 3.92 seconds.
- Snakemake dry run with `data_root=Data`: **PASS**, 9 jobs planned.
- Pipeline through inventory, harmonisation, validation, and analysis with `data_root=Data`: **PASS**.
- Complete local build: **BLOCKED BY ENVIRONMENT**, because the `quarto` executable was unavailable when HTML and PDF rendering began; this was not a scientific validation failure.
- Default lowercase `data/reference` tables target: **PASS**.

## Uppercase `Data/` baseline

- Snapshot ID: `f1484622df74831453d66fb36cfc9fab002bd0695385195143930328d4f74653`
- Snapshot files: 74
- Dataset records: 37
- Quality checks: 370 total; 347 PASS, 21 SKIP, 2 WARN, 0 FAIL
- Selection: 20 candidate series; 12 included and 8 excluded
- Analysis outputs: 72 `series.csv` rows and 296 `metrics.csv` rows
- Bundle hashes were generated successfully for the analysis tables.

The two warnings concern missing values in wastewater datasets: one series is 100% missing and another is 52.7% missing. Report selection requires complete values, so the warnings do not silently enter the selected report series.

## Duplicate and path inventory

The uppercase `Data/` tree contains 37 dataset directories but only 20 unique data-plus-metadata byte pairs. There are 9 exact duplicate groups containing 17 redundant directory copies. No same-data/different-metadata conflict was found in this byte-level inventory.

Two dataset directories are unexpectedly nested inside `Data/RESPVIRUSES_wastewater (1)/`:

- `RESPVIRUSES_wastewater (3)`
- `SHIGELLOSIS_oblig`

No duplicate directory or nested directory has been deleted. Any future migration must preserve the recorded snapshot and compare post-migration analysis-table hashes or independently documented expected changes.

## Lowercase `data/reference` baseline

- Snapshot ID: `d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee`
- Snapshot files: 168
- Dataset records: 56
- Quality checks: 853 total; 774 PASS, 76 SKIP, 3 WARN, 0 FAIL
- Selection: 56 candidate series; 12 included and 44 excluded
- Analysis outputs: 72 `series.csv` rows and 296 `metrics.csv` rows

The two roots produce different snapshots and inventories, but the currently selected stakeholder analysis produced the same row counts for `series.csv` and `metrics.csv`. Row-count equality is not proof of content equality; later migration work must compare content hashes and metric values before choosing the canonical root.

## Environment divergence

- README, Conda configuration, and GitHub Actions describe Python 3.11/3.11.6.
- `pyproject.toml` requires Python 3.14 or newer.
- Docker uses Python 3.14.
- README, Conda configuration, and GitHub Actions use Quarto 1.3.353.
- Docker uses Quarto 1.9.38.

These differences must be resolved before the environment is treated as a single reproducible contract.

## Repository hygiene observations

- Two tracked `.DS_Store` files are present under `scripts/health_pipeline/`.
- The default pipeline configuration points to lowercase `data/reference`; the main validation workflow overrides the root to uppercase `Data`.
- Three presentation profiles exist, but the main Snakemake configuration enables one stakeholder file.

## Baseline gate

No destructive cleanup is approved by this record. Before deleting or moving data, the next phase must:

1. Preserve this commit and both snapshot IDs.
2. Produce a machine-readable duplicate-resolution map.
3. Compare pre/post-migration table contents and hashes, not only row counts.
4. Explain every intentional difference.
5. Keep validation at zero FAIL results.


## Original record: docs/phase-1-safe-hygiene.md

# Phase 1 safe hygiene

Phase 1 improves repository clarity without changing scientific calculations, source data, workflow configuration, or generated report behavior.

## Included

- Contributor guidance and validation expectations.
- Data-root documentation and a destructive-change safety gate.
- A repository map classifying production, optional, experimental, legacy, and historical paths.
- Explicit notices in historical output/prototype directories.
- Removal of tracked operating-system metadata files.

## Excluded

- No source datasets are moved, renamed, deduplicated, or deleted.
- No environment versions or dependency locks are changed.
- No stakeholder parameters, formulas, selection rules, schemas, or templates are changed.
- No historical prototype is deleted in this phase.

## Acceptance checks

```sh
python -m pytest -q
snakemake --dry-run --cores 1 --config data_root=Data
```

A full CI build remains required before merging.


## Original record: docs/phase-2-environment-alignment.md

# Phase 2 environment alignment

Phase 2 defines one machine-readable runtime contract and aligns every supported execution path with it.

## Contract

- Python: validated 3.11.6; supported `>=3.11.6,<3.12`
- R: 4.3.2
- Quarto: 1.3.353
- uv: 0.8.14
- TinyTeX: baseline observation 2026.10; actual release version is recorded because CI installation is not byte-locked

The authoritative values are stored in `workflow/toolchain.json`. A regression test checks the Python metadata, Conda metadata, Dockerfile, CI workflows, and setup documentation against this contract.

## Decisions

The existing green full-report CI toolchain is retained as the validated contract. Docker and `pyproject.toml`, which previously required Python 3.14 and Quarto 1.9.38, are aligned to that contract. The optional uv environment remains a separate dependency set from the production Snakemake lock, but both now support the same Python line.

TinyTeX is not described as fully pinned: the setup action installs it dynamically. The workflow records the actual TeX version in release provenance, and the project does not claim byte-identical PDFs across platforms.

## Excluded

- No source data, stakeholder configuration, formulas, selection policy, or templates change.
- No production Python or R package versions change.
- No Quarto upgrade is attempted in this phase.

## Acceptance checks

```sh
python -m pytest -q
uv lock --check
snakemake --dry-run --cores 1 --config data_root=Data
```

A full CI report build and smoke tests are required before merge.


## Original record: docs/phase-3-canonical-data.md

# Phase 3 — canonical data root

## Decision

`data/reference/` is the canonical live input root. The default workflow already used it, while CI overrode the default with the older uppercase `Data/` tree. Phase 3 removes that override so local execution and CI read the same source release.

This is not described as deduplication. The roots are not byte-identical: `data/reference/` is broader and newer. The legacy tree is frozen and will be removed only in a separate, reviewable commit after the canonical build is green.

## Pre-migration evidence

The comparison was run from main commit `1aeb1a1414bcbf94ae8acf8288565f5edf21cf71` with the `tables` target against both roots.

| Property | Legacy `Data/` | Canonical `data/reference/` |
|---|---:|---:|
| Snapshot ID | `f1484622df74831453d66fb36cfc9fab002bd0695385195143930328d4f74653` | `d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee` |
| Dataset directories | 37 | 56 |
| Unique data/metadata byte pairs | 20 | 56 |
| Selected report series rows | 72 | 72 |
| Selected report metric rows | 296 | 296 |

The selected topic set and pathogen classification table are unchanged. Scientific table bytes are not identical: 14 series rows differ, including four count rows, twelve population rows, and fourteen calculated incidence rows. Differences are concentrated in revised 2022–2025 counts and 2025 population denominators. The complete hashes and path-level dispositions are preserved in the consolidated `phase-3-data-migration.json` record below.

## Safety interpretation

Equal row counts do not establish data equivalence. The canonical root is accepted as a newer source release, and all observed differences are disclosed rather than normalized away. Existing content-addressed snapshots remain the mechanism for reproducing an earlier release.

## Changes in this step

- Remove the CI-only `data_root=Data` override.
- Keep `workflow/config.yaml` at `data/reference` as the single active default.
- Update user documentation to name the canonical root.
- Add a machine-readable map covering every legacy directory, hashes, release metadata, duplicate groups, and its canonical successor.
- Add tests preventing active workflows from reverting to the legacy root.
- Keep `Data/` frozen until the canonical full-build checks pass; deletion is a separate reviewed commit.

## Acceptance gate

Phase 3 may proceed to legacy-tree deletion only when:

- Python tests pass.
- Snakemake dry run resolves from `data/reference/` without an override.
- Full HTML, PDF, and Shiny CI passes against `data/reference/` on both push and pull-request events.
- The migration JSON parses, covers all 37 legacy dataset directories, and contains no unmapped entries.
- No unexplained scientific output difference remains.


## Original record: docs/phase-3-data-migration.json

{"analysis_comparison":{"canonical_metrics_rows":296,"canonical_metrics_sha256":"e4e37ba8162c5c911b30741f065e37a62c4f7dbf6970e2e4deb51a11d862555f","canonical_series_rows":72,"canonical_series_sha256":"8ed503bee5bc41a60200456c9263c6d7f22f8d1d507d6520daac4b88635a611a","changed_count_rows":4,"changed_incidence_rows":14,"changed_population_rows":12,"changed_series_rows":14,"explanation":"The canonical root is a newer and broader IDD release. Differences are concentrated in revised 2022-2025 counts and 2025 population denominators; they are expected source-version changes, not a byte-preserving rename.","legacy_metrics_rows":296,"legacy_metrics_sha256":"4b80640609dff31f79fd977774cd91a8c8768d3a7ab551eada0e7f8e8799def2","legacy_series_rows":72,"legacy_series_sha256":"58ce7f3b40237c7d0f37529430bb228d4f35de6eb731793883a41c738953168f","pathogen_class_table_equal":true,"scientific_values_identical":false,"selected_topics_equal":true,"stakeholder":"public_health_expert"},"canonical_dataset_directories":56,"canonical_root":"data/reference","canonical_snapshot_id":"d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee","decision":"data/reference is the canonical live source root; Data is a frozen legacy input pending removal after this migration PR passes full CI.","entries":[["Data/AIDS_oblig","data/reference/AIDS_oblig","6162e05227e011f677030c800bcb966161401db98832dbb04a0bc421d71a394c",1],["Data/AIDS_oblig (1)","data/reference/AIDS_oblig","6162e05227e011f677030c800bcb966161401db98832dbb04a0bc421d71a394c",1],["Data/CAMPYLOBACTERIOSIS_oblig","data/reference/CAMPYLOBACTERIOSIS_oblig","9043244ebaca8ba3a12a38d2f7642115894ea06e14ad04e70f01c6164185cf18",null],["Data/CHLAMYDIOSIS_oblig","data/reference/CHLAMYDIOSIS_oblig","3ad06897db7e9434a5479324b1926e5bbc85dc79d4e745a1e14d6e337f759983",null],["Data/COVID19_genomic_surveillance","data/reference/COVID19_genomic_surveillance","cd4035cf9b92c87581abdcf034be230f23f43546e3df8e36935dbaaac0c564df",null],["Data/COVID19_oblig","data/reference/COVID19_oblig","81659330ed8432543a4528be2ab254d0553ba327c4c99fcdb7044f796f025ff7",2],["Data/COVID19_oblig (1)","data/reference/COVID19_oblig","81659330ed8432543a4528be2ab254d0553ba327c4c99fcdb7044f796f025ff7",2],["Data/COVID19_oblig (2)","data/reference/COVID19_oblig","81659330ed8432543a4528be2ab254d0553ba327c4c99fcdb7044f796f025ff7",2],["Data/COVID19_sentinella","data/reference/COVID19_sentinella","eabb4283750fd5094bf1c3fff833f4aa0755812fef207fb5afbea6664ab552d2",3],["Data/COVID19_sentinella (1)","data/reference/COVID19_sentinella","eabb4283750fd5094bf1c3fff833f4aa0755812fef207fb5afbea6664ab552d2",3],["Data/COVID19_sentinella (2)","data/reference/COVID19_sentinella","eabb4283750fd5094bf1c3fff833f4aa0755812fef207fb5afbea6664ab552d2",3],["Data/COVID19_wastewater_sequencing","data/reference/COVID19_wastewater_sequencing","869deda465a9add91f4428716072545e0d5ec35d09ed24a116ddabb6506f1964",null],["Data/EHEC_oblig","data/reference/EHEC_oblig","ca9ef99a48ace01870afaa51bd0e1c69264c2164e9e9ade38af990ec0b55153e",null],["Data/GONORRHEA_oblig","data/reference/GONORRHEA_oblig","e2699bf76734c5899dfcd46f140af37d5088fe62f6eda57c28fb016fdd3ba870",null],["Data/HEPATITIS_A_oblig","data/reference/HEPATITIS_A_oblig","094c75e3027d29e0de694f95a1ca030e1c4cb674ee3ce807f4b7e0d22ef285b6",null],["Data/HEPATITIS_B_oblig","data/reference/HEPATITIS_B_oblig","eede200094378eb1983b8b84a7bc7a1cac9c7317101ca4902c34b846dd80bed4",null],["Data/HEPATITIS_C_oblig","data/reference/HEPATITIS_C_oblig","9f5f6dfa6ddaf133704a18209ec130ae7a16ed4d4735e2ef6267f57499f2b78e",null],["Data/HEPATITIS_E_oblig","data/reference/HEPATITIS_E_oblig","e4aa14b88e71cb01586685944991ac7b02f58561abed5c11120e25bd2832437b",null],["Data/HIV_oblig","data/reference/HIV_oblig","d3b57d48bc31ba25b967a4fa31149fee42fc932acdad83d955a581a58edbceae",4],["Data/HIV_oblig (1)","data/reference/HIV_oblig","d3b57d48bc31ba25b967a4fa31149fee42fc932acdad83d955a581a58edbceae",4],["Data/INFLUENZA_oblig","data/reference/INFLUENZA_oblig","7df68f32fa2a788395e5e2c10bd6394d822c1afedb98333bbc5cc5b144a92fd1",5],["Data/INFLUENZA_oblig (1)","data/reference/INFLUENZA_oblig","7df68f32fa2a788395e5e2c10bd6394d822c1afedb98333bbc5cc5b144a92fd1",5],["Data/INFLUENZA_oblig (2)","data/reference/INFLUENZA_oblig","7df68f32fa2a788395e5e2c10bd6394d822c1afedb98333bbc5cc5b144a92fd1",5],["Data/INFLUENZA_sentinella","data/reference/INFLUENZA_sentinella","1941c1d3de9f7dfdb15c11aac84ba9aa6feda3f07bfbd7f6101d643574f99d3a",6],["Data/INFLUENZA_sentinella (1)","data/reference/INFLUENZA_sentinella","1941c1d3de9f7dfdb15c11aac84ba9aa6feda3f07bfbd7f6101d643574f99d3a",6],["Data/INFLUENZA_sentinella (2)","data/reference/INFLUENZA_sentinella","1941c1d3de9f7dfdb15c11aac84ba9aa6feda3f07bfbd7f6101d643574f99d3a",6],["Data/LYME_sentinella","data/reference/LYME_sentinella","f667170e9287a352803efc34dda16cd63621fcae124d0591918df2d34df55237",null],["Data/RESPVIRUSES_sentinella","data/reference/RESPVIRUSES_sentinella","d0a76d079e3214bda6799bbced28f381d011b9632ca933aa290523de3fc4120d",7],["Data/RESPVIRUSES_sentinella (1)","data/reference/RESPVIRUSES_sentinella","d0a76d079e3214bda6799bbced28f381d011b9632ca933aa290523de3fc4120d",7],["Data/RESPVIRUSES_sentinella (2)","data/reference/RESPVIRUSES_sentinella","d0a76d079e3214bda6799bbced28f381d011b9632ca933aa290523de3fc4120d",7],["Data/RESPVIRUSES_sentinella (3)","data/reference/RESPVIRUSES_sentinella","d0a76d079e3214bda6799bbced28f381d011b9632ca933aa290523de3fc4120d",7],["Data/RESPVIRUSES_wastewater (1)/RESPVIRUSES_wastewater (3)","data/reference/RESPVIRUSES_wastewater","edf730c2773cb1779cee0bde291ca3ac2dfc8e152ff850f8144f460fa67aa628",8],["Data/RESPVIRUSES_wastewater (1)/SHIGELLOSIS_oblig","data/reference/SHIGELLOSIS_oblig","2b174430a3e57521f057b0f449b9f1ae56181f148ea80ec42e50921b7ee32879",9],["Data/RESPVIRUSES_wastewater (1)","data/reference/RESPVIRUSES_wastewater","edf730c2773cb1779cee0bde291ca3ac2dfc8e152ff850f8144f460fa67aa628",8],["Data/RESPVIRUSES_wastewater (2)","data/reference/RESPVIRUSES_wastewater","edf730c2773cb1779cee0bde291ca3ac2dfc8e152ff850f8144f460fa67aa628",8],["Data/RESPVIRUSES_wastewater (3)","data/reference/RESPVIRUSES_wastewater","edf730c2773cb1779cee0bde291ca3ac2dfc8e152ff850f8144f460fa67aa628",8],["Data/SHIGELLOSIS_oblig","data/reference/SHIGELLOSIS_oblig","2b174430a3e57521f057b0f449b9f1ae56181f148ea80ec42e50921b7ee32879",9]],"entry_action":"superseded_by_canonical_release","entry_columns":["legacy","canonical","legacy_pair_sha256","legacy_duplicate_group"],"generated_from_commit":"1aeb1a1414bcbf94ae8acf8288565f5edf21cf71","hash_definition":"sha256(hex(data.csv sha256) + hex(metadata.json sha256))","legacy_dataset_directories":37,"legacy_exact_duplicate_groups":9,"legacy_redundant_copies":17,"legacy_root":"Data","legacy_snapshot_id":"f1484622df74831453d66fb36cfc9fab002bd0695385195143930328d4f74653","legacy_unique_byte_pairs":20,"schema_version":1,"unmapped_legacy_directories":0}


## Original record: docs/phase-4-legacy-removal.json

{
  "schema_version": 1,
  "phase": 4,
  "action": "remove_frozen_legacy_data_root",
  "legacy_root": "Data",
  "canonical_root": "data/reference",
  "migration_manifest": "docs/phase-3-data-migration.json",
  "legacy_snapshot_id": "f1484622df74831453d66fb36cfc9fab002bd0695385195143930328d4f74653",
  "canonical_snapshot_id": "d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee",
  "legacy_dataset_directories": 37,
  "legacy_files_removed": 74,
  "unmapped_legacy_directories": 0,
  "precondition": "Phase 3 canonical-root builds passed for push and pull_request",
  "deletion_commit": "d3e25a224c39dfef0e6c9a843e0d2c19ee213b0c",
  "source_main_commit": "3408ff6bed35038a16adbcd74da5793a0c31ae4a",
  "recovery": "Restore from Git history only to an explicitly archival path; do not recreate Data as an active input root.",
  "scientific_note": "The canonical root is a newer source release, not a byte-identical rename. Scientific differences remain documented in the Phase 3 migration manifest."
}


## Original record: docs/phase-5-multi-audience-reports.md

# Phase 5 — multi-audience reports

## Scope

Generate researcher, operational (health institution) and public interactive HTML reports from one shared report source, differentiated only by stakeholder parameter files, with machine-readable provenance in every output.

Out of scope, unchanged: packaging refactors, scientific calculations, source data, historical files (`public_health_expert.json` and `example_output/` are retained).

## Design decisions

- **One template.** `scripts/health_pipeline/report_public_health_expert.qmd` (plus the shared `methods.qmd` companion and R helpers) renders every audience. Snakefile declares it once as `SHARED_TEMPLATE`.
- **Three parameter files.** `researcher.json` (`technical`/`full`), `health_institution.json` (`dashboard`/`monitoring`), `public.json` (`editorial`/`plain_language`). They differ in `title`, `question`, `outputs` and `presentation` only.
- **Identical analytic parameters.** All three use the analytic settings of the historical `public_health_expert` profile. The analysis tables (`metrics.csv`, `series.csv`, `lineage.csv`, `selection.csv`) are byte-identical across audiences, and `metrics.csv` matches the Phase 3 canonical hash `e4e37ba8…`. Findings therefore agree across audiences; only communication differs.
- **Operational geography.** The schema supports `CH` or `CHFL` national totals only. Canton-level series exist for some diseases but not all selected ones, so no canton subset was invented. A `CH` scope was tested: influenza has no complete CH-level 2019 baseline and is excluded, changing the viral headline from +124% to −3%. Because that difference is a data-availability artefact, not a scope choice, `CHFL` is kept for all audiences and the limitation is stated in the monitoring summary.
- **Uncertainty is translated, not hidden.** Every audience shows quality-check counts (PASS/WARN/SKIP/FAIL), limitations and provenance. The operational brief flags small numbers (< 20 cases in either year; a display rule, not a statistical test). The public report adds a plain-language “How sure can we be?” section, including the influenza sensitivity comparison.
- **Provenance.** `publish.py` writes `provenance.json` (HTML) and `provenance.pdf.json` (PDF) beside each report and embeds the HTML record as `<script type="application/json" id="report-provenance">`. See README “Provenance format”.
- **Interactivity.** Dependency-free script: every report table can be filtered and sorted; documents have contents navigation and expandable details. The Shiny app remains the fully reactive option.
- **Selected-report compatibility.** `render_selected.py` and `src/artifact_download.py` use the `researcher` lineage bundle and fall back to `public_health_expert` for artifacts built before Phase 5.

## Acceptance gate

- `python -m pytest -q` passes, including `tests/test_audiences.py` (three audiences enabled, schema-valid, distinct presentations, shared analytic parameters, single shared template, canonical data root, provenance wiring and record contents, lineage fallback).
- `snakemake -n` resolves 3 × (analyse, render_html, render_pdf, package_shiny) from `data/reference/`.
- Full `snakemake --cores 2` builds HTML, PDF, Shiny packages and `release.json`.
- `python scripts/health_pipeline/check_outputs.py` confirms exactly three audience HTML reports with embedded and sidecar provenance.
- `tests/shiny_smoke.R` and `tests/dashboard_smoke.R` pass against `results/reports/researcher/app`.


## Original record: docs/phase-6-ci-hardening.md

# Phase 6 — CI hardening and release gates

## Scope

Make a release impossible to publish unless tests and the three-audience build pass, and make
every uploaded artifact verifiable against its recorded hashes and provenance. No change to
data, scientific calculations or report content.

## CI jobs (`.github/workflows/validate.yml`, on push and pull_request)

| Job | Needs | Gate |
|---|---|---|
| `fast` | — | `ruff check .` (pinned in `scripts/ci/requirements-lint.txt`), `python -m pytest -q` (unit, schema, audience, environment and CI contract tests), `snakemake --dry-run` |
| `secrets` | — | Full-history scan with gitleaks 8.30.1, downloaded and SHA-256 verified by `scripts/ci/secret_scan.sh` |
| `container` | `fast` | `docker build` of the `Dockerfile`, then a smoke run of its default command (`uv sync --locked`, Quarto and Marimo versions) |
| `full` | `fast` | Full `snakemake --cores 2`; `check_outputs.py`; `verify_release.py`; Shiny and dashboard smoke tests; rebuild dry run must report “Nothing to be done”; upload of `results/` only after all of these succeed (`if-no-files-found: error`) |

`refresh-idd-data.yml` runs the same output and release verification before uploading the
lineage artifact consumed by the selected-report UI.

## Release verification (`scripts/health_pipeline/verify_release.py`)

- Every artifact hash in `release.json` matches the file on disk; every produced file is recorded.
- Each audience's `provenance.json` and `provenance.pdf.json` bundle hashes match `data/`; the
  shared-template and parameter hashes match the source files.
- The provenance embedded in each HTML page equals its `provenance.json` sidecar.
- Every local link and asset in rendered HTML resolves, including `#anchor` targets; pages load no
  remote scripts, stylesheets or images. External hyperlinks are not fetched (CI must not depend
  on third-party availability).

`tests/test_ci_contract.py` proves the verifier rejects tampered artifacts, unrecorded files,
tampered bundles, broken links, missing anchors, remote assets and embedded-provenance drift.

## Supply chain

- All actions in all workflows are pinned to full commit SHAs with a version comment; a test
  rejects tag references. `.github/dependabot.yml` proposes weekly grouped updates.
- Ruff, gitleaks, TinyTeX and Quarto are version-pinned; downloaded binaries are checksum-verified.
- Ruff enforces pyflakes and syntax rules (`E9`, `F`) only; formatting is not enforced to avoid a
  repository-wide rewrite. Stricter rules can be enabled incrementally.

## Branch protection guidance (repository admin; not set by code)

Protect `main` (Settings → Branches, or a ruleset):

- Require a pull request before merging, with at least one approving review; dismiss stale approvals.
- Require status checks to pass and the branch to be up to date: `fast`, `secrets`, `container`, `full`.
- Block force pushes and deletion; include administrators.

Equivalent API call (adjust reviewers as needed):

```sh
gh api -X PUT repos/LarsEBaumann/Health_Report_Generator/branches/main/protection \
  -H "Accept: application/vnd.github+json" --input - <<'JSON'
{"required_status_checks":{"strict":true,"contexts":["fast","secrets","container","full"]},
 "enforce_admins":true,
 "required_pull_request_reviews":{"required_approving_review_count":1,"dismiss_stale_reviews":true},
 "restrictions":null,"allow_force_pushes":false,"allow_deletions":false}
JSON
```

The selected-report and data-update workflows keep `ref: main`, so they only ever build protected code.

## Acceptance gate

- `ruff check .`, `python -m pytest -q` and `snakemake --dry-run` pass.
- Full build, `check_outputs.py`, `verify_release.py`, Shiny and dashboard smoke tests pass; rebuild is a no-op.
- Secret scan reports no leaks.
- On the pull request, all four jobs pass on both push and pull_request events.


## Original record: docs/phase-7-release.md

# Phase 7 — hackathon release documentation

## Scope

Final documentation and release polish. No change to data, scientific calculations or report content.

## Deliverables

- README rewritten as an entry point: purpose, quick start, outputs, architecture diagram, data source and version, headline limitation, documentation index. Detailed material moved, unchanged apart from path fixes, into `docs/reproduction.md`, `docs/scientific-policy.md` and `docs/audiences.md`. The "Tests and release discipline" section is kept as it was.
- New: `docs/architecture.md` (data-flow diagram and design decisions), `docs/limitations.md`, `docs/demo.md`, `docs/release-checklist.md`, `RELEASE_NOTES.md`, `CITATION.cff`.
- `data/README.md`: source, terms (public use with source attribution, per the FOPH IDD data page), acquisition, layout, version location. The project licence is deliberately left to the repository owner.
- `scripts/health_pipeline/run_all.sh` fixed to be the documented thin Snakemake wrapper. It previously defaulted to the retired `data/Data` and ran every stakeholder file through a legacy script.
- Corrected a stale claim that CI never fetches new data; the weekly workflow synchronises from the public API.
- `tests/test_release_docs.py`: relative links and heading anchors resolve; the README names the one command and every configured audience's report path; `run_all.sh` dry-runs all audiences and avoids retired paths; the citation file is valid; data terms and key limitations are stated; headline numbers quoted in the docs match the smoke test.

## Not done (decisions for the maintainer)

- No `LICENSE` file: the licence is the owner's choice.
- No version tag or GitHub release: see `docs/release-checklist.md`.
- `CITATION.cff` uses the GitHub handle as author alias; replace it with full names and add a version and release date when tagging.
- Package refactor and removal of historical prototypes remain out of scope (see limitations).

## Acceptance gate

A fresh clone follows the README quick start and produces the three audience reports with provenance; documentation links resolve; `python -m pytest -q` passes.


