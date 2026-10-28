# Repository and planned workspace map

## Planning authority

The [Track B integration plan](integration-plan.md), [contracts](integration-contracts.md), [workspace](steward-workspace.md) and [acceptance](integration-acceptance.md) govern target scope. The [workflow-preservation policy](workflow-preservation-policy.md) applies throughout B0-B7. See [conflict dispositions](b0-conflict-dispositions.md). Targets are not claims of implemented functionality.

Integration home: integration/steward-ready-v1. Focused branches start there and PR back there. Track A remains frozen at m4/frozen-descriptive-reports, c72bd54f69300b8e79bb967c201529d48625ae45. Former composer branches are transfer/history sources, not another integration home.

## Existing supported foundation

| Path | Role |
|---|---|
| Snakefile, workflow/ | Orchestration, configuration/schema and version contracts |
| data/reference/ | Canonical committed IDD inputs and publisher metadata |
| scripts/health_pipeline/ | Verified analysis, tabular preparation, shared report source, publishing, cache and checks |
| scripts/health_pipeline/config/stakeholders/ | Existing stakeholder configurations |
| src/local_ui.py, src/local_report.py | Host-local form/adapter, custom cache and fixed profile choices; dynamic discovery remains a target |
| src/ui.py, src/artifact_download.py, CONNECTOR_SETUP.md | Separate optional GitHub-backed connector without custom cache |
| Dockerfile.report, Dockerfile, compose.yaml, lockfiles | Environment boundaries; changes require compatibility evidence |
| tests/, .github/workflows/ | Regression, container, release and CI gates |
| docs/evidence/ | Historical validation records with preserved tested identities |

The explicitly mapped supplied-table CLI exists; the combined guided source-review/composer UI does not. Read the [architecture](architecture.md) and [tabular reproduction guide](m4-tabular-reproduction.md) for route boundaries.

## Proposed additions, not yet implemented

The workspace specification separates catalogues/recipes, immutable originals, incomplete work, accepted runs, validated cache, reviews and approved exports conceptually. It does not mandate an installed report-vault/ directory. Concrete schema/registry/adapter/component/storage locations require B1 decisions and tested migrations. Retain existing path adapters until replacements pass parity. Steward/private inputs are not automatically committed to Git.

Selected external presentation components are assessed and pinned in the plan. Reuse/adapt/defer explicitly instead of copying whole alternative workflows or losing attribution.

## Historical and superseded material

Phase records, migration/removal JSON and docs/evidence/ remain audit history, not the active roadmap. Original composer notes retain their historical branch and checkpoint context; B0-B7 supersede their active delivery instructions. See the conflict dispositions rather than rewriting historical acceptance.

Historical licence prose does not override today's MIT LICENSE or separate source-data terms. Handover records baseline acceptance, not combined-product completion.

Health_Report_Generator-test/, scripts/health_pipeline/example_output/, design/report-mockups.html and configs/report.yml are historical/prototype/reference material unless explicitly selected. They are not evidence of a successful current render. Do not delete scientific policy, provenance, licences, audit manifests or validated evidence to remove obsolete planning language.
