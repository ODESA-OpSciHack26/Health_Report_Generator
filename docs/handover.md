# Baseline acceptance and remaining combined integration

## Current planning authority

The current candidate is an accepted foundation, not completion of the combined donor product. Follow [the combined integration plan](integration-plan.md), [steward workspace](steward-workspace.md), [contracts](integration-contracts.md) and [acceptance gates](integration-acceptance.md). M4 integrates existing v2 IDD/CSV/UI functionality, Nisha's report design and configuration-driven stakeholders. M5 adds full surveillance capabilities. This replaces the earlier implication that artifact packaging was the only remaining work and supersedes the uncommitted M4/M5/M6 split.

## Historical baseline and evidence

| Record | Scope |
|---|---|
| [M0](evidence/m0/README.md) | Preserve and reproduce V1 |
| [M1](evidence/m1/) | Provenance/baseline guards |
| [M2](evidence/m2/README.md) | Shared-template and dependency ownership |
| [M3](evidence/m3/README.md) | Local form/adapter, cache checks and date-consistent wording |

M3 tested implementation: `cbc856ca9c5367d47b55e6836493bbe259af8e22`. Final feature head including evidence/scanner review: `8b0a08b90bad800e4ad9731fd1d3221abbf018c5`. The earlier M3 capture included 187 Python tests. Its actual browser check is pre-commit evidence. PR #4's successful remote checks were PR validation, not a
new execution against the integration merge commit.

The later accepted integration candidate is `fe5fb8ed1ab5f4bf94cc10da1637b82b539692ec`. The maintainer supplied a clean fresh-checkout capture with eleven passing stages, unchanged analytical hashes, 18 selected artifacts and matching template identities. The user subsequently reported all three reports, navigation/downloads and PDFs visually passed. Retain this as baseline-only reported acceptance; the redesigned product needs new review. See [acceptance](integration-acceptance.md) for scope and limitations.

## Existing behaviour versus target

The baseline supports the standard three IDD reports, a custom-request CLI and a local form with four fixed profile choices. CSV upload and donor redesign are not integrated into that baseline. The GitHub connector is a separate optional path. Current commands remain in [setup](../GETTING_STARTED.md), [local interface](local-interface.md) and [reproduction](reproduction.md). New planning documents must not be used as executable setup instructions until implemented.

## Preservation and distribution

Keep historical phase/evidence records as history, not active forward plans. Local artifact/log hashes do not make those files transferable; preserve actual inputs, snapshots, code/environment specifications, configs and complete report folders when distributing a reproducible bundle. Visual acceptance is not independent scientific validation, cold-cache proof, network isolation or byte-identical rendering.

Work remains on `integration/steward-ready-v1`; main and original release references are unchanged. New tags, deployment and release publication require a separate maintainer decision under the [release checklist](release-checklist.md).
