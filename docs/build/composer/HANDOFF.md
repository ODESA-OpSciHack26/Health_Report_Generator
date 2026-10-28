# Composer isolated integration lane: technical build handoff

Status: operational handoff; product implementation not started by this document. Prepared 28 October 2026.
Product integration: integration/steward-ready-v1.
Exact seed: 0cb8dd095a29760ca7b0dc45167538b938b3a6c7.
Isolated lane: build/composer.
Frozen reference: m4/frozen-descriptive-reports at c72bd54f69300b8e79bb967c201529d48625ae45.

## 1. Mission and authority

Build the documented unified reporting product through tested vertical slices, continuous internal integration and human visual revision. Support captured reference data or general tables, confirmed interpretation, supported selection, three distinctive presets, saved custom compositions, adjacent evidence inspectors, verified publication and portable replay.

Read the existing [plan](../../integration-plan.md), [contracts](../../integration-contracts.md), [data workflow](../../data-workflow.md), [workspace](../../steward-workspace.md), [presentation adaptation](../../presentation-adaptation.md), [inspector decision](../../decisions/inspectable-blocks.md), [acceptance](../../integration-acceptance.md), [preservation policy](../../workflow-preservation-policy.md) and [conflict dispositions](../../b0-conflict-dispositions.md). They remain product authority. This handoff defines execution, not a competing roadmap.

Use [requirements.json](requirements.json) to distinguish required, optional, decision-required and deferred scope. Do not silently downgrade a requirement, implement historical examples literally or advertise deferred surveillance/inference. Optional format and generic PDF/static decisions need explicit disposition before final acceptance.

## 2. Branches and integration

Reserve design/contracts, design/comparison-inspector, design/csv-interpretation, design/composer-interface and design/verification. These are Git work branches, not duplicated application directories. Create each from the current build/composer tip when assigned, not all from a stale original seed. Their briefs are in tasks/.

Internal task PRs target build/composer. One coordinator serializes integration after applicable checks and independent review, subject to actual permissions and approval mechanisms. Frequent small commits and fix/revert commits are encouraged; no shared-history force-push or silent rebase. An upstream synchronization is a recorded decision with affected checks rerun.

One umbrella draft PR, titled 'build: composer isolated integration lane', tracks build/composer into integration/steward-ready-v1. It remains draft/unmerged until explicit human promotion approval. The build lane is an experimental candidate, not another accepted base. Frozen/main/release refs remain unchanged. Branch protection is not installed by this document.

## 3. Runner and resource prerequisites

An actual runner needs Git/filesystem access, the locked report runtime, storage/compute, browser-testing tools and persistent task state. No chat response or handoff file starts an unattended process. Prefer separate clones for concurrent writers; linked worktrees require proof that container Git metadata/provenance remains accessible and correct.

Declare cost/time budgets, credentials, artifact storage and retention before execution. Default maximum concurrency is two implementation writers plus one independent verifier, with one integrator. Serialize shared build resources and never share an uncommitted worktree. After two unsuccessful repair attempts at the same unchanged failure, pause that task and provide a reproducible blocker; independent unblocked work can continue.

Use least privilege. No organization administration, deployment secrets, public preview hosting, private-data publication or implicit input refresh. Dependency setup follows the approved acquisition boundary. Reproduction uses captured inputs. This operating contract never overrides connector confirmation rules or access controls.

## 4. Roles and file ownership

Coordinator/integrator: owns task decomposition, dependency/interface decisions, the build tip, requirement/evidence ledger and integration order. Assign file ownership before edits and resolve overlap before parallel work.

Data implementation: owns interpretation, selection, immutable record identity, saved methods/results and replay. It does not invent semantics from labels.

Presentation implementation: owns registered blocks, presets, scoped styling, common inspector and composer controls. It consumes saved verified results rather than recalculate scientific metrics.

Independent verification: owns expected fixtures, adversarial/integrity checks, baseline comparison and review findings. It must not be the only author/approver of the implementation being tested. Model agreement is not evidence that a result is true.

Human product owner: approves visual direction, scope changes, material scientific/disclosure decisions and final promotion. Record actual reviewer identity in controlled evidence when review occurs; technical instructions need no personal names.

Each task has one primary writer and exact allowed paths/interfaces. Coordinate changes to shared schemas, CI, locks and renderer/verifier boundaries. Every task PR includes the mandatory workflow-preservation section and requirement/evidence references.

## 5. Checkpoints

G0: verify seed/docs/code/environment, close or record remaining B0 issues and establish clean baseline evidence. PR #9 checks passed on 4c0a7ae5996e30ae07eb070847a334f558d48e68, not as a new execution of seed 0cb8dd095a29760ca7b0dc45167538b938b3a6c7. Check documentation links/status/licence consistency, including the previously identified source-data README paragraph; do not edit licence/citation authorship. Record actual commands and limits.

G1: minimal strict contracts for one complete comparison: interpretation/scope, component instance, method/result, evidence and effective composition. Provide deterministic resolution, fixtures and rejection tests without silently changing request v1/v2 or calculations. Broader schemas grow through explicit decisions; do not spend the whole build specifying hypothetical methods.

G2: first live vertical slice. Captured fixture -> exact relevant records -> existing reference comparison -> full-precision saved result -> plotted subset -> registered graph -> adjacent expandable data/calculation/analysis-code/render-code/reproduction -> independent verification. Preserve current eligibility/non-positive-baseline behavior. This is the first mandatory visual checkpoint.

G3: generalize existing blocks and three distinct presets. Add supported table interpretation, selection and staged multi-measure/group/ungrouped-count contracts with fixtures. Contracts unlock parallel work, but prioritize working end-to-end output over disconnected components.

G4: complete authoring: source selection/upload, compact confirmation, analytical scope, discover/clone profiles, add/remove/duplicate/reorder/configure, actual preview and save/replay. UI/CLI resolve the same request. Second mandatory visual checkpoint; mock-only controls are not completion.

G5: complete versioned publication/verifiers, failure safety, cache invalidation, export/disclosure and all required route/format decisions. These concerns start in G1/G2 and develop throughout.

G6: final revision and acceptance. Run the requirement matrix from clean compatible source, supply actual reviewed artifacts, resolve issues and deliver reproduction/handover. Human approval, not a green build alone, permits promotion.

Map checkpoints onto B1-B7; B6 integrity remains cross-cutting. Existing product stages are not replaced.

## 6. Visual loop and revision

At G2/G4/G6 provide actual interactive output, desktop/narrow screenshots, collapsed/expanded inspector states, navigation/table/control findings and a short delta. Identify commit, fixture/recipe, render/evidence manifests, environment and untested items. Only synthetic or reviewed open fixtures enter shareable artifacts. Follow [REVIEW_AND_RESUME.md](REVIEW_AND_RESUME.md).

Screenshot comparisons supplement numerical/accessibility/scientific checks. Never auto-approve reference screenshots or widen tolerances to hide regressions. Keep bulky raw artifacts in approved run/CI storage, not ordinary code commits.

Convert human feedback into task/requirement IDs and candidate-linked dispositions. Cosmetic revisions can proceed within agreed semantics; data/method/schema/disclosure/scope changes require explicit decisions and migrations/tests. Continue independent backend work while awaiting visual feedback, but do not accept/promote around unresolved blocking decisions.

## 7. Invariants and stopping

Retain captured source, original records, explicit interpretation/selection, domain QC, full precision, saved results, shared parameterized source, exact artifacts, version-compatible verification and replay. Separate numerical/display identities. Missing/unavailable is not zero/normal. Generic tables do not inherit domain attribution/denominators/statuses.

Inspectors use retained evidence/code, not moving remote branches; expansion performs no calculation. Public exports actually omit restricted bytes, including scripts/downloads/source literals. Collapse is not access control. No arbitrary executable configuration or false acceptance claims.

Pause the affected task for unexplained drift, lost lineage, unknown disclosure, broken replay, unsafe paths, wrong source identity, unapproved contract changes or proposed weakening/deletion of tests. Preserve evidence and supply the smallest corrective options. Do not reset/delete another writer's state or overwrite accepted artifacts to recover.

## 8. First assignment and completion

After bootstrap/policy alignment: coordinator reads governing documents/ledger, verifies refs/environment, establishes B0 dispositions and baseline with new isolated output names, then assigns design/contracts the minimal G1 slice. Verification starts baseline/adversarial fixtures in parallel. Presentation may prepare a fixture visual but does not replace production entry points before contracts are ready.

Task handoffs contain objective, dependencies, base SHA, allowed paths, interfaces, fixtures, commands/exits, artifacts, migration/backout, limits, ownership and next action. Completion requires review/checks, not merely written code.

Every required ledger entry needs implementation and independent evidence; visual entries also need human disposition. Optional/deferred/decision-required entries need explicit handling. Final review can require further commits/render cycles in this lane. Promotion, release/tagging/deployment, protection/deletion and private-data distribution are separate authorized actions.
