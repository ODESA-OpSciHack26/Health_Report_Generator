# Documentation index

## Active product plan

The authoritative forward plan is [Track B integration](integration-plan.md). The active integration branch is `integration/steward-ready-v1`. Track A is preserved at `m4/frozen-descriptive-reports`, commit `c72bd54f69300b8e79bb967c201529d48625ae45`. Use B0-B7 for current delivery stages; older M4/M5 labels describe their historical planning context. Surveillance remains a separately gated future extension.

- [Integration plan](integration-plan.md): end state, current capabilities, dependencies and preparation checklist.
- [Contracts](integration-contracts.md): interpretation, selection, analysis, composition, evidence and publication responsibilities.
- [Steward workspace](steward-workspace.md): source review, report composition and export experience.
- [Inspectable blocks](decisions/inspectable-blocks.md): expandable data, calculations, analysis/render code and reproduction details beside each result.
- [Acceptance](integration-acceptance.md): objective gates and evidence scope.

These describe target behavior unless explicitly identified as implemented. Committing a plan does not implement a composer, upload UI or evidence inspector.

## Existing executable routes

Use [setup](../GETTING_STARTED.md), [reproduction](reproduction.md), [canonical IDD architecture](architecture.md), [local form](local-interface.md), [supplied-table CLI](m4-tabular-reproduction.md), [descriptive visuals](m4-tabular-descriptive-visuals.md), [audiences](audiences.md), [dependency ownership](dependency-ownership.md) and [scientific policy](scientific-policy.md). The optional GitHub-backed interface has separate [connector setup](../CONNECTOR_SETUP.md).

The canonical route and explicitly mapped CSV/TSV CLI exist. The unified source-selection/mapping/composer workspace does not yet exist. Existing local and GitHub-backed forms are different interfaces.

## Historical and transitional guidance

[Handover](handover.md), [repository map](repository-map.md) and [original composer notes](branch-notes/m5-report-composer.md) retain useful history but are being reconciled in B0. Where their milestone or integration-home statements conflict, the current integration plan governs. Do not rewrite historical test identities or infer a new run from a documentation update.

Phase records, migration JSON and `docs/evidence/` remain historical evidence. Preserve licences and attribution; current software terms are [MIT](../LICENSE), separate from [data terms](../data/README.md).
