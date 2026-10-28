# Design task: verification

Branch: design/verification. PR target: build/composer. Status: not started. Begin G0 preparation in coordination with the integrator; create from the current build tip when assigned.

Dependencies: starts at baseline and remains independent throughout. Requirements: all applicable ledger entries.

Objective: protect numerical meaning, evidence truth, replay, publication and disclosure through independent checks.

Ownership: expected fixtures, adversarial tests and review findings. Coordinate test-file ownership; do not edit another writer's uncommitted work. Do not approve a result only from its own generated manifest, weaken/delete acceptance tests or inflate visual tolerances to obtain green status.

Acceptance: baseline plus stage-specific full/report-runtime tests; manually expected values/lineage; false rehashed evidence/source identity; failure/race/path cases; cache invalidation; restricted-artifact exclusion; clean saved-request replay. Distinguish test execution from source inspection and browser/scientific review.

Handoff: findings per exact candidate/requirement, commands/exits, evidence locations and explicit blockers/unrun checks. No self-promotion or substitution for human final acceptance. Follow [handoff](../HANDOFF.md), [ledger](../requirements.json) and [review](../REVIEW_AND_RESUME.md).
