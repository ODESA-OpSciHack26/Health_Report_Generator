# Track B contracts and architectural boundaries

Status: target responsibilities, not a released schema/API. Updated 28 October 2026. Governed by [the plan](integration-plan.md) and [inspectable-block decision](decisions/inspectable-blocks.md). B1 delivers concrete strict schemas and migration tests. Existing tabular request versions 1/2 remain unchanged until an explicit compatible extension is implemented.

## Pipeline and identities

Input adapter -> recorded interpretation -> domain QC and analytical selection -> domain analysis -> verified results/capabilities -> resolved composition/publication plan -> shared QMD and registered renderers -> exact verification -> no-replace publication.

Keep source/interpretation/selection identity, numerical-analysis identity and composition/render identity distinct. The current descriptive serialization mixes labels/chart selection with numerical results; do not promise whole-file invariance for every display edit. Change serialized meaning only through an explicit version/migration decision.

| Entity | Required responsibility |
|---|---|
| Dataset | Immutable content identity, retained reference, attribution/terms, available fields/capabilities, sensitivity |
| Interpretation | Confirmed mapping, parsing/frequency/timezone, units/roles, missingness and aggregation policy, inference/override status |
| Selection | Actual predicates, retained original record identities, before/after counts, exclusion reasons; labels are not filters |
| Analysis | Method/version, resolved parameters, scope, full-precision results, eligibility/QC, source lineage |
| Profile | Stable ID/version, purpose/detail, wording, defaults and allowed settings; discovery separate from publication |
| Component | Trusted type/version, bindings/options, required capabilities, renderer/formats, evidence producer and tests |
| Composition | Ordered unique instances, resolved settings, dependency/context rules and omission decisions |
| Evidence | Inputs, calculation, results, plotted data, code/environment references and disclosure state |
| Publication/run | Selected profiles/formats, request and effective plan, state, timestamps, exact artifacts/hashes, reviews and permitted exports |

Use JSON-compatible strict configuration. Reject unknown executable fields, unsafe identifiers/paths, duplicate instance IDs, invalid bindings and unsupported versions. Canonical schema/precedence rules are fixed in B1, not inferred from this prose. Save the author request and fully resolved effective plan so changing defaults cannot silently reinterpret old recipes.

## Data and domain rules

Reuse captured-byte CSV/TSV preparation. Initial supported shape is category plus one measure and optional time. Suggest roles conservatively; require correction/confirmation for ambiguity and save the interpretation. Preserve leading-zero identifiers. New encodings, delimiters, decimal conventions, missing sentinels, ungrouped/multi-measure shapes or wide-to-long transforms require explicit versioned contracts.

Do not silently sum rates, average percentages, treat numeric identifiers as measures, infer observation time from import time or classify arbitrary uploads as FOPH data. Filtering preserves original source-record identities.

IDD analysis retains its domain-specific verified metrics, QC, denominators and selection rules. Generic descriptive analysis remains separate. Share metadata/capability interfaces, not a universal scientific algorithm. Unsupported content is unavailable, not zero, normal or low risk.

## Composition and inspector

Each block instance references its type/version, analysis scope/result, exact input and plotted-data identities, method/parameters, relevant analysis/render source and environment, initial disclosure and distribution policy. The common inspector renders data, calculation, analysis code, rendering code and reproduction views beside the result. Required context travels with the claim.

Source panels show retained versioned implementation, relevant helpers and effective parameters, not generated illustrative code or moving remote branch contents. Record execution metadata at the analysis boundary; label generated replay recipes separately from actual execution traces. Do not claim that hashes attest all loaded binaries.

Reordering preserves evidence links; duplication creates a new display identity while sharing unchanged results. Opening disclosures performs no analysis. Initial analytical scope is report-global; block-local display subsets are labelled. Advanced block-local analytical scopes need independent identities and explicit approval.

## Backend and formats

Keep one shared report entry point with source-specific capability adapters. No extra audience QMDs. Renderers format verified results, not recalculate scientific metrics. Retain the existing host/Compose execution route initially; topology/backend changes need a tested ADR, dependency ownership and rollback. Components advertise only tested interactive/static/PDF capabilities.

## Verification, caches and lifecycle

Version generation and independent verification together. Validate exact artifact/evidence sets, source/result references, embedded/sidecar agreement and effective composition. Reconstruct supported calculations and evidence from captured inputs; do not accept a rehashed false result. Historical artifacts use their recorded compatible source/schema, not weakened checks.

Cache keys cover the appropriate input, method or rendering identities. Validate entries and preserve original render timestamps separately from new retrieval/submission times. Use isolated work and complete no-replace publication for the new unified lifecycle; do not describe old replacement routes as already migrated.

## Privacy/export and extension limits

Reader collapse, steward initial display state and artifact distribution policy are different controls. Restricted bytes must be absent from public HTML, scripts, downloads, manifests and linked code artifacts, not merely hidden. Give a restricted export its own manifest, omission reasons and replay limits; retain the private accepted run under its actual policy.

Do not expose credentials, home paths or arbitrary environment dumps. New scientific methods, geographic surveillance and source families require reviewed prerequisites, implementation and fixtures. No-code customization means combinations of trusted existing capabilities, not uploaded executable expressions.
