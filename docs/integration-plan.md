# Track B: unified reporting product and inspectable composer

Status: authoritative forward plan; implementation is incremental and incomplete. Updated 28 October 2026 after PR #9. Integration home: `integration/steward-ready-v1`, build seed inspected at `0cb8dd095a29760ca7b0dc45167538b938b3a6c7`. Frozen Track A: `m4/frozen-descriptive-reports` at `c72bd54f69300b8e79bb967c201529d48625ae45`. Main, original releases and historical evidence remain unchanged.

## Product end state

One trusted local steward workspace supports a captured IDD snapshot or a general table. The steward uploads or selects data, reviews a compact proposed interpretation, accepts/corrects it, chooses analytical scope and audiences, previews, configures blocks if needed, renders/verifies and saves a portable recipe. Clear inputs should not require handwritten mappings or a long wizard. One command replays an explicitly selected batch. A stakeholder assembled from existing capabilities needs configuration, not a new audience template.

Every analytical block has a common evidence inspector directly beside or below its result: exact permitted input data, selection/eligibility, calculation and assumptions, saved results, plotted data, analysis code, rendering code and reproduction identities. Details expand independently; material scope, units and caveats remain visible. This is a block-contract requirement from B1, not a final UI embellishment.

Detailed specifications: [technical data workflow](data-workflow.md), [presentation adaptation](presentation-adaptation.md), [contracts](integration-contracts.md), [workspace](steward-workspace.md), [inspector decision and E0-E7 sequence](decisions/inspectable-blocks.md), and [acceptance](integration-acceptance.md).

## Current versus target

Implemented foundations include the canonical IDD workflow, captured CSV/TSV inspection and explicit preparation, verified bundles, checksum-pinned tabular request versions 1/2, one-command three-audience HTML rendering, descriptive results/row references, charts, interactive tables and exact verification. Generic input currently maps one category, one measure and optional time.

Not yet implemented: guided upload/interpretation, actual generic selection controls, a dynamic block/profile registry, editable compositions, unified publication plans, per-block evidence inspectors or the combined steward experience. Generic geography labels are not filters; period normalization is not a date-window filter.

The target includes multiple measures, group candidates and explicit ungrouped/row-count modes, implemented through validated interpretation/result extensions rather than silently changing old request semantics. Additional formats such as Parquet, delimiter/encoding/locale handling and wide-to-long transformation are separately evaluated extensions. Do not claim universal spreadsheet compatibility. No name-based sum/mean decision or unreadable-value coercion may be hidden from interpretation review.

Prompt draft preview is desirable, but unconfirmed settings or sampled data are labelled and cannot become verified publication. Final rendering consumes captured bytes and the confirmed interpretation. Three distinctive defaults plus explicit extra profiles remain the publication goal. Generic reports currently support HTML; canonical PDF/apps are separate existing capabilities. Track A acceptance is not acceptance of the complete combined product.

## Branch and milestone policy

Focused feature branches normally start from the current integration tip and PR back into `integration/steward-ready-v1`. The former composer branch was a transfer source, not another accepted integration home. Never move the frozen reference for development. Use Track A/Track B and B0-B7 as active delivery identifiers. Older M4/M5 names are historical; future Surveillance Extension covers reviewed maps, baselines, seasonal windows and statuses, not initial composer scope.

The approved composer isolated integration lane is `build/composer`, seeded at `0cb8dd095a29760ca7b0dc45167538b938b3a6c7`. It is an experimental candidate lane, not a replacement accepted product base. Internal `design/*` branches start from its current tip and PR into it. Only its umbrella draft PR targets product integration, with explicit human promotion approval required. The [operational handoff](build/composer/HANDOFF.md), [requirements ledger](build/composer/requirements.json) and [review/resume protocol](build/composer/REVIEW_AND_RESUME.md) map execution checkpoints onto this plan without replacing product requirements. Internal integration still requires actual permissions and applicable approvals; no protections, runner, release or deployment are installed by prose.

## Delivery stages

| Stage | Work and dependency | Exit condition |
|---|---|---|
| B0 | Align plan, technical workflow, presentation, contracts, workspace, inspector and active guidance | Conflicts explicitly resolved; no runtime changes |
| B1 | Strict interpretation/selection, composition, capability, publication and evidence contracts | Deterministic resolution; invalid settings/references rejected; old requests unchanged |
| B2 | Extract scoped presentation components and distinct presets; first comparison evidence chain/inspector | Numerical parity; truthful data/method/code bindings; stable navigation |
| B3 | Guided bounded upload, confirmed interpretation, saved mapping and supported selection; follows B1, can overlap B2 | Snapshot/time-series and planned shape extensions have fixtures/replay and stable record identity |
| B4 | Dynamic profile discovery and explicit publication; version manifests/verifiers together | New configured stakeholder; exact artifact/evidence checks |
| B5 | Unified low-friction source review, composer, actual preview and save/replay UI | UI/CLI effective requests agree; accessible controls |
| B6 | Cross-cutting provenance, layered cache, disclosure and lifecycle throughout B1-B5 | Correct invalidation; verified reuse; safe approved exports |
| B7 | Combined IDD/general-table/default/custom acceptance | Clean replay, runtime and browser review, transferable evidence |

E1-E7 in the inspector decision are concrete evidence slices within these stages. Prove the existing reference comparison first, not a new inference method. A visual fixture spike may accompany B1; production presentation extraction follows its contracts.

## B0 preparation checklist

The documentation specifies the technical workflow, selective presentation adaptation and inspector direction. PR #9 added conflict dispositions and workflow preservation. B0 is not automatically closed by that merge; validate remaining items at G0 in the build handoff before functional activation:

- Confirm README cache/publication wording and architecture route distinctions against executable behavior.
- Confirm repository-map/handover/historical-note dispositions and licence/status consistency, including the source-data README, without changing licence/citation authorship.
- Validate active documentation links/status claims and record reviewed candidate, unresolved issues and explicit dispositions.
- Fix the minimal B1 contract/test scope, including staged table-shape extensions, without claiming a released schema or completed renderer.

B0 is not complete merely because new documents exist. This handoff bootstrap changes no runtime code, calculations, dependencies or frozen references. Earlier tests retain their actual source/review scope.

## Preserved technical reference identities

Earlier integration baseline: `fe5fb8ed1ab5f4bf94cc10da1637b82b539692ec`. Repair reference: `6cbe222eb7edefe353d7370168c974c43b1a5350`. Earlier report-design reference: `a1cba89bbb5e37b20b48e2df8b334aa4ba7d250b`. Current presentation/table-workflow reference: `12a7afaab5e86dab81cc03b7e39f0284a8104b3c`. The latter was source-inspected, not newly runtime/browser validated. Preserve the [assessment](m4-wp0-donor-assessment.md), machine-readable decisions, licences, attribution and original failure evidence. Technical prose uses neutral component/source descriptions; required credit and historical records are not removed.

Reuse/adapt/defer selected components explicitly rather than wholesale merging environments, deletions or audience engines. The former WP0-WP7 responsibilities continue: compatibility assessment; contracts; lifecycle; CSV integration; presentation; builder; integrity/export; combined acceptance. B0-B7 reorganize delivery, not remove obligations. Retire redundant supported paths only after replacement parity.

## Non-goals and release boundary

No automatic clinical/outbreak conclusions, arbitrary executable settings, patient-data hosting, unnecessary framework migration or unreviewed statistical tests. Retain the trusted host/Compose boundary initially; do not expose a browser container to the Docker socket. HTML-first composer delivery does not silently satisfy generic PDF/static parity; implement or explicitly approve deferral before claiming combined-format acceptance. Release, deployment, protection changes and evidence distribution remain separate decisions.
