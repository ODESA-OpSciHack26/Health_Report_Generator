# Health report pipeline

See the [repository README](../../README.md) for setup, Snakemake targets, reproducibility, quality policy and outputs.

The processing stages are `inventory.py`, `harmonise.py`, `checks.py`, `analyse.py`, `publish.py`, and `release.py`. Verification is `check_outputs.py` and `verify_release.py`.

`report_shared.qmd` is the single audience-neutral presentation template. The workflow copies it as `report.qmd` beside the validated CSVs and shared R helpers in each app bundle. Render that packaged copy, not this source file without its data.

Supplied-table rendering (`tabular_prepare.py` → `tabular_bundle.py` → `tabular_render.py`/`tabular_run.py`) uses the same shared source and is documented in [report generation](../../docs/report-generation.md).

Schema and lineage: [SCHEMA.md](SCHEMA.md).
