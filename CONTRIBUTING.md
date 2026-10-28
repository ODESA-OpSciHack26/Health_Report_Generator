# Contributing

Thank you for improving the Health Report Generator. Changes must preserve reproducibility, scientific traceability, and audience-appropriate communication. The [mandatory workflow-preservation policy](docs/workflow-preservation-policy.md) applies throughout development and maintenance.

## Development setup

Follow the root README.md for supported environment and installation commands. Run commands from the repository root.

## Before changing code

1. Track B feature work normally starts from the current integration/steward-ready-v1 tip and PRs back there. For the approved composer isolated integration lane, design/* task branches start from the current build/composer tip and internal PRs target build/composer. Its umbrella draft PR targets integration/steward-ready-v1 and stays unmerged until explicit human promotion approval. See the [build handoff](docs/build/composer/HANDOFF.md). This exception does not bypass permissions/confirmation rules or authorize changes to frozen/main/release refs. Other maintenance targets require a maintainer decision.
2. Record whether the change affects data, scientific policy, calculations, presentation, provenance, or only documentation.
3. Do not edit generated files under results/; regenerate through the applicable documented pipeline.
4. Do not delete or deduplicate source data by filename alone. Compare data and metadata content, preserve original snapshot identity and document every resolution.
5. Read the [conflict dispositions](docs/b0-conflict-dispositions.md), [technical workflow](docs/data-workflow.md) and [integration plan](docs/integration-plan.md). Target functionality is not an executable setup instruction.

## Validation

Run checks relevant to the change:

```sh
pip install -r scripts/ci/requirements-lint.txt
ruff check .
python -m pytest -q
snakemake --dry-run --cores 1
```

For a complete release check, also run:

```sh
snakemake --cores 2
python scripts/health_pipeline/check_outputs.py
python scripts/health_pipeline/verify_release.py --out results
Rscript tests/shiny_smoke.R results/reports/researcher/app
Rscript tests/dashboard_smoke.R results/reports/researcher/app
bash scripts/ci/secret_scan.sh .   # Linux x86_64; downloads pinned gitleaks
```

CI boundaries are described in [phase 6](docs/phase-6-ci-hardening.md). Complete rendering requires the pinned R, Quarto and TinyTeX environment. Use the [release checklist](docs/release-checklist.md) for candidate-specific fresh-checkout evidence and applicable container/full gates. Report commands not run; do not treat source inspection as runtime/browser acceptance.

## Change rules

- Keep scientific calculations out of presentation; render saved verified results.
- Add/update tests for calculations, selection, schemas and provenance.
- Reject unknown configuration keys rather than silently ignoring them.
- Preserve explicit SKIP, WARN and FAIL meanings.
- Never convert missing to zero unless scientific policy explicitly defines it.
- Do not describe descriptive changes as causal effects or significance.
- Every audience retains limitations, exclusions, source, filters and generation metadata.
- Update dependency locks deliberately with declarations.
- Pin GitHub Actions to full commit SHAs with version comments.
- Preserve frozen references, historical evidence, licences and attribution.

## Pull requests

Keep PRs independently reviewable. Include purpose/scope, user-visible and scientific impact, commands/outcomes, known limits and follow-ups. Every PR MUST include the workflow-preservation section required by the policy: affected stages/routes; base/candidate identities; applicable pre/post numerical and provenance checks; compatibility/migration/backout; and unrun checks. Intentional scientific or schema changes require explicit versioned decisions, not weakened tests.

Documentation-only changes must identify unchanged runtime/data/calculations/dependencies and validate links/status claims. A written policy is not an installed CI gate. Structural cleanup, data migration, scientific-policy changes and report redesign should remain separate PRs where possible. Release/publication remains a separate maintainer decision.
