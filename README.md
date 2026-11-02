# Reproducible infectious-disease reports

One open Swiss data source, three audiences, one command. This project turns Federal Office of
Public Health (FOPH) [Infectious Diseases Dashboard](https://www.idd.bag.admin.ch/) exports into
interactive HTML and PDF reports for researchers, health institutions and the public. Report
rendering uses R and Quarto from one shared source; audiences differ only by parameter files, and
every output carries machine-readable provenance, uncertainty context and limitations.

This tree is the **release candidate on branch `release/composer-r`** of the sandbox repository
`LarsEBaumann/composer-sandbox`. It is not the final public distribution repository, and a branch
name is not acceptance. Upstream attribution and citation are preserved in [CITATION.cff](CITATION.cff).

## What is supported

| Route | Command | Outputs |
|---|---|---|
| Canonical pipeline | `snakemake --cores 2` | three audiences × (report + methods HTML, report + methods PDF, packaged Shiny app), `release.json` |
| Supplied-table CLI | `tabular_run.py build` | three audiences × (report + methods HTML) |
| Local composer | `src/composer_site.py` | one composed HTML report package per render, with download |
| Composed batch (HTML) | `publish.py batch` | per-audience composed HTML from retained bundles |
| Custom request | `custom_report.py` | one HTML report from a saved request |
| Verification | `check_outputs.py`, `verify_release.py` | pass/fail, no rendering |

Formats are not interchangeable across routes: the supplied-table, composer and composed-batch
routes are HTML-only; PDF and packaged Shiny apps are produced by the canonical pipeline.

## Quick start (Docker, Linux/amd64)

No GitHub token, fork, Actions run or host Python/R/Quarto/TinyTeX installation is required.
Initial software setup requires internet; report generation reads the committed data and does not
fetch new IDD data.

```sh
git clone https://github.com/LarsEBaumann/composer-sandbox.git
cd composer-sandbox
git switch release/composer-r
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
docker compose build report
docker compose run --rm report snakemake --cores 2
```

One command builds every audience listed in `workflow/config.yaml`. Open:

```text
results/reports/researcher/report.html
results/reports/health_institution/report.html
results/reports/public/report.html
```

Keep each complete `results/reports/<audience>/` folder together: report pages link to methods
pages, analysis data, provenance sidecars and the packaged app.

Verify the build:

```sh
docker compose run --rm report python scripts/health_pipeline/check_outputs.py
docker compose run --rm report python scripts/health_pipeline/verify_release.py --out results
```

The native wrapper `bash scripts/health_pipeline/run_all.sh` runs the same command in a configured
native environment. See [installation](docs/installation.md).

## What you get

| Audience | Report | Purpose |
|---|---|---|
| researcher | `results/reports/researcher/report.html` | parameters, coverage, QC, methods and reproduction |
| health_institution | `results/reports/health_institution/report.html` | descriptive monitoring, count changes, small-number cautions and quality |
| public | `results/reports/public/report.html` | plain language, readable provenance and uncertainty |

All three share identical analytic parameters, so findings agree; only communication differs. The
viral change versus 2019 (+124%) becomes -3% excluding influenza, and every report shows both. See
[report generation](docs/report-generation.md) for routes, composition recipes and examples, and
[scientific policy](docs/report-generation.md#methods-and-scientific-policy) for the analysis rules.

## Versions, data and provenance

- Toolchain policy: `workflow/toolchain.json` (Python 3.11.6, R 4.3.2, Quarto 1.3.353, uv 0.8.14,
  TinyTeX 2026.10).
- Python orchestration lock: `scripts/health_pipeline/requirements.lock.txt`; R packages:
  `renv.lock`; environment declaration: `workflow/environment.yml`; lint tool:
  `scripts/ci/requirements-lint.txt`.
- Data: committed FOPH exports under `data/reference/`, each with `retrieval.json` (source URL,
  retrieval time, hashes). Attribution and terms: [data/README.md](data/README.md).
- Every report embeds a machine-readable provenance record (source, snapshot id, filters,
  effective parameters, software versions, generation timestamp) and writes a sidecar;
  `results/release.json` records artifact hashes, Git state and runtime versions.

Details and verification: [reproducibility](docs/reproducibility.md).

## Documentation

- [Installation and setup](docs/installation.md)
- [Report generation](docs/report-generation.md)
- [Local composer](docs/composer.md)
- [Reproducibility and provenance](docs/reproducibility.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Limitations](docs/limitations.md)

Release notes: [RELEASE_NOTES.md](RELEASE_NOTES.md). Contribution rules: [CONTRIBUTING.md](CONTRIBUTING.md).
Pipeline schema notes: [scripts/health_pipeline/SCHEMA.md](scripts/health_pipeline/SCHEMA.md).

## Licence, attribution and citation

The software is MIT-licensed ([LICENSE](LICENSE)). The source data remain under the publisher's
terms; the MIT licence does not license the data — attribute the FOPH when redistributing reports
or data. Cite this software and the data source as described in [CITATION.cff](CITATION.cff).

## Uncertainty and scope

These are descriptive reports of officially notified cases, not infection incidence. There are no
significance tests, confidence intervals or causal claims. Recent years may be revised, small
numbers swing widely, and the data cannot explain the influenza effect. See
[limitations](docs/limitations.md) before using any number outside the report's own framing.
