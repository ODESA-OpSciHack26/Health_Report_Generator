# Design task: contracts

Branch: design/contracts. PR target: build/composer. Status: not started. Create from the current build tip when assigned.

Dependencies: G0 baseline and coordination with verification. Requirement focus: R01-R03 and interfaces required by later entries.

Objective: minimum strict interpretation/scope, component-instance, method/result, composition and evidence contracts for one complete comparison, not every hypothetical future method.

Ownership: isolated schema/resolver/fixture additions. Coordinator records exact allowed paths before edits. Coordinate shared request/provenance/verifier changes; do not silently alter calculations or request v1/v2. Do not enable an unfinished production renderer.

Acceptance: deterministic resolution; rejection of unknown fields, unsafe refs, duplicate identities, missing dependencies and incompatible bindings; original/effective settings retained; compatibility fixtures.

Handoff: comparison implementation can consume the agreed input/result/method/instance/evidence interfaces. Include base/candidate, commands/exits, independent review, artifacts, migration/backout and unrun checks. Follow [the build handoff](../HANDOFF.md), [ledger](../requirements.json) and [review protocol](../REVIEW_AND_RESUME.md).
