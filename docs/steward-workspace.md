# Steward workspace and report authoring experience

Status: target experience, not shipped UI behavior. Updated 28 October 2026. See [plan](integration-plan.md), [contracts](integration-contracts.md), [inspectable blocks](decisions/inspectable-blocks.md) and [acceptance](integration-acceptance.md).

## Finished user journey

1. Open/create a local workspace without replacing an existing one. Show location, versions and trusted-single-steward assumptions. A workspace is not an encrypted vault.
2. Choose a captured IDD snapshot or CSV/TSV. Show source identity, bounded preview, dimensions, missingness and QC. Acquisition is separate from regeneration.
3. Review suggested roles and confirm/correct interpretation. Save mapping, parsing, units, supported period and identifier policies. Ambiguous columns require a decision.
4. Set actual report-global analytical selection and supported comparisons. Distinguish exclusions from display-only filtering; geography annotations do not filter data.
5. Select the standard three-profile batch or clone a profile for a new purpose. Discovering a profile does not add it to publication.
6. Assemble registered blocks, select metrics/graphs, add attributed editorial notes and reorder/duplicate/place supporting detail. Required context cannot be suppressed.
7. Preview the actual report with draft/sampling labels and actionable capability/dependency messages. Preview is not verified publication.
8. Render/verify through the same effective request service as the CLI. Show queued/running/failed/succeeded state and safe diagnostic references. Preserve previous accepted output after failure.
9. Save/reopen a portable recipe and export explicitly approved artifacts. One command replays the selected batch with retained source/environment references.

## Composer layout

- Source/interpretation panel: source identity, preview, field review, selection and QC.
- Block library: categories/search, explanation, availability and prerequisites.
- Ordered outline plus real preview: headings, stable instances, configure/move/duplicate/remove and placement.
- Settings: metrics/order, permitted bindings, display precision, caption, supported scale, detail and initial evidence disclosures.
- Run/evidence view: validation, analysis-versus-display changes, progress and last accepted report.

Use move buttons and keyboard operation; dragging is optional convenience. Preserve visible focus, understandable labels, expansion states, contrast and responsive layouts. Retain Marimo initially; do not replace the framework merely to obtain a composer widget. The existing host-local and GitHub-backed forms remain different supported routes until a replacement passes parity.

## Inspectable results

Every analytical graph, table or card has adjacent independently expandable data, calculation, analysis-code, rendering-code and reproduction sections. Large data is clearly previewed with full permitted artifacts or a withholding explanation. The inspector is common UI driven by each block's evidence bindings.

Researcher defaults emphasize methods/audit. Institutional defaults emphasize scope/comparability. Public defaults show plain-language explanation and material limits with technical evidence reachable. Custom profiles set initial disclosure, not permission to leak restricted artifacts or remove essential caveats.

## Distinct report defaults

Researcher: question/scope -> quality/coverage -> statistics -> diagnostics -> detailed rows -> methods/reproduction.

Institution: monitoring scope -> changes to review -> latest/reference values -> eligibility/quality -> optional trends -> attributed operational context.

Public: main message -> one primary visual -> explanation/limits -> reachable supporting counts -> source/methods.

A new stakeholder is a genuinely new configured profile, not merely the already existing public-health-expert profile. Different defaults must differ in information architecture, not only titles/colours.

## Workspace ownership and safety

Conceptual storage separates catalogue/recipes, immutable originals, incomplete work, accepted runs, validated cache, reviews and approved exports. This is not permission to move current directories before a migration. Application code/defaults/public fixtures remain in Git; steward data, logs/private profiles are not automatically committed.

Enforce input/resource limits and path containment before upload acceptance. Do not execute arbitrary code, Quarto fragments or expressions from profiles. Escape authored content and distinguish it from generated findings. A public export must actually omit restricted raw data/source literals; collapsing sections is not access control. Record retention/deletion explicitly and never treat accepted inputs/runs as disposable cache.

HTML composer support comes first. Static/PDF behavior is capability-specific and tested separately. Scheduling, collaboration, translation workflow, remote hosting and advanced inference/surveillance are later separately approved work, not automatic consequences of the builder.
