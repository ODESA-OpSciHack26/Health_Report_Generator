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
time. It runs natively, not in Docker. Run from the repository root.

1. Create the Python environment:

   ```sh
   uv venv --python 3.11.6 .venv-pipeline
   uv pip install --python .venv-pipeline/bin/python -r scripts/health_pipeline/requirements.lock.txt
   ```

2. Build the audience data bundles it reads (Python only, about a minute):

   ```sh
   .venv-pipeline/bin/python -m snakemake tables --cores 2
   ```

3. Start it:

   ```sh
   .venv-pipeline/bin/python src/composer_site.py \
     --work-root "$HOME/.local/state/health-report-composer" \
     --inputs-root results/reports --data-root data/reference
   ```

4. Open `http://127.0.0.1:2719/?token=<token>`, where `<token>` is the contents of
   `$HOME/.local/state/health-report-composer/access-token.txt`. The Researcher, Health institution
   and Public presets should show as available. Stop with `Ctrl+C`.

Generating a report from the composer also needs R packages (`Rscript workflow/restore_r.R`) and
Quarto 1.3.353, see [installation](docs/installation.md#alternative-native-environment). Token
handling, options, the CSV workflow and limitations: [composer](docs/composer.md).

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
