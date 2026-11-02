# Release notes

## release/composer-r — release candidate (not accepted)

This branch is a release candidate for the R-based Composer product. It is not accepted, not
tagged and not deployed; a branch name is not acceptance, and no GitHub Actions run for this
candidate is recorded here.

### Supported product

- Canonical pipeline: `snakemake --cores 2` (or `run_all.sh`) renders researcher,
  health_institution and public reports from one shared Quarto source and audience parameters,
  producing HTML, PDF, provenance sidecars, packaged Shiny apps and `results/release.json`.
- Supplied-table CLI: `tabular_run.py build` renders the same three audiences to HTML from one
  explicitly mapped CSV/TSV with a checksum-pinned request.
- Local composer: `src/composer_site.py` serves the composition editor, renders one HTML report
  package at a time and offers the report download.
- Composed batch (`publish.py batch`), custom reports (`custom_report.py`), and verification
  (`check_outputs.py`, `verify_release.py`) remain available as documented.

Report rendering uses R and Quarto. Python orchestrates acquisition, harmonisation, analysis,
validation and provenance; it does not render reports.

### Changes in this candidate

- **Pilot separation.** The experimental Python tabular renderer, its pilot dependency locks, its
  Dockerfile, its CI job and enforcement checker, its tests and its documentation are no longer part
  of the release tree. They remain available in the preserved history of this repository.
- **Renderer option.** `--renderer` remains accepted by the supplied-table CLIs with `r` as the only
  supported value and the default. `--renderer python` fails with an explicit argparse error; there
  is no silent fallback.
- **Existing pilot artifacts.** Reports produced by the retired Python renderer
  (`health-report/tabular-render/2`) can still be integrity-verified offline. Their recorded source
  cannot be verified from this checkout and this release cannot regenerate them; `--verify-source`
  says so explicitly.
- **Retired routes.** The GitHub-backed selected-report entry point, its workflow and its route-only
  configuration are removed. Shared audience configuration is retained, including the historical
  `public_health_expert` analytic base profile used by audience tests.
- **Handover utilities.** `report.py`, `mock_test.py`, `check_tabular_handover.py`,
  `watch_and_open_report.sh` and the legacy `data/archive/lyme_sentinella_legacy/` dataset are
  removed after confirming no supported caller. `evidence_archive.py` is retained as a
  renderer-independent archive/verify tool for result sets.
- **Documentation.** Seven user documents replace the development diary set: README,
  installation, composer, report-generation, reproducibility, troubleshooting and limitations.
  Machine-readable data migration/removal audit records are retained unchanged.
- **CI.** The `rfree-pilot` job and the `quarto_runtime` marker are gone; the fast job excludes only
  `report_runtime`, the container job runs the complete suite and the mandatory `report_runtime`
  group. Intended required checks are `fast`, `secrets`, `container`, `full`.

### Versions

Python 3.11.6, R 4.3.2, Quarto 1.3.353, uv 0.8.14, TinyTeX 2026.10 — policy in
`workflow/toolchain.json`. Python lock: `scripts/health_pipeline/requirements.lock.txt`; R
resolution: `renv.lock`.

### Known limitations and terms

See [limitations](docs/limitations.md). Reports describe notified cases, not infections; comparisons
are descriptive; recent years can be revised. The software is [MIT](LICENSE)-licensed; the licence
does not cover the source data. Data: FOPH/BAG Infectious Diseases Dashboard, with separate
[data terms](data/README.md) and attribution.

Composer acceptance remains scoped: no broad browser, accessibility, clinical or deployment
acceptance is claimed. Release, tags, deployment and branch protection are separate maintainer
decisions.
