# Release notes

## Integration documentation alignment (unreleased)

Active Track B stages are B0-B7 on integration/steward-ready-v1. Older M4/M5 labels retain historical context. The mandatory [workflow-preservation policy](docs/workflow-preservation-policy.md) applies throughout; [conflict dispositions](docs/b0-conflict-dispositions.md) record route, branch, status and licence resolutions. These documentation changes do not implement target features, close B0, constitute new runtime acceptance or publish a release.

## Hackathon release

Reproducible, parameterised FOPH Infectious Diseases Dashboard reporting: researcher, health-institution and public interactive HTML reports from a shared Quarto source and audience parameters, with machine-readable provenance.

### Highlights

- snakemake --cores 2 or bash scripts/health_pipeline/run_all.sh builds canonical HTML, PDF and Shiny outputs for audiences in workflow/config.yaml.
- Standard audiences differ in communication parameters and retain matching analytical tables. Python calculates results; presentation consumes verified tables.
- Sidecar/embedded provenance records source, snapshot, release/retrieval dates, filters, effective parameters, versions, Git commit and render time; release.json records artifact/code hashes.
- Blocking quality gate, content-addressed snapshots and source-row lineage.
- Historical release toolchain: Python 3.11.6, R 4.3.2, Quarto 1.3.353, TinyTeX v2026.10; workflow/toolchain.json governs current runtime policy.
- Separate weekly API synchronization and exact-snapshot reproduction; acquisition is not hidden inside report regeneration.

### Development history

| Phase | Outcome |
|---|---|
| 0 Baseline | Reference behavior/tests/dry run recorded |
| 1 Safe hygiene | Junk removal, documentation and contributor guide |
| 2 Environment alignment | Python/R/Quarto/TinyTeX contract with CI checks |
| 3 Canonical data | data/reference/ and migration manifest |
| 4 Legacy removal | Reversible removal of retired Data/ |
| 5 Multi-audience reports | Three audiences, provenance and interactive tables (PR #12) |
| 6 CI hardening | Gated CI, action pinning, secret scan and release verification; see docs/phase-6-ci-hardening.md |
| 7 Release polish | Architecture, limitations, demo, citation, release notes and one-command wrapper fix |

Historical phase records preserve their original context and evidence. The wrapper replaced an earlier reference to removed data/Data and an inappropriate loop over every profile. Documentation now distinguishes separate weekly acquisition from report generation.

### Custom reports and supplied tables

custom_report.py uses a request file and the shared template. Its local cache key covers request, snapshot, code, toolchain and schema. Sidecars include provenance and request/cache identity. The host-local form uses this path/cache; the GitHub-backed interface does not. Cache has no eviction and custom outputs are outside standard release.json. Legacy --out is replaced on every run; preserve earlier output or use a fresh destination.

The optional explicitly mapped CSV/TSV route supports three verified HTML reports; see [tabular reproduction](docs/m4-tabular-reproduction.md). Guided upload, dynamic profiles/composition and evidence inspectors remain Track B targets. Generic HTML does not imply PDF/app parity.

### Known limitations and terms

See [limitations](docs/limitations.md): canonical national totals, descriptive comparisons and transitional non-package code layout. Current software terms are [MIT](LICENSE), not a licence for source data. Historical statements that no project licence existed do not describe the current repository.

Data source: FOPH/BAG Infectious Diseases Dashboard, with separate [data terms](data/README.md) and attribution. Each report identifies its exact snapshot, publication and retrieval dates. Release/tag/deployment decisions remain separate under the [release checklist](docs/release-checklist.md).
