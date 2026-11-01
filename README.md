# Reproducible infectious-disease reports

One open Swiss data source, three audiences, one command. This project turns Federal Office of Public Health (FOPH) [Infectious Diseases Dashboard](https://www.idd.bag.admin.ch/) exports into interactive HTML reports for researchers, health institutions and the public. Shared Quarto source and audience parameter files retain machine-readable provenance, uncertainty and limitations. Built for the hackathon challenge One Data Source, Many Audiences.

## Available reporting routes

- Canonical health reports: generate three audience-specific reports from the
  committed Swiss infectious-disease data using the quick start below.
- [Experimental local composer](docs/composer.md): work with supported CSV inputs
  or prepared health bundles through a separate local browser application.
  Its runtime and input preparation requirements differ from the canonical route.
- [Supplied-table CLI](docs/m4-tabular-reproduction.md): generate three HTML
  reports from an explicitly mapped CSV/TSV.
- Retired local and GitHub-backed forms: see the retirement notices below.

The composer is experimental, not a production release. Its recorded local
acceptance is scoped; it does not establish broad browser/accessibility acceptance,
clinical validity or deployment readiness. Historical candidate identities and
review scope remain in the [composer handoff](docs/build/composer/HANDOFF.md).

The [data-workflow preservation policy](docs/workflow-preservation-policy.md)
continues to apply. Development targets and historical integration decisions are
documented separately in the [integration plan](docs/integration-plan.md) and
[conflict dispositions](docs/b0-conflict-dispositions.md).

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

For acceptance, check out the exact recorded candidate before testing. The report image uses Dockerfile.report; the former UI Dockerfile is retired. workflow/toolchain.json declares runtime versions. Builds read committed data/reference/ without fetching new IDD data. Acquisition is separate.

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

## Report scope and block binding (experimental)

Stakeholder settings accept two optional arrays: `include_topics` (if present, only those topic identifiers are candidates; must be non-empty and valid) and `exclude_topics` (removes topics from the analytical selection). Omitted fields preserve the existing eligibility policy; the two lists may not overlap. Topic identifiers are validated against `scripts/health_pipeline/config/pathogen_class.csv`, and every dataset keeps an explicit selection reason. `exclude_from_group_totals`, `sensitivity_exclude` and `classes_in_main_comparison` keep their separate meanings.

Changing this scope is an analysis change: regenerate the bundle through the canonical workflow (for example `snakemake --cores 2` or `analyse.py` against a validated harmonised output). Rendering a retained bundle only changes presentation. Composed recipes use `health-report/composition-recipe/2`, where `reference-comparison` requires an explicit `topic` bound to a saved included topic; contract v1 remains readable with its historical deterministic binding.

Composed recipes may also include one `series-trend` block (`topic`, `measure`, optional inclusive `years` defaulting to the reporting window, and an optional closed `presentation` object with `style` `standard` or `compact`). It displays saved annual observations for one included topic, leaves a missing year as a gap rather than zero, and refuses a second instance. The style changes figure size and wording only, never the saved rows or the analytical identity. Like the comparison, it only selects among saved results and cannot broaden analytical scope.

A composed recipe may bind one `series-collection` block instead of a single trend: `topics` is `"eligible"` (every included topic in the saved bundle, in topic order) or an explicit non-empty list (author order, which must resolve completely), with one `measure`, optional inclusive `years`, and an optional `{style, default_topic}` presentation. Each topic becomes a separately checked series record and its own native disclosure panel; the default topic is open first, and all panels work without JavaScript. A recipe cannot combine a collection with a single `series-trend` block, and only one collection is allowed. Unknown or excluded topics fail the collection rather than being dropped.

Composed recipes may also include one `coverage-selection` summary of the saved selection decisions, one institutional `monitoring-overview` of each included topic's latest saved value, and one `sensitivity-comparison` of the saved main and sensitivity group specifications. These read saved records only; they add no calculation and no new contract.

## Composed audience reports (experimental, HTML-only)

One command composes all three audience reports from their own retained analysis bundles and audience recipes:

```sh
docker compose run --rm report python scripts/health_pipeline/publish.py batch \
  --bundle-root results/reports --output-root results/composed \
  --data-root /app/results/snapshots/<snapshot-id> \
  --workflow-config workflow/config.yaml
```

`compose.yaml` mounts the repository at `/app`, so these are container paths: a host-expanded `$(pwd)/...` value is not valid inside the container.

Recipes live in `scripts/health_pipeline/config/composer/compositions/<audience>.json` and must declare that audience. The batch refuses a recipe or bundle whose audience does not match instead of substituting another audience's inputs. Outputs are `results/composed/researcher/report.html`, `results/composed/health_institution/report.html` and `results/composed/public/report.html`, each with `methods.html`, `provenance.json` (also embedded in the HTML) and a `data/` folder holding the exact audience parameters, artifact manifest and saved CSVs used by the download links. Keep each folder together so those links resolve. The command exits nonzero if any requested report fails; a partial run may leave the other reports in place, so check the exit status before treating the batch as complete.

This is presentation-only rendering: it re-renders saved bundles and does not re-run acquisition, harmonisation or analysis. Full analysis reproduction remains `snakemake --cores 2`. Composed reports are HTML-only; passing `--composition` with PDF is rejected, and the legacy HTML/PDF route (`snakemake`, or `publish.py html|pdf` without `--composition`) is unchanged. Composed outputs are outside `results/release.json`. The main report links directly to the methods page's `#quality-checks` section, which lists every recorded check result with status, rule and dataset filters plus per-dataset warning explanations; each published artifact is listed with type, size, digest and a direct download in “Report settings and source files”.

## Local and GitHub-backed interfaces

The [experimental local composer](docs/composer.md) has its own service,
local access token and saved working state. It is separate from both
retired Marimo forms described below. See its guide for launch requirements and
current limitations.

The former [host-local Marimo form](docs/local-interface.md) is retired from this product tree. Use the experimental composer for supported browser workflows. The custom-report CLI and its cache remain available; retiring the form does not remove those services.

The former [GitHub-backed Marimo interface](CONNECTOR_SETUP.md) is retired from this product tree. The selected-report CLI and workflow remain available independently. The experimental composer uses a local access credential, not a GitHub token.

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

See [tabular reproduction](docs/m4-tabular-reproduction.md) for setup, checksum-pinned requests, outputs and verification, plus the [browser review checklist](docs/m4-browser-review.md). This supplied-table CLI supports one category, one measure and optional time in explicitly mapped CSV/TSV. It is a command-line route, not the browser upload workflow. See the [experimental composer guide](docs/composer.md) for that separate interface. Generic HTML does not imply PDF/app support, and capabilities must not be inferred across routes.

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

The production Python lock is scripts/health_pipeline/requirements.lock.txt; renv.lock records R dependencies; workflow/toolchain.json governs runtime policy. workflow/environment.yml is a convenience environment, not another authoritative lock. See [dependency ownership](docs/dependency-ownership.md).

## Documentation and handover

- [Documentation index](docs/README.md), [integration plan](docs/integration-plan.md), [contracts](docs/integration-contracts.md), [technical data workflow](docs/data-workflow.md), [steward workspace](docs/steward-workspace.md).
- [Architecture](docs/architecture.md), [audiences](docs/audiences.md), [reproduction](docs/reproduction.md), [scientific policy](docs/scientific-policy.md), [schema](scripts/health_pipeline/SCHEMA.md).
- [Limitations](docs/limitations.md), [demo](docs/demo.md), [release notes](RELEASE_NOTES.md), [release checklist](docs/release-checklist.md).
- [Repository map](docs/repository-map.md), historical docs/phase-*.md, [contributing](CONTRIBUTING.md), [setup](GETTING_STARTED.md), [connector setup](CONNECTOR_SETUP.md).
- [Handover](docs/handover.md) preserves baseline evidence and tested identities; it does not accept the future combined product. Cite using [CITATION.cff](CITATION.cff).

Release, tags, deployment, branch protection and evidence distribution require separate maintainer decisions. This documentation patch neither closes B0 nor supplies fresh runtime/browser/scientific acceptance.
