# Contributing

Thank you for improving the Health Report Generator. Changes must preserve reproducibility,
scientific traceability and audience-appropriate communication.

## Development setup

Follow [installation](docs/installation.md) and run commands from the repository root. Use the
production Python lock and the pinned R/Quarto toolchain; do not add a second runtime resolution.

## Before changing code

1. Record whether the change affects data, scientific policy, calculations, presentation,
   provenance or only documentation.
2. Do not edit generated files under `results/`; regenerate through the documented pipeline.
3. Do not delete or deduplicate source data by filename alone. Compare data and metadata content,
   preserve original snapshot identity and document every resolution.
4. Keep analysis and presentation separate: render saved verified results, never recompute
   scientific results in the presentation layer.

## Validation

Run the checks relevant to the change:

```sh
pip install -r scripts/ci/requirements-lint.txt
ruff check .
python -m pytest -q -m "not report_runtime"
snakemake --dry-run --cores 1
```

A complete check also needs the report image (R, Quarto, TinyTeX):

```sh
python -m pytest -q                      # includes the report_runtime group
snakemake --cores 2
python scripts/health_pipeline/check_outputs.py
python scripts/health_pipeline/verify_release.py --out results
Rscript tests/shiny_smoke.R results/reports/researcher/app
Rscript tests/dashboard_smoke.R results/reports/researcher/app
bash scripts/ci/secret_scan.sh .         # Linux x86_64; downloads pinned gitleaks
```

Report which commands you ran and which you did not. Source inspection is not runtime acceptance.

## Change rules

- Add or update tests for calculations, selection, schemas and provenance.
- Reject unknown configuration keys rather than silently ignoring them.
- Preserve explicit SKIP, WARN and FAIL meanings, and never convert missing to zero unless the
  scientific policy defines it.
- Do not describe descriptive changes as causal effects or significance.
- Every audience keeps limitations, exclusions, source, filters and generation metadata.
- Update dependency locks deliberately, with the declaration they come from.
- Pin GitHub Actions to full commit SHAs with version comments.
- Preserve historical evidence, licences and attribution.
- Do not reintroduce a retired route or renderer without a versioned decision and its own tests.

## Pull requests

Keep PRs independently reviewable. Include purpose and scope, user-visible and scientific impact,
commands and outcomes, known limits and follow-ups, and the affected stages/routes with base and
candidate identities. Intentional scientific or schema changes need explicit versioned decisions,
not weakened tests.

Documentation changes must identify unchanged runtime/data/calculations/dependencies and keep links
resolving (`tests/test_docs_contract.py`, `tests/test_release_docs.py`). A written CI policy is not
an installed branch-protection gate. Structural cleanup, data migration, scientific-policy changes
and report redesign should stay separate PRs where possible. Release and publication remain separate
maintainer decisions.
