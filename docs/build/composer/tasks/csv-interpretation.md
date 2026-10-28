# Design task: csv-interpretation

Branch: design/csv-interpretation. PR target: build/composer. Status: not started. Create from the current build tip when assigned.

Dependencies: G1 interpretation/selection/record identities; can overlap component extraction. Requirements: R05, R06, R08, relevant R10-R13; R15 only with approved scope.

Objective: low-friction capture, compact role confirmation, actual selection and explicitly supported shape extensions.

Ownership: data adapter/interpretation/selection changes with exact paths assigned first. Capture once; preserve source strings/record IDs; expose ambiguity, conversions, units and aggregation. Use versioned contracts and saved effective settings. No renderer bypasses preparation, implicit FOPH semantics, silent sum/mean or invented dates.

Acceptance: snapshots/time series; calendar/ISO dates; identifiers/leading zeros; blanks/sentinels/invalid values; repeated periods; non-positive values; separate units/measures; groups, ungrouped and record-count modes; resource limits and CLI replay. Optional formats/locales have separate decisions/tests.

Handoff: stable confirmed request/result interface for actual composer integration; document unsupported cases, migrations and evidence. Follow [handoff](../HANDOFF.md), [ledger](../requirements.json) and [review](../REVIEW_AND_RESUME.md).
