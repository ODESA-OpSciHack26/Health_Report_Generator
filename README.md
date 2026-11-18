# Reproducible infectious-disease reports

One open Swiss data source, three audiences, one command. This project turns Federal Office of
Public Health (FOPH) [Infectious Diseases Dashboard](https://www.idd.bag.admin.ch/) exports into
interactive HTML and PDF reports for researchers, health institutions and the public. Rendering uses
R and Quarto from one shared source; audiences differ only by parameter files, and every output
carries machine-readable provenance, uncertainty context and limitations.

Release candidate `v2.0.0-rc.1` (branch `release/v2.0.0-rc.1`), not yet accepted. Citation:
[CITATION.cff](CITATION.cff).

**Choose your path**

| I want to… | Go to |
|---|---|
| Build all three audience reports | [Quick start](#quick-start) |
| Compose a report in the browser | [Run the composer](#run-the-composer) |
| See every route and output format | [Other routes](#other-routes) |
| Check versions, data and provenance | [Reproducibility](#reproducibility) |

## Quick start

Build all reports with Docker (Linux/amd64). No host Python, R, Quarto or TeX is needed; the build
step needs internet, report generation does not.

```sh
git clone https://github.com/ODESA-OpSciHack26/Health_Report_Generator.git
cd Health_Report_Generator
git switch release/v2.0.0-rc.1
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose build report
docker compose run --rm report snakemake --cores 2
```

Open the reports (keep each `results/reports/<audience>/` folder together):

```text
results/reports/researcher/report.html
results/reports/health_institution/report.html
results/reports/public/report.html
```

Verify:

```sh
docker compose run --rm report python scripts/health_pipeline/check_outputs.py
docker compose run --rm report python scripts/health_pipeline/verify_release.py --out results
```

Without Docker, set up the native environment from [installation](docs/installation.md) and run
`bash scripts/health_pipeline/run_all.sh`.

## Run the composer

The composer is a local browser app (`src/composer_site.py`) for composing one report package at a
time. It runs natively, not in Docker. Run all commands below from the repository root.

Opening the interface requires Python; generating reports also requires native R, the restored
project R packages, and Quarto. Building the Docker report image does not install these tools on
your host.

### 1. Install the native prerequisites

Follow [native installation](docs/installation.md#alternative-native-environment) to install the
toolchain specified in `workflow/toolchain.json`, including R 4.3.2, Quarto 1.3.353 and uv.

### 2. Restore the Python and R environments

```sh
uv venv --python 3.11.6 .venv-pipeline
uv pip install --python .venv-pipeline/bin/python -r scripts/health_pipeline/requirements.lock.txt
Rscript workflow/restore_r.R
```

The R restoration uses `renv.lock` and installs the project library under `.r-library`.
Do not substitute individual latest-version package installations.

### 3. Configure and check rendering

Run these commands in the same terminal used to start the composer:

```sh
export HEALTH_REPORT_PROJECT="$PWD"
export HEALTH_REPORT_R_LIBRARY="$PWD/.r-library"
export R_PROFILE_USER="$PWD/.Rprofile"

Rscript -e 'library(knitr); library(rmarkdown)'
quarto --version
quarto check knitr
```

Confirm that Quarto matches the specified version, detects `knitr` and `rmarkdown`, and passes the
Knitr engine render check. Resolve failures before starting the application. Repeat the exports
when launching from a new terminal.

### 4. Prepare the audience inputs

```sh
.venv-pipeline/bin/python -m snakemake tables --cores 2
```

### 5. Start the application

```sh
.venv-pipeline/bin/python src/composer_site.py \
  --work-root "$HOME/.local/state/health-report-composer" \
  --inputs-root results/reports --data-root data/reference
```

Keep this terminal running. In another terminal, print the local access URL:

```sh
printf 'http://127.0.0.1:2719/?token=%s\n' \
  "$(cat "$HOME/.local/state/health-report-composer/access-token.txt")"
```

Open the printed URL in your browser. Keep the token private; do not include it in shared logs,
screenshots or issues. The Researcher, Health institution and Public presets should show as
available.

Generate one report to confirm the complete workflow, not just that the interface opens.
Stop with `Ctrl+C`. Stopping the application does not require deleting its working state.

Token handling, options, the CSV workflow and limitations: [composer](docs/composer.md).
For failures, see [troubleshooting](docs/troubleshooting.md).

## What you get

| Audience | Report | Purpose |
|---|---|---|
| researcher | `results/reports/researcher/report.html` | parameters, coverage, QC, methods and reproduction |
| health_institution | `results/reports/health_institution/report.html` | descriptive monitoring, count changes, small-number cautions |
| public | `results/reports/public/report.html` | plain language, readable provenance and uncertainty |

All three share the same analytic parameters, so findings agree; only communication differs. The
viral change versus 2019 (+124%) becomes -3% excluding influenza, and every report shows both.

## Other routes

| Route | Command | Outputs |
|---|---|---|
| Canonical pipeline | `snakemake --cores 2` | per audience: report + methods HTML and PDF, Shiny app; `release.json` |
| Local composer | `src/composer_site.py` | one composed HTML report package per render |
| Supplied-table CLI | `tabular_run.py build` | per audience: report + methods HTML |
| Composed batch | `publish.py batch` | per-audience composed HTML from retained bundles |
| Custom request | `custom_report.py` | one HTML report from a saved request |
| Verification | `check_outputs.py`, `verify_release.py` | pass/fail, no rendering |

Only the canonical pipeline produces PDF and Shiny apps; the others are HTML-only. Details and
recipes: [report generation](docs/report-generation.md).

## Reproducibility

- Versions: `workflow/toolchain.json` (Python 3.11.6, R 4.3.2, Quarto 1.3.353, uv 0.8.14, TinyTeX
  2026.10); locks in `scripts/health_pipeline/requirements.lock.txt` and `renv.lock`.
- Data: committed FOPH exports in `data/reference/`, each with `retrieval.json` (source URL,
  retrieval time, hashes). Terms: [data/README.md](data/README.md).
- Provenance: every report embeds and writes a machine-readable record (source, snapshot id,
  filters, parameters, software versions, timestamp); `results/release.json` records artifact
  hashes and Git state.

Details: [reproducibility](docs/reproducibility.md).

## Uncertainty and scope

These are descriptive reports of officially notified cases, not infection incidence. There are no
significance tests, confidence intervals or causal claims. Recent years may be revised and small
numbers swing widely. Read [limitations](docs/limitations.md) before reusing any number.

## More documentation

[Installation](docs/installation.md) · [Report generation](docs/report-generation.md) ·
[Composer](docs/composer.md) · [Reproducibility](docs/reproducibility.md) ·
[Troubleshooting](docs/troubleshooting.md) · [Limitations](docs/limitations.md) ·
[Release notes](RELEASE_NOTES.md) · [Contributing](CONTRIBUTING.md)

The software is MIT-licensed ([LICENSE](LICENSE)); the data remain under FOPH terms and must be
attributed. Cite via [CITATION.cff](CITATION.cff).
