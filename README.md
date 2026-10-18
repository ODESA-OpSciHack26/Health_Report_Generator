# Local Health Report Generator

Generate audience-specific health reports locally from either:

- the committed IDD dataset; or
- an uploaded CSV/TSV file.

The project runs in Docker. No Python, R, Quarto, TinyTeX, GitHub token, or
GitHub Actions setup is required for local use.

## Start the local interface

```sh
docker compose build report
docker compose --profile ui up ui
```

Open <http://localhost:2718>.

1. Choose an audience.
2. Choose the IDD dataset or upload a CSV/TSV file.
3. Generate the report.
4. Find the run under `results/runs/`.

IDD reports use the validated IDD analysis. Uploaded tables use automatic
descriptive analysis. A CSV/TSV file does not need a mapping file. A detected
date/time column creates a time-series report; otherwise the file is treated
as a snapshot.

## Run the IDD pipeline directly

```sh
docker compose run --rm report snakemake --cores 2
```

The equivalent native wrapper is `bash scripts/health_pipeline/run_all.sh`.
Runtime versions are recorded in `workflow/toolchain.json`.

Reports are written to `results/reports/` with HTML, PDF, provenance, QC,
and editable report sources.

Standard report paths are `results/reports/researcher/report.html`,
`results/reports/health_institution/report.html`, and
`results/reports/public/report.html`.

## Documentation

Read the [Developer and user guide](docs/guide.md) for the complete workflow,
architecture, data rules, outputs, testing, and release checklist.

Technical references: [architecture](docs/architecture.md),
[limitations](docs/limitations.md), [data notes](data/README.md), and
[citation metadata](CITATION.cff).

## Project metadata

- Authors: ODESA OpSciHack26 project team and contributors
- Guide created: 2026-10-18
- Guide last updated: 2026-10-18
- License: see the repository owner’s release decision and `CITATION.cff`
