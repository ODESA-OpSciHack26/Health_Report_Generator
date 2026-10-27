# Integration contracts and architecture decisions

Status: target M4 contracts. Field names below describe responsibilities, not a released schema/API. Final schemas and migration tests are delivered in WP1. Current executable behaviour remains documented in [architecture](architecture.md). See [plan](integration-plan.md).

## 1. Boundaries

The flow is input adapter -> recorded interpretation -> blocking QC -> domain-specific analysis -> verified bundle -> shared parameterised renderer -> complete output manifest. IDD and generic descriptive analysis remain distinct; one renderer does not mean one arbitrary statistical method. UI and CLI submit the same validated request to the same execution service. Rendering must not reread an unvalidated upload or recalculate epidemiological results.

## 2. Entities and required responsibilities

| Entity | Required identity and content |
|---|---|
| Dataset | source type, immutable content identity, retained input reference, terms/attribution, schema, available roles/capabilities, sensitivity |
| Interpretation | original-to-normalised field mapping, time parsing/frequency/timezone, measure and identifier roles, units, missing/invalid handling, aggregation decisions, inferred/confirmed/overridden status and method version |
| Stakeholder | stable ID, version, purpose, wording templates, detail level, allowed/default filters, ordered components, bindings/options, mandatory communication elements |
| Request | schema version, dataset/interpretation identities, stakeholder and overrides, analytical selection, presentation, outputs, execution/environment identity |
| Analysis bundle | integrity manifest, verified tables, units, scope, coverage, QC, lineage and available capabilities; shared core metadata with domain-specific tables |
| Component | stable type/version, required capabilities, binding/option schema, rendering implementation, fallback, provenance and tests |
| Run/export | state, request identity, source/analysis/render identities, timestamps, artifacts and hashes, review references, errors/limitations and disclosure policy |

Schemas reject unknown or invalid executable fields, unsafe paths, incompatible bindings and unrecognised IDs. Use explicit migrations and versioned fixtures; do not silently reinterpret old recipes after an upgrade. Final decision: document which configuration format is canonical; JSON is compatible with existing profiles, and UI-generated exports must round-trip without semantic loss.

## 3. CSV interpretation

Reuse the donor's structural validation and optional mapping while fixing the split between importer and renderer. Automatic suggestions remain low-friction for clear inputs. Ambiguous roles, time parsing or aggregation must be surfaced and resolved. Record the resolved interpretation even when no mapping file was manually supplied.

Treat identifier-like numbers as candidates for identifiers, not measures by default. Parse year integers with explicit calendar-year rules. Preserve leading zeros and category codes. Define duplicate-header/row, encoding, delimiter, decimal, timezone, missing-sentinel, invalid-value and mixed-unit policies. Do not assume that sums of rates, means of percentages or an 'All' category are meaningful. A time-free snapshot records import time separately from observation time; import date must not masquerade as a measured period.

Structured IDD-compatible uploads require their own explicit contract and checks; extension names alone do not confer eligibility. General tables never inherit disease classifications, population denominators or FOPH attribution. Repeated imports of identical source bytes should have stable source identity even if run IDs/import timestamps differ.

## 4. Parameter resolution and capabilities

Define precedence: validated application defaults -> selected dataset interpretation/capabilities -> stakeholder defaults -> explicit request overrides, constrained by supported analytical options. Resolve once, record the result and give UI/CLI the same validation errors. Profiles cannot override mandatory QC or disclosure rules. A dynamic title/question must use the actual component scope, not a fixed 2025 string.

A section declares inputs and returns supported, unavailable or invalid. Unsupported optional sections render an honest explanation or are omitted with a recorded reason; required unsupported sections block generation. Unavailable is not zero, normal, no change or no risk. M4 reserves M5 capabilities without simulating their results. Different geographic or time scopes must be labelled per component.

## 5. Presentation and graph plugins

Keep a single shared report entry point plus common methods presentation and reusable components. Display logic can format verified data, not introduce hidden analysis. A chart configuration selects trusted code, never supplies arbitrary code. Bindings reference defined table/field identities and units. Component registration includes semantic prerequisites, options, visual labels, missingness behaviour, uncertainty handling, accessible description, interaction, safe static representation and output formats. Refuse unsupported format claims; HTML interactivity does not imply equivalent PDF behaviour.

Review whether donor Plotly/Python results should be packaged as verified chart specifications/assets for the existing renderer or rendered through a compatible presentation backend. Choose via a tested WP0/WP1 spike. Preserve one common entry point and provenance contract whichever backend wins; avoid forcing an unnecessary language rewrite or retaining parallel audience engines. Keep environment ownership explicit and pinned.

## 6. Caches and atomic publication

Use conceptual layers: input/normalisation identity; analysis identity covering input, interpretation, analytical parameters, methods and relevant software; render identity covering bundle, stakeholder/wording/components, visual settings, template and renderer environment. Reuse current cache verification where correct. Initially conservative invalidation is acceptable; undeclared reuse is not.

A hit must validate its manifest and retain original rendering provenance. Record the new request/submission separately from the original render. No wall-clock import date should silently change a semantic snapshot identifier. Never reuse by filename alone. File locks must cover all supported writers or use isolated immutable entries with atomic publication. A failed render or partial HTML/PDF pair cannot replace a successful output. Cache schema changes require explicit invalidation/migration, not exceptions that weaken integrity checks.

## 7. Provenance and retention

Embed and export machine-readable provenance identifying source and dataset version/digest, filters, interpretation, selected stakeholder/components, effective parameters, transformation/method versions, analytical/table lineage, code/environment identities and generation time. Track component-specific windows/geography when they differ. A descriptive CSV report must meet the shared provenance contract, not only record filename and row count.

Keep private forensic details out of public provenance. Export manifests state what was intentionally omitted and whether full replay requires private retained inputs. Software locks, source/snapshot content and configs are necessary companions to hashes. Record manual review as reviewer-reported evidence, not an automated verification result.

## 8. Decisions required before coding across boundaries

Record ADRs for execution topology, report backend/asset bridge, shared bundle schema, registry/discovery and publication selection, CSV inference/override policy, cache/concurrency design, privacy/export policy and dependency migrations. Each ADR includes donor alternatives, rationale, risks, rollback, owner and evidence. Revisit only with recorded consequences; architecture decisions must not remain hidden in one-off patch scripts.
