# Reproducible infectious-disease reports

One open Swiss data source, three audiences, one command. This project turns Federal Office of Public Health (FOPH) [Infectious Diseases Dashboard](https://www.idd.bag.admin.ch/) exports into interactive HTML reports for researchers, health institutions and the public. Shared Quarto source and audience parameter files retain machine-readable provenance, uncertainty and limitations. Built for the hackathon challenge One Data Source, Many Audiences.

## Workflow preservation and development status

The [mandatory data-workflow preservation policy](docs/workflow-preservation-policy.md) applies throughout every development stage. The [Track B plan](docs/integration-plan.md) describes the future unified workspace, not shipped UI behavior. Active integration is integration/steward-ready-v1; feature branches PR back there. Track A remains frozen. [Conflict dispositions](docs/b0-conflict-dispositions.md) distinguish current routes from historical guidance and targets. A policy document does not install CI enforcement or prove a new runtime pass.

## Quick start

Recommended local path: Docker Compose on Linux/amd64. No GitHub token, fork, Actions or host Python/R/Quarto/TinyTeX installation is required. Initial software setup requires internet.

```sh
git clone https://github.com/ODESA-OpSciHack26/Health_Report_Generator.git
cd Health_Report_Generator
# To reproduce the integration line rather than the default branch:
git checkout integration/steward-ready-v1
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
docker compose build report
docker compose run --rm report snakemake --cores 2
```

For acceptance, check out the exact recorded candidate before testing. The report image uses Dockerfile.report; the optional connector UI uses Dockerfile. workflow/toolchain.json declares runtime versions. Builds read committed data/reference/ without fetching new IDD data. Acquisition is separate.

Open results/reports/public/report.html. Keep each complete results/reports/<id>/ folder together for links/downloads. Verify:

```sh
docker compose run --rm report python scripts/health_pipeline/check_outputs.py
docker compose run --rm report python scripts/health_pipeline/verify_release.py --out results
```

With the native pipeline/rendering environment configured, the one-command wrapper remains:

```sh
bash scripts/health_pipeline/run_all.sh
```

See [GETTING_STARTED.md](GETTING_STARTED.md) for native setup and diagnostics.

## What you get

| Audience | Report | Purpose |
|---|---|---|
| researcher | results/reports/researcher/report.html | Parameters, coverage, QC, methods and reproduction |
| health_institution | results/reports/health_institution/report.html | Descriptive monitoring, count changes, small-number cautions and quality |
| public | results/reports/public/report.html | Plain language, readable provenance and uncertainty |

Canonical audience folders also hold methods.html, PDFs, provenance.json (embedded in HTML too), analysis data and a Shiny app. results/release.json records artifact/code hashes, Git state and runtime versions. See [audiences](docs/audiences.md).

For existing canonical IDD audiences, copy a stakeholder file in scripts/health_pipeline/config/stakeholders/, change its validated communication settings and list its ID in workflow/config.yaml. No audience-specific QMD is needed. Standard release audiences retain matching analytical scope. This is not a claim that a dynamic generic registry, composer or arbitrary new method is shipped.

## Local and GitHub-backed interfaces

The optional [host-local Marimo form](docs/local-interface.md), for trusted Linux/WSL use, selects an audience/year range and invokes Docker plus the custom-report cache. It needs host uv and Docker Compose, but no GitHub account/token/fork/Actions. It offers three standard profiles plus the retained public-health-expert profile as custom reports.

The [GitHub-backed Marimo interface](CONNECTOR_SETUP.md) is separate: it uses a fork, token and Actions; each request renders from scratch without the custom-report cache. Neither interface is the target unified upload/interpretation/composer workspace.

## Custom reports

Copy a stakeholder settings file such as public.json, edit supported fields and submit it. Invalid requests stop before rendering with Invalid request: ... . Example:

```sh
docker compose run --rm report python scripts/health_pipeline/custom_report.py \
  examples/request-2022-2025.json --out results/custom
```

The last line reports cache miss or cache hit, a SHA-256 key and folder. Cache entries live in results/cache/custom_reports/. The key covers request, data snapshot, report code, toolchain and schema version. Identical requests reuse original provenance/render time; request/data/template changes create a new key. This machine-local cache has no eviction; deleting results/cache/ causes rerendering. Both custom_report.py and the host-local adapter use this path; the GitHub-backed form does not.

Warning: --out is replaced on each run. Preserve an earlier output or select a fresh disposable destination. New unified no-replace publication is a target, not a claim that this legacy behavior has changed. Outputs include report.html, methods.html, provenance.json and request_provenance.json with effective filters, parameters, cache components/code hash and rendered_utc. Custom reports are outside results/release.json.

A request copied from public.json retains reference_year/index_base_year 2019, even when displayed years are 2022-2025. Change both fields explicitly for another baseline.

## How it works

Separate API acquisition -> captured source/metadata -> content-addressed snapshot -> harmonisation -> blocking quality gate -> Python analysis/results/lineage -> verified bundles -> shared Quarto/R presentation -> provenance and exact release verification. Snakemake may invoke analysis per audience; presentation never independently recalculates scientific results. See [architecture](docs/architecture.md).

## Data source and interpretation limits

FOPH IDD CSV exports use https://api.idd.bag.admin.ch/api/v1/export/latest/<DATASET>/csv and are committed in data/reference/ with retrieval.json (URL, retrieval time, SHA-256). The publisher updates weekly on Wednesdays. Reports identify the actual captured snapshot, publisher release dates and retrieval dates. Attribute Federal Office of Public Health (FOPH/BAG), Infectious Diseases Dashboard; see [data terms](data/README.md). Software is [MIT](LICENSE); this does not license source data.

Canonical reports describe notified cases, not all infections; comparisons are descriptive, not significance tests or causal claims. Scope is national Switzerland plus Liechtenstein, not canton-level or seasonal alert analysis. Aggregation choices matter: the viral increase versus 2019 (+124%) becomes -3% excluding influenza. Preserve these caveats; see [limitations](docs/limitations.md).

## Optional supplied-table reports

The default canonical workflow is unchanged. An explicitly mapped synthetic CSV can generate three verified HTML audience reports:

```bash
docker compose run --rm --no-deps report python scripts/health_pipeline/tabular_run.py build --input examples/tabular/observations.csv --request examples/tabular/request.json --output reproduced/tabular-example
```

See [tabular reproduction](docs/m4-tabular-reproduction.md) for setup, checksum-pinned requests, outputs and verification, plus the [browser review checklist](docs/m4-browser-review.md). Current supported generic shape is one category, one measure and optional time in explicitly mapped CSV/TSV. No upload UI is enabled. Generic HTML does not imply PDF/apps. Guided interpretation, actual generic selection controls, multiple-measure/ungrouped extensions, dynamic composition and per-block inspectors remain staged targets.

## Tests, provenance and release discipline

```sh
ruff check .
python -m pytest -q
snakemake --dry-run --cores 1
# after a full build
python scripts/health_pipeline/check_outputs.py
python scripts/health_pipeline/verify_release.py --out results
Rscript tests/shiny_smoke.R results/reports/researcher/app
```

Tests cover scientific/QC boundaries, incomplete periods/baselines, denominators, metadata/overlap conflicts, CLI failures, stale gates, snapshot tampering/relocation, deterministic tables and independent fixture reconstruction. An unchanged successful build should have a no-work dry run.

CI has fast, secrets, container and full gates; see [phase 6](docs/phase-6-ci-hardening.md). Release bundles are uploaded only after full checks succeed; CI does not deploy a production site. Failed builds can leave older reports: only a completed build and matching release.json define a release. Preserve earlier accepted artifacts separately. Historical green checks are not a test of a later merge commit.

The production Python lock is scripts/health_pipeline/requirements.lock.txt; uv.lock covers optional Marimo/connector dependencies; renv.lock records R dependencies; workflow/toolchain.json governs runtime policy. workflow/environment.yml is a convenience environment, not another authoritative lock. See [dependency ownership](docs/dependency-ownership.md).

## Documentation and handover

- [Documentation index](docs/README.md), [integration plan](docs/integration-plan.md), [contracts](docs/integration-contracts.md), [technical data workflow](docs/data-workflow.md), [steward workspace](docs/steward-workspace.md).
- [Architecture](docs/architecture.md), [audiences](docs/audiences.md), [reproduction](docs/reproduction.md), [scientific policy](docs/scientific-policy.md), [schema](scripts/health_pipeline/SCHEMA.md).
- [Limitations](docs/limitations.md), [demo](docs/demo.md), [release notes](RELEASE_NOTES.md), [release checklist](docs/release-checklist.md).
- [Repository map](docs/repository-map.md), historical docs/phase-*.md, [contributing](CONTRIBUTING.md), [setup](GETTING_STARTED.md), [connector setup](CONNECTOR_SETUP.md).
- [Handover](docs/handover.md) preserves baseline evidence and tested identities; it does not accept the future combined product. Cite using [CITATION.cff](CITATION.cff).

Release, tags, deployment, branch protection and evidence distribution require separate maintainer decisions. This documentation patch neither closes B0 nor supplies fresh runtime/browser/scientific acceptance.
