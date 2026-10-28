# Track B: unified reporting product and inspectable composer

Status: authoritative forward plan; implementation is incremental and incomplete. Updated 28 October 2026 after PR #7. Integration home: `integration/steward-ready-v1`, inspected at `eb392370852992b8cd5794ea90548c36ebae47f7`. Frozen Track A: `m4/frozen-descriptive-reports` at `c72bd54f69300b8e79bb967c201529d48625ae45`. Main, original releases and historical evidence remain unchanged.

## Product end state

One trusted local steward workspace supports a captured IDD snapshot or a general CSV/TSV. The steward reviews interpretation and analytical scope, uses three distinctive default presets or clones a new stakeholder, adds/removes/duplicates/reorders registered blocks, previews the actual report, renders and verifies, and saves a portable recipe. One command replays an explicitly selected batch. A stakeholder assembled from existing capabilities needs configuration, not a new audience template.

Every analytical block has a common evidence inspector directly beside or below its result: exact permitted input data, selection/eligibility, calculation and assumptions, saved results, plotted data, analysis code, rendering code and reproduction identities. Details expand independently; material scope, units and caveats remain visible. See [the decision and E0-E7 sequence](decisions/inspectable-blocks.md). This is a block-contract requirement from B1, not a final UI embellishment.

## Current versus target

Implemented foundations include the canonical IDD workflow, captured CSV/TSV inspection and explicit preparation, verified bundles, checksum-pinned tabular request versions 1/2, one-command three-audience HTML rendering, descriptive results/row references, charts, interactive tables and exact verification. Generic input currently maps one category, one measure and optional time.

Not yet implemented: guided generic upload/interpretation, a dynamic block/profile registry, editable compositions, unified publication plans, per-block evidence inspectors or the combined steward experience. Generic geography labels are not filters; period normalization is not a date-window filter. Multiple measures, wide-to-long conversion and additional parser policies need explicit contracts. Generic reports currently support HTML; canonical PDF/apps are separate existing capabilities.

Track A acceptance is not acceptance of the complete combined product. Previous successful tests retain their actual candidate/review scope.

## Branch and milestone policy

Focused feature branches start from the current integration tip and PR back into `integration/steward-ready-v1`. The former composer branch was a transfer source, not another integration home. Never move the frozen reference for development. Use Track A/Track B and B0-B7 as active delivery identifiers. Older M4/M5 names are historical; future Surveillance Extension covers reviewed maps, baselines, seasonal windows and statuses, not initial composer scope.

## Delivery stages

| Stage | Work and dependency | Exit condition |
|---|---|---|
| B0 | Align plan, contracts, workspace, inspector decision and active guidance | Conflicts explicitly resolved; no runtime changes |
| B1 | Strict composition, capability, publication and evidence contracts | Deterministic resolution; invalid settings/references rejected; old requests unchanged |
| B2 | Extract existing renderers and distinct presets; first comparison evidence chain and shared inspector | Numerical parity; real data/method/code bindings; stable navigation |
| B3 | Confirmed CSV interpretation, limits, saved mapping and supported selection; follows B1, can overlap B2 | Snapshot/time-series fixtures and replay; stable original record identity |
| B4 | Dynamic profile discovery and explicit publication; version manifests/verifiers together | New configured stakeholder; exact artifact/evidence checks |
| B5 | Unified source review, composer, actual preview and save/replay UI | UI/CLI effective requests agree; accessible authoring controls |
| B6 | Cross-cutting provenance, layered cache, disclosure and lifecycle throughout B1-B5 | Correct invalidation; verified reuse; safe approved exports |
| B7 | Combined IDD/general-table/default/custom acceptance | Clean replay, runtime and browser review, transferable evidence |

E1-E7 in the inspector decision are the concrete evidence implementation slices within these stages. Prove the existing reference comparison first; do not introduce new inference to demonstrate inspectability.

## B0 preparation checklist

This initial alignment commit updates the index, plan, contracts, workspace, acceptance and inspector specification. B0 remains open until the following are completed in this readiness branch:

- Correct top-level README ambiguity: the local host form uses the custom cache; the GitHub-backed form does not. Preserve actual commands and present destination-replacement behavior until migrated.
- Update architecture to describe the existing opt-in tabular route separately from the target registry/evidence design. Scope configuration-only stakeholder claims to their actual route.
- Reconcile repository map, handover and original composer notes with the active integration home and current versus historical status, preserving original acceptance records.
- Record an explicit conflict disposition and validate documentation links and status claims.
- Define the first B1 contract/test scope; do not advertise an unfinished renderer or released schema.

B0 is not complete merely because a new design document exists.

## Preserved donor and planning provenance

Earlier integration baseline: `fe5fb8ed1ab5f4bf94cc10da1637b82b539692ec`. v2 repair donor: `6cbe222eb7edefe353d7370168c974c43b1a5350`. Nisha donor: `a1cba89bbb5e37b20b48e2df8b334aa4ba7d250b`. Preserve the [donor assessment](m4-wp0-donor-assessment.md), its machine-readable decisions, attribution, licences and original failure evidence. Reuse/adapt/reject components explicitly; do not wholesale merge donor environments, deletions or audience engines.

The former WP0-WP7 responsibilities continue: compatibility assessment; contracts; lifecycle; CSV integration; presentation; builder; integrity/export; combined acceptance. B0-B7 reorganize delivery, not delete those obligations. Retire redundant supported paths only after replacement parity; the backup enables deliberate refactoring, not indiscriminate removal.

## Non-goals and release boundary

No automatic clinical/outbreak conclusions, arbitrary executable settings, patient-data hosting, unnecessary framework migration or unreviewed statistical tests. Retain the trusted host/Compose boundary initially; do not expose a browser container to the Docker socket. HTML-first composer delivery does not silently satisfy generic PDF/static parity; implement or explicitly approve deferral before claiming combined-format acceptance. Release, deployment, protection changes and evidence distribution remain separate decisions.
