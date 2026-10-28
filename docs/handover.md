# Baseline acceptance and remaining combined integration

## Current planning authority

The current line is a reporting foundation, not completion of the combined product. Follow the [Track B integration plan](integration-plan.md), [workspace](steward-workspace.md), [contracts](integration-contracts.md), [acceptance gates](integration-acceptance.md) and [mandatory workflow-preservation policy](workflow-preservation-policy.md). Active delivery identifiers are B0-B7. Older M4/M5 and composer C/WP labels retain historical context only. Surveillance is a separately gated future extension. See [conflict dispositions](b0-conflict-dispositions.md).

## Historical baseline and evidence

| Record | Scope |
|---|---|
| [M0](evidence/m0/README.md) | Preserve and reproduce V1 |
| [M1](evidence/m1/) | Provenance/baseline guards |
| [M2](evidence/m2/README.md) | Shared-template and dependency ownership |
| [M3](evidence/m3/README.md) | Local form/adapter, cache checks and date-consistent wording |

M3 tested implementation: cbc856ca9c5367d47b55e6836493bbe259af8e22. Final feature head including evidence/scanner review: 8b0a08b90bad800e4ad9731fd1d3221abbf018c5. The earlier M3 capture included 187 Python tests. Its actual browser check is pre-commit evidence. PR #4's successful remote checks were PR validation, not a
new execution against the integration merge commit.

The later accepted integration candidate is fe5fb8ed1ab5f4bf94cc10da1637b82b539692ec. The maintainer supplied a clean fresh-checkout capture with eleven passing stages, unchanged analytical hashes, 18 selected artifacts and matching template identities. The user subsequently reported all three reports, navigation/downloads and PDFs visually passed. Retain this as baseline-only reported acceptance; the redesigned product needs new review. See acceptance for scope and limitations.

Frozen Track A is m4/frozen-descriptive-reports at c72bd54f69300b8e79bb967c201529d48625ae45. Its reported acceptance belongs to that revision, not to a later integration tip or documentation patch.

## Existing behaviour versus target

The historical IDD baseline supports three standard reports, a custom-request CLI and a local form with four fixed profile choices. The current integration foundation also has an opt-in explicitly mapped CSV/TSV CLI with three verified HTML views. It does not yet have the guided upload/interpretation/composer workspace or per-block evidence inspectors. Generic mapping remains one category, one measure and optional time.

The host-local form uses the custom-report cache; the separate GitHub-backed connector does not. Legacy custom --out is replaced on each invocation. Preserve an earlier output or use a new destination. Unified no-replace publication is a target requirement, not a claim that this legacy route is migrated.

Current commands remain in [setup](../GETTING_STARTED.md), [local interface](local-interface.md), [tabular reproduction](m4-tabular-reproduction.md) and [reproduction](reproduction.md). Design prose must not be used as executable setup until implemented.

## Preservation and distribution

Historical phase/evidence records remain history, not active forward plans. Hashes alone do not make artifacts transferable: preserve actual permitted inputs, snapshots, code/environment specifications, configs and complete report folders. Visual acceptance is not independent scientific validation, cold-cache proof, network isolation or byte-identical rendering.

Work integrates through integration/steward-ready-v1. Main, original releases and frozen references remain unchanged. New tags, deployment and publication require a separate maintainer decision under the [release checklist](release-checklist.md).
