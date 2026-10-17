# Health report pipeline

See the [repository README](../../README.md) for setup, Snakemake targets, reproducibility, quality policy and outputs.

The processing stages are `inventory.py`, `harmonise.py`, `checks.py`, `analyse.py`, `publish.py`, and `release.py`. `report.py` is a compatibility entry point using the same analysis and QMD. It requires a successfully validated output directory. `mock_test.py` now runs the correctness regression suite; it no longer labels merely surviving damaged input as a pass.

`report_public_health_expert.qmd` is a generic presentation template despite its historical filename. The workflow copies it as `report.qmd` beside the validated CSVs and shared R helpers in each app bundle. Render that packaged copy, not this source file without its data.

Schema and lineage: [SCHEMA.md](SCHEMA.md).

## Importing a CSV or TSV file

The optional tabular importer accepts a UTF-8 CSV or TSV file with arbitrary
column names. Inputs may contain a time field for time-series reporting, or
omit time entirely for a dated snapshot. A mapping file identifies the
category and numeric value columns when the generic input path is used.

The importer creates the dataset-folder layout used by the pipeline:

```text
data/imported/<filename>/
├── data.csv
└── metadata.json
```

Run it explicitly from the repository root:

```bash
python scripts/health_pipeline/ingest_tabular.py \
  path/to/input.csv \
  --output-root data/imported
```

Use a `.tsv` filename for tab-separated input. The importer validates the
header and row widths, records the delimiter, row and column counts, import
time, and input SHA-256 in `metadata.json`. For a snapshot, it records an
explicit snapshot period and does not imply that the values form a time
series. It does not change the existing IDD source tree under
`data/reference/` and is not part of the default Snakemake build yet.
