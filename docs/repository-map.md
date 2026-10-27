# Repository and planned workspace map

## Planning authority

The [documentation index](README.md) links the authoritative [combined integration plan](integration-plan.md), [steward workspace](steward-workspace.md), [contracts](integration-contracts.md) and [acceptance](integration-acceptance.md). The plan is target behaviour, not a statement that CSV/design integration is already implemented.

## Existing supported foundation

| Path | Role |
|---|---|
| `Snakefile`, `workflow/` | Orchestration, configurations/schemas and version contracts |
| `data/reference/` | Canonical committed IDD inputs and publisher metadata |
| `scripts/health_pipeline/` | Verified analysis, shared report source, helpers, publishing, cache and checks |
| `scripts/health_pipeline/config/stakeholders/` | Existing stakeholder configurations |
| `src/local_ui.py`, `src/local_report.py` | Accepted host-side local form/adapter; fixed profile options pending M4 integration |
| `src/ui.py`, `src/artifact_download.py`, `CONNECTOR_SETUP.md` | Separate optional GitHub-backed connector |
| `Dockerfile.report`, `Dockerfile`, `compose.yaml`, lockfiles | Existing environment boundaries; changes require documented compatibility evidence |
| `tests/`, `.github/workflows/` | Regression, container, release and CI gates |
| `docs/evidence/` | Historical machine/human validation records; preserve tested identities |

## Proposed additions, not yet implemented

The portable `report-vault/` layout is specified in [workspace](steward-workspace.md). It contains steward-owned catalogues, inputs, recipes, runs, reviews, caches and exports; it is not a second source-code tree. Application-side schema, registry, adapter and component locations are selected in WP1 ADRs rather than pretending a new package layout is already installed. Retain adapters for current paths until tested migrations are accepted. Private vault contents are not automatically added to Git.

Donor modules are pinned and tracked in the plan. Integration must select/adapt them rather than copying whole alternative workflows or losing attribution.

## Historical and superseded material

`docs/phase-*.md` and migration/removal JSON files are historical implementation/audit records, not the active roadmap. `docs/phase-7-release.md` records its original licence/setup context; it does not override today's MIT LICENSE or current release checklist. `docs/handover.md` records accepted baseline scope, not final product completion.

`Health_Report_Generator-test/`, `scripts/health_pipeline/example_output/`, `design/report-mockups.html` and `configs/report.yml` are historical/prototype/reference material unless a donor manifest explicitly selects a component. They are not evidence of a successful current render.

No committed file containing the discarded conversational design-only/CSV-later M4-M6 sequence was found in the inspected documentation inventory. Replace conflicting active guidance; do not delete scientific policy, historical provenance, licences, audit manifests or validated evidence merely to remove old plans.
