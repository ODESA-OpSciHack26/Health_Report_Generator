# Technical presentation adaptation

Status: design specification and source assessment; not an implemented theme or browser acceptance. Updated 28 October 2026. See [plan](integration-plan.md), [data workflow](data-workflow.md) and [inspectable blocks](decisions/inspectable-blocks.md).

## 1. Scope

Adapt presentation components selectively while retaining the current calculation, verification, dependency and shared-template boundaries. A full branch merge or wholesale runtime replacement is unnecessary. This document describes visual/technical responsibilities, not personal ownership. Existing licence, citation, contributor and historical attribution records remain intact.

Technical reference revision: `12a7afaab5e86dab81cc03b7e39f0284a8104b3c`. Presentation sources include `reports/utils/style.css`, `reports/utils/general_style.css`, the report QMD layouts and their helper modules. The reference revision was source-inspected; it has not received a new runtime/browser acceptance in this adaptation. Earlier compatibility evidence does not automatically validate revised code.

## 2. Reusable visual patterns

Use shared design tokens for typography, spacing, surface/background, borders and permitted colours. Adapt summary-card geometry, readable values/labels, section hierarchy, contrasting table headers, alternating rows, callouts, responsive grids and supported print styling. Scope CSS to report/component containers; global body/table/heading rules must not accidentally alter methods or evidence panels.

Port section composition into registered blocks and audience presets rather than adding separate production QMDs. Preserve one common entry point. Operational/public-health presentation informs the institutional preset; the plain-language public preset remains independently designed.

## 3. Keep visual language separate from analysis

Status badges, coloured cards and chart bands can encode scientific or operational claims. Do not import above-normal/record-high labels, thresholds, comparison windows, year-to-date calculations, maps, suppression rules or clinical interpretations as styling. Initial cards use neutral verified scope, coverage, missingness or comparison information. Surveillance capabilities remain gated.

Helpers that load/transform/aggregate data are not pure styling libraries. Reproduce useful appearance using saved verified results; do not copy differing percentage formulas, implicit sums/means, date coercions or automatic frequency changes into the presentation layer. Plot interaction backends require a separate compatibility/dependency/static-fallback decision. Existing static graphics remain supported until that decision is implemented.

## 4. Shared block evidence interface

Each graph/table/card has adjacent independently expandable data, calculation, analysis-code, rendering-code and reproduction views. Code folding can support the visual treatment, but a wrapper chunk alone is not complete analysis provenance. Source excerpts match retained implementation and provide access to approved complete files/dependencies.

Preserve a clean initial reading surface and visible material context. Inspector state differs from artifact distribution permission. Moving/duplicating blocks preserves stable evidence references and unique DOM/control identities. Opening evidence performs no calculation or moving-source network lookup.

## 5. Adaptation sequence

1. Record reference revision, selected paths/content identities and reuse/adapt/defer decisions with validating tests; retain existing required attribution separately.
2. Prepare a visual fixture using the same verified values for old/adapted styles, without changing the active production route.
3. Extract scoped design tokens/CSS and reusable markup, preserving contrast, focus and narrow-screen layout.
4. Apply the design to the existing reference-change block plus its full evidence inspector.
5. Expand to other registered blocks and three genuinely distinct presets.
6. Verify numerical invariance, actual plotted-data bindings, exact provenance/artifacts, evidence navigation and supported browser/print behavior.

A fixture-based visual spike can accompany B1. Production component adaptation belongs to B2 after the contracts. No new scientific method, framework migration, new parser or environment change is justified solely by visual parity.

## 6. Acceptance

Compare real rendered pages, not source alone. Check headings/cards/tables, readable precision, warnings, keyboard disclosure, focus/expanded states, responsive layout, downloads and offline/static claims. Do not rely on colour alone. Confirm that no required uncertainty/context is hidden or false status implied. Keep historical examples distinct from newly generated outputs and record actual candidate/fixture/review identities.
