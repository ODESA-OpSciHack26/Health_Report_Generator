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

Block-level reader experience, parameters, evidence requirements, failure behaviour and
implementation status are captured in [BLOCK-CATALOGUE.md](BLOCK-CATALOGUE.md). Gate A/B1
(explicit report topic scope and recipe v2 topic binding) is a completed implementation
checkpoint at `181f206382f8c71a6a58f912ef02b507b0dd1280`, retaining its documented
limitations and scoped review; the next analytical implementation candidate is the
separately gated saved-series block.

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

## 9. Current candidate and status (31 October 2026)

Status: documentation reconciliation of an accepted local candidate. Not a release, not remote
publication, not promotion out of the isolated lane, and not a claim that every requirement is met.

### 9.1 Identity

| Item | Value |
|---|---|
| Repository | local `composer-sandbox` (not the canonical `Health_Report_Generator` remote) |
| Branch | `design/contracts` (internal task branch; no upstream configured) |
| Accepted commit | `6ccc58177ccda018a3ff39efe9106ed965da5c65` — "Add neutral CSV composer with verified reuse and shared visual pass" |
| Parent | `d33d3e10bd5de9a6e2aff982c344bdbb80cc61e6` (Round B1 checkpoint) |
| Worktree at acceptance | clean; nothing pushed |
| Lane tip before publication | `build/composer` = `0b9975fca19f762bec2566588495c974d7cab674` (local; the remote was `72b80d9`) |
| Lane tip after merge (verified) | `origin/build/composer` = `a1aab9b64586ddcecd38a80df93349ea054f044b` — merge commit of PR #1 |
| Product integration | `integration/steward-ready-v1` = `0cb8dd0` (local and origin) — untouched |

Status at reconciliation (31 October 2026, before publication): everything from `0b9975f` onward
existed only locally and `design/contracts` was not on the remote. That paragraph is kept as
history. After PR #1 merged (2026-10-31T21:28:53Z), `design/contracts`, its 21 commits and the merge
commit `a1aab9b` are all on the remote; the merged tree is identical to the accepted candidate.

### 9.2 What the candidate implements

Neutral CSV composer, end to end: bounded capture (20 MiB / 100k rows / 100 columns / 64 KiB
cell), compact interpretation confirmation with explicit roles, prepared rows with stable
1-based ordinals, descriptive analysis (inclusive quartiles, sample SD, no pooling, repeated
key-period records preserved), neutral rendering through the shared report source, explicit
`local-audit` versus `restricted-share` disclosure with permitted evidence only, per-instance
presentation controls (groups, displayed periods, axis-label policy, statistics columns,
precision, layout, height, panel columns/scales), report-bound "Data & sources", dataset-scoped
saved-report history, verified reuse (canonical request identity plus package validation, no
re-render), "edit a copy", and a shared visual pass for both modes.

Health behaviour is preserved: canonical bundles, four stakeholder options, existing drafts,
reports, titles, duplicates and period semantics are untouched; the health suites and R smokes
remain green.

### 9.3 Status matrix

States: **verified** (implemented with executed evidence), **partial**, **not implemented**,
**decision required**, **deferred**. Evidence is local-only unless stated; no state implies
product promotion or human acceptance of the whole product.

| Stage | State | Basis |
|---|---|---|
| B0 | partial | Documentation reconciled here; G0 still open because the seed was never executed |
| B1 | verified | composition-recipe/2 validators, capability gating, disclosure and evidence contracts, with rejection tests |
| B2 | partial | shared parameterised source and registered renderers exist; per-block adjacent inspectors and structurally distinct presets are not complete |
| B3 | verified for the CSV slice | bounded upload, confirmed interpretation, stable record identity, UI/CLI replay parity; multi-measure/group shapes not started |
| B4 | not implemented | no dynamic profile discovery or versioned composer publication verifier |
| B5 | verified for the neutral composer | authoring, preview, save/replay, history and reuse; health editing remains the existing custom-draft flow |
| B6 | partial | provenance, disclosure and content-keyed reuse lifecycle in the CSV lane; no combined lifecycle across all routes |
| B7 | not implemented | combined IDD/general-table/default/custom acceptance not attempted |
| G0 | not closed | baseline recorded at `72b80d9`, not at the seed |
| G1 | verified | strict contracts |
| G2 | partial | reference comparison renders; adjacent per-block inspector absent |
| G3 | partial | table interpretation done for one group/measure/optional time; presets and multi-measure not |
| G4 | partial | composer UI/CLI parity; cloning a genuinely new profile not implemented |
| G5 | partial | no-replace publication, digest validation, disclosure omission and reuse invalidation; no versioned composer verifier |
| G6 | not started | final acceptance not attempted |
| R01 | partial | baseline evidence recorded (EV-BOOT-001/002), seed never executed, G0 open |
| R02 | verified | strict deterministic contracts and rejection tests |
| R03 | partial | comparison exists; complete adjacent inspector not |
| R04 | partial | three canonical audiences render from the shared source; "structurally distinct presets" not re-assessed |
| R05 | verified | confirmed table interpretation, original records retained, UI/CLI agree |
| R06 | not implemented | multi-measure/group/ungrouped counts are Slice C-E work |
| R07 | partial | add/remove/duplicate/reorder/configure and edit-a-copy; clone-new-profile absent |
| R08 | verified | labelled previews and saved recipes replay through UI and CLI |
| R09 | partial | digest/provenance validation in the lane; no versioned composer evidence verifier |
| R10 | verified | failed runs preserve accepted output; content-keyed analysis compatibility and reuse validation |
| R11 | verified for neutral CSV | restricted packages exclude values, records and retained files, enforced server-side |
| R12 | not started | end-to-end acceptance across data/profiles |
| R13 | verified in exercised scope | no numerical drift from presentation work; old recipes remain valid; frozen reference unchanged |
| R14 | decision required | generic PDF/static parity still undecided |
| R15 | deferred | optional formats/encodings |
| R16 | deferred | surveillance/inference |
| R17 | verified with owner visual acceptance (scoped) | DOM structure/wiring checks plus the owner's desktop and narrow-layout review |
| Round A (CSV slice plan) | done | baseline record |
| Round B (neutral CSV) | verified and accepted | this candidate |
| Rounds C-E | not started | count modes, multi-measure, profiles/dataset versions, batch |

### 9.4 Evidence

Executed on the accepted tree (all local, outside the repository):

- Focused composer/CSV/display suites: 103 passed, 2 skipped — `~/.state/composer-bootstrap/csv-b-check/evidence-20261031T201934Z`.
- Maintained suite 894 passed / 4 skipped with both R smokes clean — `suite-20261031T202257Z`.
- DOM harnesses: journey 62/62, conflict gate 18/18, shared editor 0 — `node-20261031T201852Z`.
- Owner fixtures rendered through the pinned image: 34/34 — `presentation-20261031T190134Z`.
- CLI replay parity: 25/25 — `replay-20261031T122917Z` (earlier run at the same code path; not re-executed for this documentation turn).
- Candidate manifest: `~/.state/composer-bootstrap/csv-b-check/candidate-manifest-20261031T202637Z`
  plus the closure record `closed-20261031T2030Z` (inside the same root).

Runtime for those runs: image `sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8`
(R 4.3.2, the image's `/opt/health-report-venv`). These are local paths; nothing here is
published or remotely checkable.

### 9.5 Owner dispositions and accepted limitations

The owner accepted, by direct visual review, the exercised desktop and narrow-layout behaviour of
P1–P4, Data & sources, saved-report history and verified reuse, the shared visual pass, the
compact dataset selector with its expansion control, single-line section rows, and the structural
preview area. That is scoped acceptance of the exercised journeys — not accessibility,
cross-browser, large-group, scientific or publication acceptance, and not acceptance of reports
the owner has not seen.

Accepted limitations: structural preview bounded to the first 100 rows and 20 columns with no
paging; long-cell inspection via `title` tooltips only; history capped at the newest 20 reports
without pagination; status unification partial; health source-card capture/release dates "Not
recorded" where the bundle lacks them (never inferred); no broad accessibility or cross-browser
acceptance; reuse not recorded as an access event; pre-change reports carry no reuse identity.

### 9.6 Remote relationship and first safe next action

As recorded at reconciliation (31 October 2026, before publication): local acceptance, a commit in
this repository, publication to `origin`, integration into `build/composer` and promotion to
`integration/steward-ready-v1` were five different states, and only the first two existed. That
paragraph is kept as history.

Verified after the merge (read-only, same day):

- PR #1 "build: neutral CSV composer candidate (design/contracts)" was merged by the owner on
  2026-10-31T21:28:53Z with 21 commits; base `build/composer` @ `0b9975f`, head
  `design/contracts` @ `2bd1bed`.
- Merge commit `a1aab9b64586ddcecd38a80df93349ea054f044b`, a true merge: `0b9975f` and `2bd1bed`
  are both ancestors, and `git diff --stat 2bd1bed a1aab9b` is empty — the merged tree is identical
  to the accepted candidate.
- `origin/build/composer` now equals `a1aab9b`; `integration/steward-ready-v1` remains `0cb8dd0`.
- Publication and internal integration of this candidate into the experimental lane are complete.
  Product promotion, final combined acceptance, release and deployment have **not** occurred.
  Runtime evidence remains local, and the merge is not a fresh test run.

First safe next action: the remaining product work is unchanged — the R14 decision, slices C–E,
B4/B7 and G6 — on a new task branch from the lane tip after explicit assignment. Nothing is
promoted.
