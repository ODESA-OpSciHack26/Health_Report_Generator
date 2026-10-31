# Neutral CSV — Slice B durable handoff

Status (superseded 31 October 2026): the work described here was accepted by the owner, committed
as `6ccc58177ccda018a3ff39efe9106ed965da5c65` and closed. This file remains the historical record
of the slice and its evidence; **current status, the requirement ledger and the next action live in
[HANDOFF.md](HANDOFF.md) §9**. The paragraph below records the state at the time of writing.

Original status: Slice B CODE COMPLETE, NOT ACCEPTED. Written 2026-10-31T09:4xZ (UTC) by the previous
agent at session end. The implementation is stopped; human browser review and resolution of the
open findings in §6 are pending. Slices C–E are NOT authorised. Nothing in here is a
permission to commit, push, stage, reset, stash, delete, clean, restart, recreate containers
or rotate credentials — those all require separate owner approval.

Read first: [ROUND-CSV-PLAN.md](ROUND-CSV-PLAN.md) (scope/ownership + slice status),
[REVIEW_AND_RESUME.md](REVIEW_AND_RESUME.md), [HANDOFF.md](HANDOFF.md),
[ROUND-B1-CLOSEOUT.md](ROUND-B1-CLOSEOUT.md), docs/integration-plan.md,
docs/integration-contracts.md, and the neutral CSV implementation brief (2026-10-30).

---

## 1. Exact current candidate / worktree state

- Repository: /home/builder/composer-sandbox. Branch: `design/contracts`.
- HEAD: `d33d3e10bd5de9a6e2aff982c344bdbb80cc61e6` (Round B1 checkpoint; parent
  `a2cc51034a67b821475f374f64d84ce9166b3027`). Single worktree at the repo root, no stash,
  index empty, EVERYTHING UNSTAGED AND UNCOMMITTED. `git diff --check HEAD` exits 0 (one
  trailing-space fix was applied to report_helpers.R before the manifest was taken).
- Status: 13 modified + 7 untracked = 20 paths. Full list with sha256 in the source manifest:
  `~/.state/composer-bootstrap/csv-b-check/candidate-manifest-20261031T094156Z/`
  (`source-hashes.sha256`, `git-status.txt`, `head.txt`, `branch.txt`); pointer:
  `~/.state/composer-bootstrap/csv-b-check/current-candidate-manifest-pointer.txt`.
  Manifest self-checksums: source-hashes.sha256
  9b63fc38d9268e6a80a17a408d50dbe7007155bdfa00bbd914879c8ebb19bac7; git-status.txt
  2c79c7cf38efbd07a6088bdf9b3af62e467a0584ebc89c65554d0a25d075e5bf.

Modified (13): scripts/health_pipeline/composer_library.py, composer_workspace.py,
config/composer/block-labels.json, publish.py, report_shared.qmd,
templates/methods.qmd, templates/report_helpers.R, src/composer_site.py,
src/composer_web/app.css, src/composer_web/app.js, src/composer_web/index.html,
tests/js/minidom.mjs, tests/r_composition_smoke.R.

Untracked (7): docs/build/composer/ROUND-CSV-PLAN.md,
scripts/health_pipeline/neutral_describe.py, neutral_library.py, neutral_publish.py,
tests/js/csv_dom_check.mjs, tests/test_composer_csv.py, tests/test_neutral_describe.py.

## 2. Implemented behaviour (key files and interfaces)

BACKEND / DATA LAYER
- scripts/health_pipeline/neutral_describe.py (new): bounded capture
  (20 MiB / 100k rows / 100 cols / 5M cells / 64 KiB cell; UTF-8 + BOM CSV/TSV), compact
  role suggestion, confirmation validation, prepared rows (stable 1-based ordinal, raw
  strings verbatim, float-or-null measure, ISO period-or-null), explicit descriptor
  (inclusive quartiles + sample SD, no pooling, repeated group-period keys counted),
  repeatable verification (verify_repeatable). Schema tags:
  health-report/neutral-{analysis,interpretation,prepared}/1.
- scripts/health_pipeline/neutral_library.py (new): neutral block vocabulary
  (intro, data-overview, values-by-group, values-over-time, data-quality, limitations,
  reproduction), recipe validator, default/starter recipe, id allocation, capability gating.
  NEUTRAL_AUDIENCE = "neutral-overview".
- scripts/health_pipeline/neutral_publish.py (new): neutral provenance records (block
  records with analytical/instance identities over the analysis digest, composition record),
  shareable-safe (no absolute recipe path; coverage instead of value statistics).
- scripts/health_pipeline/composer_library.py: neutral block types REGISTERED but
  non-composable — the health editor/inventory never offers them; BLOCK_ORDER extended so the
  shared label loader stays in lockstep. block-labels.json: neutral names added (single source).
- scripts/health_pipeline/publish.py: KNOWN_BLOCKS extended; validate_composition accepts
  data-overview/values-by-group/values-over-time/data-quality (v2, closed field sets,
  time_period validation); `_is_neutral_bundle` + `_render_neutral` (QMD
  `input_kind=neutral`, doc titles parameterized per document, evidence package without raw
  bytes, reproduction/ composition.json).
- scripts/health_pipeline/report_shared.qmd + templates/methods.qmd: `input_kind`
  canonical|tabular|neutral; `doc_title` parameter (health defaults untouched); neutral branch
  calls `compose_neutral_html` / `neutral_methods_html`.
- scripts/health_pipeline/templates/report_helpers.R: neutral bundle reader,
  neutral registry + block renderers, neutral methods page, `nvl` helper. Disclosure-safe
  defaults: overview = coverage + confirmed reading only; values-by-group = group counts with
  "withheld" summary column (no chart, no median/min/max); values-over-time = availability
  matrix with "not disclosed" cells; missing stays "missing"; repeated values never summed.

SITE / SAVED STATE
- src/composer_site.py: GET /api/csv (document: datasets, confirmation incl. preview +
  suggestion, analysis summary, recipe, composer rows), POST /api/csv/upload (bounded
  multipart; `_multipart_file`; immutable store work-root/csv-datasets/<digest>/),
  POST /api/csv/confirm (validates, prepares, describes, verifies, writes immutable
  interpretation/prepared/neutral-analysis), POST /api/csv/generate (validates recipe,
  single-slot job, frozen composition snapshot, replay command), POST /api/csv/edit
  (per-dataset draft store work-root/drafts/csv/<digest>/editor.json; move-up/down,
  exclude/include, duplicate, delete-instance, set-title ≤80 chars); `csv_recipe_for`,
  `_csv_composer_blocks`, `render_preview` is neutral-aware in composer_workspace.py.
- Health routes/presets/drafts untouched; health bundles never reach the neutral composer and
  neutral recipes never reach health blocks (validator enforced server-side).

FRONTEND (src/composer_web/)
- index.html: top-level "Health reports" / "Your CSV" route tabs; CSV panel cards: table
  (dataset list + upload + preview), confirmation, sections (composer), report + replay.
  Health panels unchanged (wrapped in #health-panel).
- app.js: `switchRoute`, `loadCsv`, `selectDataset`, `renderCsvPipeline` (preview table,
  passport, confirmation form), `submitInterpretation`, `csvEdit` (adapter over
  /api/csv/edit), `renderCsvComposer` (include/remove/reorder/duplicate/title, absent-type
  rows), `uploadCsvFile`, `generateCsv`, `pollCsv` (shared single-slot job loop, safe failure
  text, replay command disclosure). app.css: CSV layout styles.
- tests/js/minidom.mjs: `Element.fire()` now provides preventDefault/stopPropagation (the DOM
  contract the harness needs; existing behavior otherwise untouched).
- tests/js/csv_dom_check.mjs (new): transcript-driven harness for the CSV journey
  (route switch → dataset card → upload → preview → compose → generate → replay).

TESTS
- tests/test_neutral_describe.py (new, 13 tests): capture/prepare/describe/verify/limits.
- tests/test_composer_csv.py (new, journey tests added): snapshot + time-series journeys,
  edit persistence, capability separation, rejections, CLI replay; plus
  `test_csv_dom_journey_renders` (Node-gated) which builds its fixture from a real Site.
- tests/r_composition_smoke.R: label-set assertion updated (deliberately) to the shared set
  incl. the four neutral blocks; comment explains why.

## 3. Slice B requirement status (requirement → status, evidence)

IMPL = implemented with automated evidence; UNV = unverified; INC = incomplete; BLK = blocked.
Green suites are NOT acceptance; see §6 open findings.

- Route separation (Health reports / Your CSV) — IMPL (frontend + backend;
  test_composer_csv capability tests; DOM harness "default route is Health reports").
- Bounded upload + structural preview — IMPL (multipart capture tests, preview in DOM harness,
  size/row/column/cell limits in neutral_describe tests).
- Compact confirmation with actionable errors — IMPL (confirm flow, rejections; UI confirmed
  interpretation shows and re-validates; "Accept/Update interpretation" button).
- Dataset passport — IMPL (UI passport line; dataset.json fields).
- Neutral Overview starter composition — IMPL (default recipe; real render 17/17 checks).
- Supported neutral block configuration, titles, duplication, ordering — IMPL (draft store
  edit tests; DOM harness section rows; title 80-char limit). BROWSER interaction UNV.
- Generation progress + safe failure — IMPL (job loop; failure text tested via stub only;
  real failure-path rendering UNV).
- Reopening saved dataset-bound draft and finding its accepted report — IMPL for the draft
  (csv_recipe_for persists; reopen test) and reports (jobs list shows csv jobs with origin;
  show-here for csv jobs implemented in UI, UNV by DOM harness).
- Matching saved-request CLI replay — IMPL (replay_command recorded in job; asserted in
  journey tests). Standalone CLI replay executed and independently compared: UNV (§6).
- Source/profile/block compatibility enforced server-side — IMPL (recipe validator, block
  allowlists; capability separation test).
- Health four-stakeholder preservation — IMPL (health suites green: 818 passed/3 skipped
  overall; R smokes green; health titles unchanged). Real health REPORTS not re-rendered: UNV.
- Disclosure policy — IMPL for withholding defaults (scan 0 issues) BUT the explicit
  permitted-numerical-view / restricted-export path is NOT implemented → open finding F1 (§6).
- Naming/duplication/titles from Round B1 preserved — IMPL (labels single-source; titles/draft
  machinery reused; maintained recipes untouched).

## 4. Authoritative checks — commands, exits, locations

Evidence root: ~/.state/composer-bootstrap/csv-b-check/ (every run dir has exits.txt and logs).

- Focused: `bash ~/.state/composer-bootstrap/csv-b-check/run.sh`
  → neutral-describe=0, site-regression=0, workspace-regression=0, publish-validator=0
  (focused CSV/describe suite green inside the pinned image; includes 1 Node-gated skip in
  pytest because the pinned image has no Node).
- Node-gated DOM harnesses: `bash ~/.state/composer-bootstrap/csv-b-check/run_node.sh`
  (Node 26.12.1 bound READ-ONLY into the pinned image; no image or lock change; PATH prepends
  /opt/node-tools/bin) → csv-dom-journey=0 (CSV journey 11/11) and shared-editor-dom=0
  (existing shared-editor + rendering harness checks).
- Full maintained suite + R smokes: `bash ~/.state/composer-bootstrap/csv-b-check/run_suite.sh`
  → r-preview-smoke=0, r-composition-smoke=0, maintained-suite=0 —
  818 passed, 3 skipped / 0 errors (skips = the Node-gated harness tests).
- Real neutral render:
  `docker --context rootless run --rm ... -e NEUTRAL_WORK=/evidence/rendered/work
   <mount repo ro, render_neutral.py ro, /evidence>
   sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8
   /opt/health-report-venv/bin/python /render.py` → 17/17 checks.
- Disclosure scan: `python3 ~/.state/composer-bootstrap/csv-b-check/disclosure_scan.py` → 0 issues.
- Pinned image: sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8
  (composer-report:bootstrap-72b80d9); R 4.3.2; venv python at /opt/health-report-venv/bin/python.
- Rendered artifacts (reviewable as static files; same content the service serves):
  report.html ~/.state/composer-bootstrap/csv-b-check/rendered/rendered/work/out/report.html
  (~894 KB), methods.html, provenance.json, data/, reproduction/composition.json.
  Fixture: synthetic 4-row city/value/year table (labelled software test fixture, NOT real data).
- Superseded failures preserved: the earlier renders/checklist versions and the two failed
  node-harness attempts (csv-dom timed out on fixture shape; minidom preventDefault) are
  recorded in the run logs; each was a harness defect fixed in the harness, not in the product.
- Node negative-control semantics: `test_rendering_harness_still_catches_the_chained_append_defect`
  asserts that chaining `Element.append()` still THROWS (as in a real browser) against the
  fixed app.js — i.e. the harness would catch a re-introduction of the original defect. A PASS
  there means the guard is present and the DOM contract is enforced; it is NOT a layout,
  accessibility or browser engine check.
- Repro without overwriting: use a FRESH evidence dir whenever you rerun; the harness scripts
  create new timestamped dirs. Never rerun in place (§7 first safe steps).

## 5. Review-service incident — record

- The protected review container (Round B1 service, container id `e6c0233ca79e`, name
  `composer-site-review`) was ACCIDENTALLY REMOVED by the previous session while clearing
  CSV review-scaffolding containers, despite preservation instructions. This is an incident.
- It was re-created from preserved parts: image sha256:1ddf322f…, launcher
  b-round-b1-20261029T232154Z-78941/review/{start.sh,forwarder.py}, same mounts:
  /home/builder/composer-sandbox → /app (ro), baseline-lJXSvvGc/output → /inputs (ro),
  b-round-b1-…/review → /review (rw), same published port 127.0.0.1:2719→2719/tcp, same
  container name. A FRESH per-run token was written at start (by design, every start rotates
  it, under the review work root, as `access-token.txt` (mode 600; the absolute path is not
  recorded in this document). Never print/transmit token contents.
- Verified vs assumed:
  - Verified (read-only): the re-created container is Up and bound to 127.0.0.1:2719; the work
    root contains drafts/custom/{researcher,health_institution}, drafts/researcher and the
    jobs directory with the previously recorded job set (nine saved reports were directory-
    counted before the incident and are present; contents were NOT re-hashed in this session —
    the snapshot restore-test hashes from the R1 milestone are the authoritative byte checks);
    the site printed its usual startup lines.
  - Assumed: that the owner's Windows browser can open http://localhost:2719/?token=… as
    before. From inside this WSL session rootless-Docker published ports are NOT reachable
    through the sandbox loopback, so live reachability from the owner's machine is UNVERIFIED
    here and was not asserted.
- Source served: /home/builder/composer-sandbox mounted read-only — i.e. the CURRENT uncommitted
  CSV candidate serves the CSV routes on the re-created service; the pre-CSV Round B1 app is
  no longer what a fresh load of / serves (endpoints are additive, health behaviour unchanged
  in the shared tree). If the owner needs the exact pre-CSV app for review, serve from the
  preserved Round B1 commit d33d3e10 via a separate checkout — do not change this service.
- No further service changes are authorised. The stray CSV review-scaffold containers were
  removed and are not to be re-run; the restore uses only the preserved R1 launcher scripts.

## 6. Open product/verification findings (carry forward; do not fix in this handoff)

F1 DISCLOSURE MODEL: neutral blocks render availability-only/"withheld" displays by default
(data-overview coverage, values-by-group "withheld", values-over-time "not disclosed"). There
is NO implemented explicit permitted numerical view (an opted-in analysis/statistics view with
a clear consequence) and NO separately restricted row-level export. Decide whether the model
should be: defaults withhold + explicit permitted numerical view + separate restricted audit
export (recommended direction), rather than an availability-only default.

F2 COMBINATION REJECTION: the current code does NOT reject a recipe that combines a
withholding block with an incompatible "disclosure" expectation (e.g. values-by-group WITHOUT
the disclosure choice silently renders withheld). Decide whether generation should fail with an
explicit incompatibility message instead of silently changing the display's meaning.

F3 FULL SLICE-B DEMONSTRATION: the rendered demo shows the time-series composition (overview,
time, quality, limitations, reproduction). The complete required Overview experience — one
compatible primary visual, actual findings, adjacent evidence — is only partially demonstrated
(the primary visual is withheld in the current disclosure default). A snapshot demo and a
composed-package evidence walk (inspectors, data/ artifacts, methods) remain to be produced.

F4 CLI REPLAY INDEPENDENCE: the recorded replay_command was asserted in tests, but a saved
website request was NOT replayed through the CLI in an isolated run and independently compared
(section ids, values, provenance) against the site-generated package. That check is required
before the slice can be considered verified.

F5 REAL-BROWSER JOURNEY: the complete upload → confirm → compose → disclosure choice →
generate → reopen journey is implemented and DOM-harness-tested but NOT exercised in a real
browser; accessibility, keyboard, narrow layout and live interactivity are unverified. The
review-service reachability question (§5) gates how that review happens.

F6 CHECK SCOPE: DOM harness = structural rendering + request transcript; NOT layout/visual/
accessibility. Health regression = 818-pass maintained suite + R smokes green on the merged
tree, but no real health report re-render was run for this candidate.

## 7. Preservation status

- Round B1 checkpoint committed: `d33d3e10bd5de9a6e2aff982c344bdbb80cc61e6` (branch
  design/contracts).
- Earlier USB backup: completed and owner-verified (repo-at-d33d3e1.bundle, checksum
  9a3571e07de33700eb224a5ed530fcd90c151a07384bfcc9352af0081e086e65).
- CURRENT UNCOMMITTED CSV CHANGES: NOT included in the USB backup — treat the working tree as
  the only copy of the CSV candidate (plus the source manifest above).
- Remote publication and remote-backed recovery: pending (no host credential; unchanged).
- Approved housekeeping already completed (restore-test dirs, staging parts, caches); NO
  further cleanup is authorised.

## 8. Known limitations and prohibited actions

Limitations: composed neutral reports are HTML-only; no composed PDF; no ungrouped/count modes,
multi-measure/group candidates, filter predicates or extended missing tokens (slice C);
Detailed/Brief profiles and dataset-version updates (slice D/E); live review reachability from
this session; no browser/accessibility acceptance; the CSV capture store is single-steward
local; the 818-pass suite is evidence, not acceptance.

Prohibited until separate owner approval: stage/commit/push/reset/stash/clean/delete, any
cache or evidence pruning, container or service recreation/restart (the restored review service
included), credential rotation, token printing, dependency changes, starting C–E, and treating
any green run from this session as human acceptance.

## 9. First safe next steps (for the new agent)

1. Verify state read-only: git rev-parse HEAD == d33d3e10…; git status -uall matches the
   manifest (§1); re-hash the 20 paths against source-hashes.sha256.
2. Read the brief + this handoff; then decide F1/F2 (disclosure model, combination rejection)
   with the owner — those are product decisions, not code fixes to start unprompted.
3. Produce the F3/F4 evidence: one CLI replay of a saved website request into a fresh evidence
   dir (record command/exit), independently compare against the site package; prepare snapshot
   and time-series demo packages with inspectors and evidence walk.
4. Resolve F5 with the owner: agree how the owner's Windows browser reaches the review
   service or the static artifacts; record actual browser scope, version and viewports.
5. Only then, with explicit approval: any C–E work, or any commit/push.
Reproduce candidates in FRESH evidence dirs; never overwrite existing evidence or the worktree.

## 10. Session close

Implementation stopped at this boundary. Only the whitespace fix described in §1 and this
handoff document were written; everything remains unstaged and uncommitted. No commit, no
service change, no cleanup beyond the documented incident restore.

---

## 11. Continuation — Slice B disclosure findings resolved (2026-10-31T10:2xZ, uncommitted)

Status: F1–F4 addressed with executed evidence; F5 (owner browser review) and the part of F6
that needs a real health re-render remain open. Nothing is committed, staged, pushed, deleted
or restarted. Slice B is NOT accepted.

### Candidate identity

- Repository /home/builder/composer-sandbox, branch `design/contracts`, HEAD unchanged at
  `d33d3e10bd5de9a6e2aff982c344bdbb80cc61e6`. Single worktree, no stash, empty index.
- 21 unstaged paths (13 modified + 8 untracked): the 20 from §1 plus
  `tests/js/csv_dom_check.mjs` changes; see
  `~/.state/composer-bootstrap/csv-b-check/candidate-manifest-20261031T101856Z/`
  (pointer file updated). `git diff --check HEAD` exits 0. A refreshed manifest
  `candidate-manifest-20261031T101934Z/` covers the tree after this section was appended; it
  is the manifest the pointer names and the one to hash against.
- The §1 manifest was re-hashed at session start and matched byte-for-byte: no intervening
  drift, so this section describes only this session's deliberate changes.

### What changed (and why)

1. **Disclosure policy is now part of the saved request** (`neutral_library.py`,
   `publish.py`, `composer_site.py`, `neutral_publish.py`, `report_helpers.R`). A neutral
   recipe may carry `disclosure: {schema, policy, permit_values, permit_records}`; health
   recipes are refused if they carry one. `publish.validate_composition` and
   `neutral_library.validate_recipe` accept it only for `audience=neutral-overview`.
2. **Two explicit policies.** `local-audit` embeds observed values, inclusive-quartile/
   sample-SD statistics, real ggplot charts and (optionally) `data/selected-records.csv`;
   its copy says the output is not automatically private once shared and that uploaded
   health-like data stays generic. `restricted-share` excludes values, statistics, charts of
   values and records, and its copy says counts/labels/groups/metadata can still disclose and
   that the package is not anonymous. Flags that contradict a policy are refused, never
   trimmed.
3. **Block compatibility (F2).** `disclosure_conflicts()` returns reader-facing conflicts;
   the document exposes them before generation, the UI blocks Generate, and
   `csv_submit`/`publish._render_neutral` both refuse an unresolved combination. A restricted
   report can use the new explicitly named `coverage-over-time` block (observation matrix:
   `observed` / `missing`, no values). "Values over time" is never silently downgraded.
4. **Restricted evidence is redacted, not merely unlabelled.** The restricted package ships
   `data/neutral-summary.json` (`health-report/neutral-restricted-analysis/1`) instead of
   `neutral-analysis.json`, and no records file; provenance states each artefact's status
   (original source, prepared, selected, plotted, export).
5. **Replay actually works (F4 defect).** `publish.py main()` built health provenance for any
   `--provenance` render and crashed on a neutral bundle; it now routes neutral bundles to
   `neutral_build_provenance`. The documented replay command was only ever asserted as a
   string before this session.
6. **Period column headers were malformed.** The values-over-time and coverage tables emitted
   period labels as bare text outside `<th>`; both now emit real `<th>` cells. Found by the
   real render, not by the DOM harness.
7. **Server-side required/capability checks.** `limitations` cannot be removed from a neutral
   recipe; a block that the confirmed dataset cannot support is refused with
   `csv_capability` before any job exists.
8. **UI**: new disclosure card (two radios, consequence text, records checkbox, conflict
   banner), Generate disabled on conflict or on an unavailable section, `coverage-over-time`
   in the vocabulary, corrected step numbering.

### Evidence (all re-run on the final source; each dir has logs and exits)

- Focused: `bash ~/.state/.../csv-b-check/run.sh` → 34 passed, 2 skipped (Node-gated),
  neutral-describe=0, site-regression=0, workspace-regression=0, publish-validator=0
  (`evidence-20261031T101634Z`).
- DOM harness (Node 26.12.1, pinned image, read-only binds): `run_node.sh` →
  csv-dom-journey **16/16**, csv-dom-conflict-gate **14/14**, shared-editor-dom=0
  (`node-20261031T101804Z`; per-check PASS lines are in the logs).
- Full maintained suite + R smokes: `run_suite.sh` → 825 passed, 4 skipped (the 3 previously
  Node-gated plus the new conflict-gate test), r-preview-smoke=0, r-composition-smoke=0
  (`suite-20261031T101348Z`). One expected assertion update in `r_composition_smoke.R` for the
  new registered label, with the reason in the comment.
- Real renders, three packages + a negative control:
  `rendered-disclosure-20261031T101555Z` → **33/33**. A = local audit time series (chart,
  values 120/150/90/110, median 115, records CSV), B = restricted share with
  `coverage-over-time` (0 observed values in HTML, embedded scripts, JSON, CSV or paths; no
  chart; `neutral-summary.json`), C = local-audit snapshot (per-group chart, median 12.5),
  D = restricted + values block refused by the CLI with both remedies named.
- CLI replay (F4): `replay-20261031T101824Z` → **21/21**. A real in-process Site confirmed,
  chose the policy, generated with the real renderer, then executed the job's own recorded
  command in `jobs/<id>/replay`. Compared: captured digest, dataset digest in both
  provenances, contributing ordinals, confirmed interpretation, recipe digest, disclosure
  policy, plotted numbers (6 values) against expectations derived by plain arithmetic in the
  script, overview counts/median/range, section order, and visible text. The visible text is
  **identical** after removing the website-only "Preview — not an accepted publication"
  banner; that banner is the only difference — no timestamp or typography drift.
- `disclosure_scan.py` (old probe) still reports 0, but its scope is the previous package and
  it is superseded by the per-package scan inside `render_disclosure.py`; do not cite it as
  coverage of this change.

### F1–F6 disposition

- F1 resolved: explicit `local-audit` (values, statistics, charts, optional records) and
  `restricted-share` (exclusions, honest caveat) with consequences stated in UI, report and
  methods. No global stripping: the private audit path renders numbers.
- F2 resolved: incompatible combinations are explained before generation, blocked in the UI
  and refused server-side and in the CLI; `coverage-over-time` is the only availability view
  and must be chosen.
- F3 resolved: A/C above are complete demonstrations with a primary chart, readable
  numerical findings, evidence files and methods; fixtures are labelled software fixtures.
- F4 resolved: see replay evidence. One real product defect was found and fixed.
- F5 OPEN: no real browser has rendered this. DOM checks are structural only.
- F6 explicit: DOM = structure/transcript; negative control = the conflict fixture shows the
  gate refusing; health = 825-pass suite + R smokes, still **no real health report re-render**
  for this candidate.

### Review service — current facts and the one action that needs permission

- Live container `0f29d07c6533…`, name `composer-site-review`, image
  `sha256:1ddf322f…`, Up since 2026-10-31T09:35Z, 127.0.0.1:2719, mounts unchanged
  (/app ro, /inputs ro, /review rw), token file path/mode recorded, never printed
  (`candidate-manifest-20261031T101856Z/service-inventory.txt`).
- Its **process predates this session's edits**. Static `app.js`/`index.html` are read from
  disk per request while the server process is old, so the live page now calls
  `set-disclosure` against a server that does not know it. The service is currently
  inconsistent and must not be used for the journey until the process is restarted.
- This session's WSL loopback **does** reach 127.0.0.1:2719 (401 without the cookie, 302 then
  200 with it) — the earlier "unreachable from here" note is wrong for this configuration.
  Windows `localhost` reachability remains unproven from here.
- Proposed (needs separate approval, one action): `docker --context rootless restart
  composer-site-review` — same container, image, mounts and port; the launcher writes a fresh
  token on start, so the owner must re-open the new `?token=` URL. Alternative without any
  service action: review the static packages under `rendered-disclosure-20261031T101555Z`.

---

## 12. Owner browser review — findings, root causes, corrections (2026-10-31T10:5xZ)

Status: all six review findings dispositioned; five were real defects (two of them pre-existing),
one was a served-version mismatch. Corrections are uncommitted. Candidate manifest for this
state: `candidate-manifest-20261031T105516Z` (the pointer names the latest refresh). The review service was NOT
restarted, so the page the owner tested is still the mixed build described below. Slice B is not
accepted; C–E not started.

### 12.1 Served-version identity (why the review contradicted the reported checks)

- Container `0f29d07c6533…`, name `composer-site-review`, image `sha256:1ddf322f…`,
  **StartedAt 2026-10-31T09:35:00Z, RestartCount 0**. PID 1 started 09:34:59Z.
- That process predates every edit in §11 (first edit 09:52Z). `/app` is a **live read-only
  bind**: `app.js`/`index.html` were re-read from disk on each request (new), while the Python
  modules in memory were the pre-disclosure build (old). `quarto` renders read the new R
  templates from disk, so the report text was new while the API was old.
- Proof captured read-only at `~/.state/.../review-incident-20261031T105306Z/`:
  the live `/api/csv` document has keys `[audience, blocks, datasets, mode, selected_digest]`
  (no `disclosure_options`), serves 7 blocks (no `coverage-over-time`), and reports
  `record_count: null` for all three owner-uploaded datasets.
- Therefore finding A ("Unknown section type") came from the old `_csv_apply`; finding B's
  "heading with no choices" came from the new `app.js` rendering an old document with no
  `disclosure_options`, and the report text "No disclosure choice is recorded" came from the new
  renderer reading an old recipe. Neither is reproducible against the candidate (API tests and
  `fixtures-20261031T104528Z`).
- The restart requested in §11 was never performed. **Restart is still required** for the live
  journey; see 12.5.

### 12.2 Real product defects found by the review (fixed)

- **C record counts (pre-existing).** `dataset.json` stores `row_count`; the API read
  `record_count` for both the list and the confirmation passport, so the UI printed
  "null records" / "? records". Both now derive `record_count` from `row_count` (falling back
  for older files); the UI still refuses to print a null. Test:
  `test_record_counts_are_served_before_after_and_on_reopen`, plus DOM checks on the card and
  passport.
- **D snapshot interpretation (pre-existing).** `_parse_period_value` fell through to
  `pd.to_datetime`, which reads "001" as 2001-01-01; the suggestion then offered `record_id` as
  time and preparation failed on the padded identifier. Periods are now a 4-digit year written
  as such (1000–9999) or an explicit ISO date (`YYYY-MM-DD`, optional time) — nothing looser.
  Numeric identifier columns (dense 1..n, or id/record/row/index/no names) are never suggested
  as measure or time. `time=None` now yields `has_time=false`, `period_count=0`,
  `missing.periods=0`, no period rows and no date anywhere. Tests:
  `test_suggestion_never_turns_identifiers_into_dates`, `test_period_parser_rejects_invented_dates`,
  `test_selected_no_time_stays_no_time_through_preparation_and_description`,
  `test_snapshot_with_no_time_records_no_observation_date`.
- **E neutral header (pre-existing).** The shared composed header printed the health line
  (`title · years · reference year NA`). Neutral now prints only confirmed scope —
  `Supplied dataset · N records · M groups [· K periods]` — and period rows disappear when no
  time column is confirmed. Checked in the real renders (F1/F2).
- **F duplicate diagnostic (pre-existing, two bugs).** (i) `repeated = rows − distinct periods`
  counted rows with a missing period as repeats (fixture 3 → 2 instead of 1). (ii) period records
  were de-duplicated by key, so a duplicated `North/2022` silently lost its second value in the
  table. Now `repeated_group_period_keys` counts pairs carrying >1 record,
  `records_in_repeated_keys` is reported separately (2 for fixture 3), every record keeps its
  period entry, and the cell renders `11 / 12`. A missing period is never a repeat. Tests:
  `test_repeated_keys_exclude_missing_periods_and_count_records`; real-render checks on F3.
- **Extra defect found while testing:** the dataset list was ordered by directory name
  (content digest), not capture time, despite claiming "newest first". Now sorted by
  `captured_at_utc`.

### 12.3 Disclosure UI hardening (beyond the mixed-state cause)

- The policy card is built once and updated in place, so a keyboard user does not lose focus on
  the radio or the records checkbox after each change; the controls are native
  `<input type=radio name=csv-disclosure-policy>` inside their `<label>` with `for`/`id`
  matching. The DOM harness asserts that contract (19/19 journey, 17/17 conflict gate).
- Generation is blocked when there is no choice, when a section is unavailable, or when the
  combination conflicts; the API (`csv_disclosure`), the job launcher and the CLI all refuse.
  A legacy draft without a choice stays readable and editable but cannot generate until one is
  chosen (`test_legacy_no_policy_draft_is_recoverable_but_requires_a_choice`).
- A refused request creates no job directory
  (`test_conflicting_combination_creates_no_job`).
- Historical job packages were not touched, rewritten or relabelled.

### 12.4 Evidence at this state

- Focused: 54 passed, 2 skipped (`evidence-20261031T105333Z`; 4 steps exit 0). Full suite:
  **845 passed, 4 skipped**, both R smokes 0 (`suite-20261031T104922Z`).
- DOM: journey 19/19, conflict gate 17/17, shared editor 0 (`node-20261031T104900Z`).
- Real renders, both policies + two CLI negative controls: **35/35**
  (`rendered-disclosure-20261031T105230Z`).
- CLI replay of a saved website request: **21/21** (`replay-20261031T105200Z`).
- Synthetic fixture demos through the site path with real renders: **31/31**
  (`fixtures-20261031T104528Z`). These use made-up values (North/South, 10/12/14, 11/12) and are
  NOT the owner's review files; they demonstrate the pipeline, not the owner's data.

### 12.5 The one action still needed for browser review

The service process must be restarted to load the corrected backend. Same container, image,
mounts, port and work root:
`docker --context rootless restart composer-site-review`
The launcher rewrites its access-token file under the review work root on start (fresh token, mode 600), so the
owner re-opens `http://localhost:2719/?token=<contents of that file>`. Drafts, datasets and the
nine earlier job packages are on the bind mount and survive a restart; nothing is recreated or
deleted. Until this is approved, the owner-facing journey will keep reproducing the mixed-build
symptoms above; the static packages under `rendered-disclosure-20261031T105230Z/work/` and
`fixtures-20261031T104528Z/work/site/work/jobs/*/package/` show the corrected output.

---

## 13. Approved restart and post-restart verification (2026-10-31T11:12Z)

One controlled restart was approved and performed: `docker --context rootless restart
composer-site-review`. Nothing was removed, recreated, re-imaged, re-mounted or re-ported.

Pre-checks (all recorded in `pre-restart-inventory-20261031T111217Z/`): same container id
`0f29d07c6533…`, image `sha256:1ddf322f…`, the three bind mounts with their rw flags, loopback
`127.0.0.1:2719`; no job in `queued`/`running` (all 12 job records `succeeded`); candidate
HEAD `d33d3e1`, 21 unstaged paths, manifest `candidate-manifest-20261031T105526Z`.

Post-checks (`post-restart-inventory-20261031T111310Z/`):
- Same container id and image, `Up`, new start time 11:12:39Z; PID 1 started 11:12:38Z.
- Served app.js sha256 == the candidate file on disk; `/api/csv` now carries
  `disclosure_options` (local-audit permits values/records, restricted-share does neither) and
  8 blocks including `coverage-over-time`; dataset list shows 11, 8, 8 records newest-capture
  first.
- Drafts (8 files), dataset files (10) and all 12 job packages hash **identically** before and
  after the restart: nothing was rewritten or lost.
- Authentication verified without printing the token: 401 without a session, 302 on the token
  entry URL, 200 with the cookie.

Owner token: `<review work root>/access-token.txt` (mode 600, rotated by the launcher at
restart; the absolute path is deliberately not recorded here). Reopen
`http://localhost:2719/?token=` + the file's contents.

### 13.1 The owner's actual review files (verified read-only)

`verify-20261031T111406Z/` reads the captured `original.bin` bytes and reruns the corrected data
layer in a scratch directory (nothing written back):
- 01: 8 records, 2 groups, 4 periods, no missing fields, no repeated keys, overall median
  **127.5** (also the stored analysis).
- 02: suggestion is group/value/no-time; 8 records; 1 missing measure, 1 missing group; labels
  `Station A`, `Station, West`, `Focus "B" & <C>`, `No reading` preserved verbatim; no period
  anywhere; **not confirmed in the store**.
- 03: 11 records, 3 groups; `North/2022` carries both **15 and 18**; 1 repeated key carried by
  2 records; 1 missing measure, 1 missing period; literal `0` stays data; overall median 11.0.

**Known stale state, deliberately not rewritten:** the STORED analysis for 03 was produced by the
old code before this fix. It still reports `repeated_group_period_keys: 2` and holds only one
North/2022 value, because the analysis is computed once at confirmation. It must be recomputed
through the visible flow (open the dataset, keep `location / value / year`, press
"Accept/Update interpretation"). I did not rewrite it: the owner's confirmed state is theirs.

The fixture demos in §12 are synthetic (North/South, 10/12/14/16) and are labelled as such; they
are not verification of the owner's files. The owner's files are verified in 13.1.

---

## 14. Presentation controls P1–P4 and analysis compatibility (2026-10-31T12:4xZ)

Scope: readable statistics, display-only group/period selection, separate axis-label controls,
layouts, and a versioned compatibility gate. Uncommitted; no commit, push, cleanup, restart or
C–E work. The live service still runs the 11:12 build, so the browser will show the previous UI
until a restart is approved (see 14.6).

### 14.1 Candidate and owned paths

HEAD `d33d3e1` on `design/contracts`, 24 unstaged paths, `git diff --check HEAD` = 0.
New: `scripts/health_pipeline/neutral_display.py`, `tests/test_neutral_display.py`.
Changed: `neutral_describe.py` (CALC_VERSION, `analysis_compatible`, period parsing/ids,
duplicate counting), `neutral_library.py` (optional `display`, required sections), `publish.py`
(display field, stale gate in `_render_neutral`), `templates/report_helpers.R` (display helpers,
statistics table, filters, panels, inspector scope), `templates/dashboard.css`,
`templates/methods.qmd`, `src/composer_site.py` (`_csv_analysis_state`, `_csv_draft` with
`excluded`, `set-display`, stale refusal, display_ui payload), `src/composer_web/{app.js,app.css}`,
`tests/test_composer_csv.py`, `tests/js/csv_dom_check.mjs`.

### 14.2 The contract

A neutral recipe entry may carry `display` (optional, so old recipes keep their documented
output). Validated by `neutral_display.validate`, per block:

| block | capabilities |
|---|---|
| values-by-group | groups, statistics, layout (table/chart/chart-and-table), precision |
| values-over-time | groups, periods (all/range/list), axis_labels (auto/every/every_n), layout (table/chart/chart-and-table/panels/combined), precision, height, columns, panel_scale |
| coverage-over-time | groups, periods |

Defaults: groups = all analysed, periods = all, statistics = n/median/middle50/range,
precision = 1 decimal, layout = chart-and-table. Unknown keys, unsupported capabilities, empty
selections, unknown group/period names and out-of-range precision are rejected server-side with
reader-facing messages. Rounding is half-away-from-zero for display consistency; a nonzero value
is never printed as an exact zero.

### 14.3 Analysis compatibility (correctness gate)

`neutral_describe.describe` now writes `method: {calc_version: 2, definitions: …}`.
`analysis_compatible(prepared, analysis)` trusts a matching version, refuses a newer one, and
for analyses without a marker (including the owner's three reconfirmed files) recomputes from
the immutable prepared rows and compares fields. The site checks this in `_csv_analysis_state`
(document, generation) and `csv_bundle_path`; `publish._render_neutral` checks it for the CLI and
replay. A stale result blocks with `csv_analysis_stale` and the message "Update the analysis…";
the explicit update is the owner's normal "Accept/Update interpretation" action. Presentation
changes never bump `calc_version` and never rewrite `neutral-analysis.json`.

### 14.4 What each phase does

- P1: the values-by-group table is now a real statistics table — group (left), n, median,
  middle 50% (Q1–Q3), range (min–max), right-aligned numbers, `scope="row"`/`scope="col"`,
  horizontal scroll container, caption carrying measure/unit and "Summaries use non-missing
  observed values in the analysed selection." Optional columns: missing count, Q1/Q3, min/max,
  mean, sample SD — all read from the saved analysis. The caption says the SD is not an interval
  or significance evidence and that small groups can reveal observations.
- P2: per-block group selection (searchable checklist, select all/clear, "Showing X of Y analysed
  groups"). Display-only: statistics and the saved analysis are unchanged.
- P3: displayed periods (all / window / individual list) and a separate axis-label policy
  (auto / every / every N), with explicit notes ("All observations are plotted; axis labels are
  shown every N periods."). No analytical period filter was added.
- P4: layouts table/chart/chart-and-table/panels/combined, chart height, panel columns and
  shared or independent panel scales (independent is stated and flagged as not comparable).
  Repeated group-period values stay separate; missing periods stay gaps.

Settings live per instance; duplicate instances copy them with a fresh id; excluding a section
moves its entry into the draft's `excluded` list so restoring brings back the title and display
settings; reopening restores everything without writing a new revision.

### 14.5 Evidence (this candidate)

- Focused `run.sh` → 75 passed, 2 skipped (`evidence-20261031T123542Z`), including
  `test_neutral_display.py` and the display/staleness API tests.
- Maintained suite → **866 passed, 4 skipped**; both R smokes 0 (`suite-20261031T123122Z`).
- DOM harness → journey 22/22, conflict gate 17/17, shared editor 0
  (`node-20261031T123053Z`).
- Real renders, disclosure policies + CLI refusals → 35/35 (`rendered-disclosure-20261031T123410Z`).
- Owner fixtures 1–3 through the site path with real renders → 34/34
  (`presentation-20261031T122603Z`): F3 compact table 16.5 / 13.8–19.8 / 10–25, 12 / 6–14 / 0–16,
  8 / 2–8.5 / −4–9; F1 subset shows 1 of 2 groups and 3 of 4 periods while Zurich keeps n=4 and
  median 142.5; F2 has no time controls and keeps the quoted labels; restricted output still
  publishes no values.
- CLI replay → 25/25 (`replay-20261031T122917Z`), including display parity: the same saved
  request reproduces groups, axis-label policy and precision, and the visible text is identical
  after removing the website-only preview banner.

### 14.6 Service state and the one approval needed

`composer-site-review` is still the 11:12 process: `/api/csv` has no `display_ui` or
`analysis_stale`, while the static `app.js` on disk now drives those controls. The page is a
mixed build again. For browser review the service needs the same controlled restart already used
once: `docker --context rootless restart composer-site-review` (same container, image, mounts,
port; launcher rotates the token). Until then, use the static packages in
`presentation-20261031T122603Z/work/site/work/jobs/*/package/`.

### 14.7 Deliberately not done

Report-global analytical filters, new grouping/aggregation, multiple measures, reference-period
comparison, latest-per-group monitoring, Top N, sensitivity blocks, disease semantics, inference,
maps, profiles, dataset replacement, C–E. Display filtering is not anonymisation and does not
change export permissions.

---

## 15. Approved restart, compatibility defect found and fixed (2026-10-31T12:5xZ)

One approved restart was performed at 12:53Z (same container `0f29d07c6533…`, image
`sha256:1ddf322f…`, three mounts, `127.0.0.1:2719`; PID 1 started 12:53:18Z). Pre-restart
inventory `pre-restart-inventory-20261031T125253Z` (9 draft files, 15 dataset files, 15 job
packages) is byte-identical to `post-restart-inventory-20261031T125355Z`; the served app.js hash
equalled the file on disk; unauthenticated 401 → token exchange 302 → 200.

### 15.1 The post-restart check found a real defect (now fixed)

The restarted build reported every saved analysis as stale:
"…no longer matches the confirmed data and current definitions (interpretation)". Cause:
`analysis_compatible` recomputed with `prepared["interpretation"]`, which omits the display
labels (measure_label/unit/meaning), then compared the `interpretation` field against the saved
one, which has them. It also trusted a matching `calc_version` without any other check.

Fixed `neutral_describe.analysis_compatible` is now a conjunction, never a version check:
  1. identity — analysis and prepared rows name the same captured digest;
  2. confirmed-settings identity — prepared rows, saved analysis and interpretation.json agree on
     category/measure/time/missing_tokens;
  3. result integrity — the declared method is re-run over the saved rows and every analytical
     field must match (`row_count, groups, group_count, summary, missing, quality, time, measure,
     groups_sorted`).
`calc_version` is only used to refuse a NEWER calculation. Analyses without the marker (the
owner's three) go through the same recomputation, so no migration is needed.

Verified read-only against the live store: `compat-20261031T125555Z` — 15/15, including
"tampered v2 result is rejected", "wrong capture is rejected", "different confirmed settings are
rejected", "newer calculation is rejected" for all three datasets.

### 15.2 Resolved defaults are now frozen into new requests

`csv_submit` resolves each capable block's display settings and writes them into the freeze
that becomes the job's composition.json. A later change to the code defaults can no longer
silently reinterpret a saved report. Historical packages are untouched; old recipes still render
(old snapshots keep no display key and resolve at render time, as documented).

`neutral_display.defaults` was also corrected to emit only keys each block supports (it had been
returning `statistics` for values-over-time and `axis_labels`/`precision` for coverage, which the
new freeze surfaced as a validation error in the first presentation run — preserved as a failed
attempt at `presentation-20261031T130434Z`).

### 15.3 Evidence at this state

- Focused: 77 passed, 2 skipped (`evidence-20261031T1…`, newest).
- Maintained suite: **868 passed, 4 skipped**; both R smokes 0 (`suite-20261031T130921Z`).
- Owner fixtures, real renders: 34/34 (`presentation-20261031T130725Z`).
- CLI replay incl. display parity: 25/25 (`replay-20261031T130847Z`).
- Compatibility: 15/15 (`compat-20261031T125555Z`).

### 15.4 Service state

The process started at 12:53Z does not contain 15.1/15.2 (both are Python changes made after the
restart). It therefore still reports the saved analyses as stale and must not be used for review.
A second controlled restart of the same container is required and has not been performed.

---

## 16. Compatibility-cache boundary, axis-label wording, restart (2026-10-31T13:5xZ)

### 16.1 Cache key and invalidation (was mtime, now content)

The compatibility verdict is cached per dataset digest under a CONTENT key:

    sha256( "calc=<CALC_VERSION>" ||
            for name in sorted(dataset.json, interpretation.json, prepared.json,
                               neutral-analysis.json):
                name || 0x00 || sha256(file bytes) )

So the key covers the captured dataset record, the confirmed interpretation, the prepared rows,
the saved analysis and the calculation version. It is invalidated by any byte change in any of
those four files, by a CALC_VERSION change, and by process restart — and by nothing else. File
mtimes are no longer read at all: rewriting a file and restoring its timestamp produces a
different key and forces a fresh verification. Cost is one pass of hashing over those files per
request, bounded by the existing 20 MiB / 100k-row capture limits; the expensive re-derivation is
still avoided when the content key matches.

Verified in an isolated fixture (`cache-20261031T135140Z`, 8/8): compatible verdict cached →
analysis rewritten with the same byte length → original mtime restored → the document reports the
analysis stale, generation refuses with `csv_analysis_stale`, the CLI path
(`publish._render_neutral`) refuses with "no longer matches", and no report is produced. A
display-only edit made before the tamper left the analysis compatible. A pytest regression test
(`test_compatibility_cache_is_content_keyed_not_mtime`) covers the same boundary.

### 16.2 Axis-label wording

The note no longer claims the whole analysis is plotted. It now reads:
"All eligible observations in this displayed selection are plotted; every displayed period is
labelled on the axis." and, for thinning, "…axis labels are shown every N displayed periods."
Hidden groups/periods are excluded from the chart and the note says so; the checks in
`render_presentation.py` and `replay_check.py` assert the new wording and that the old
"All observations are plotted" phrase is absent.

### 16.3 Restart and post-checks

Restart at 13:58Z: same container `0f29d07c6533…`, image `sha256:1ddf322f…`, three mounts,
`127.0.0.1:2719`, PID 1 restarted 13:58:42Z. Pre-restart inventory
`pre-restart-inventory-20261031T135816Z` (9 draft files, 15 dataset files, 15 job packages)
hashes identically to `post-restart-inventory-20261031T135904Z`.

Served checks: 401 unauthenticated → 302 token exchange → 200 page; served `app.js` hash equals
the file on disk; all three owner datasets open with `analysis_stale: null`, `display_ui`
present, correct record counts (11/8/8), groups (3/2/5) and periods (4/4/0); disclosure
policy `local-audit` on all three; one job record and its 972 KB report still serve.
Health presets unchanged. No dataset, draft or job was created or modified during these checks.

### 16.4 Evidence at this state

- Focused: 78 passed, 2 skipped (`evidence-20261031T1…`, newest).
- Maintained suite: 869 passed, 4 skipped; R smokes 0 (`suite-20261031T135600Z`).
- Owner fixtures, real renders: 34/34 (`presentation-20261031T135355Z`).
- CLI replay incl. display parity and axis wording: 25/25 (`replay-20261031T135524Z`).
- Cache boundary: 8/8 (`cache-20261031T135140Z`).
- Candidate manifest: `candidate-manifest-20261031T135816Z`.

---

## 17. Report-bound “Data & sources” panel (2026-10-31T15:xxZ)

Bounded feature: for an already generated report, the steward can answer which dataset and
settings produced it, where the data came from, what may be downloaded, how it was calculated and
what reproduction requires. Nothing is recomputed and no historical package is touched.

### 17.1 Shape

- `GET /api/jobs/<job_id>/sources` → a report-bound document assembled from `job.json`, the
  package's `provenance.json`, its frozen `composition.json` (or the reproduction copy, or for
  health the provenance's own composition record) and the package `data/` files. It never reads
  the editor, the current interpretation, a live analysis or the working branch.
- `GET /api/jobs/<job_id>/retained/<name>` → steward-only download of `original.bin`,
  `prepared.json` or `neutral-analysis.json`, allowed only when the report's recorded policy is
  `local-audit`; the original is served only when its SHA-256 still matches the digest recorded in
  the report (otherwise 409, and the panel shows “Integrity check failed” without a link).
- Panel links to package artifacts use the existing `/reports/<job>/<file>` route, which already
  enforces containment, regular-file and symlink rules. Every offered artifact is one the package
  actually contains; nothing is generated on demand.
- UI: “Data & sources” button in the saved-report actions and in the CSV report area. The panel is
  a read-only dialog section (`role=dialog`, labelled, Close button, Escape closes, focus moves to
  the panel and returns to the opener). It carries the note “This information describes this saved
  report. The current editable draft may differ.”
- Sections: Data (identity, roles, measure, filters, counts, coverage, per-section display scope),
  Source & attribution (recorded publisher/URL/dates/licence for health; explicit “not recorded”
  for uploads), Methods & reproduction (methods, provenance, frozen request, method version, code
  reference, helper digests, replay state and command), package files, retained steward-only files,
  notices.
- Per-section display scope is listed section by section; no report-wide “displayed count” is
  invented. Health reports degrade to a recorded display scope rather than fabricated roles or
  measure labels.
- Fallbacks: missing package, unreadable provenance, missing frozen request, missing retained
  capture, unsupported/corrupt metadata and withheld material each produce their own state and
  explanation, never a blank panel.

### 17.2 Evidence

- Focused: 86 passed, 2 skipped (`evidence-20261031T1…`, newest); site regression 108 passed.
- Maintained suite: 877 passed, 4 skipped; R smokes 0 (`suite-20261031T150725Z`).
- DOM harness: journey 30/30 (includes panel open/close, three sections, report-relative links,
  `javascript:` never becoming a link, hostile label kept as text, per-section scope), conflict
  gate 17/17, shared editor 0 (`node-20261031T145547Z`).
- Owner fixtures, real renders: 34/34 (`presentation-20261031T151028Z`).
- CLI replay: 25/25 (`replay-20261031T151155Z`).
- Three example views: `sources-examples-20261031T150033Z/SUMMARY.md` plus the JSON documents for
  one local-audit report, one restricted report and one historical/health report.
- Preservation: `csv-datasets` files are byte-identical to the 13:58 inventory. Drafts and jobs
  changed during the window because the owner was using the app (a 14:23 generation and a 15:23
  draft edit); no write came from this work — every probe ran in an isolated `/evidence` work root.

### 17.3 Service state

The running process (started 13:58Z) predates this feature: `/api/jobs/<id>/sources` returns 404
while the static assets already contain the button. A restart is required before review; it has
not been performed.

---

## 18. Data & sources: historical binding and permission boundaries (2026-10-31T15:5xZ)

Status: P1–P4 are owner-accepted for the exercised functional and visual behaviour (including
narrow screens), with accessibility, cross-browser and large-group coverage still untested. Only
Data & sources is review pending. This section records two boundary corrections and the restart.

### 18.1 Retained material is bound to the report's recorded identities

Before: prepared.json and neutral-analysis.json were offered whenever the policy was local-audit
and the files existed in the capture directory. They change in place on reconfirmation, so an
older report could show a newer revision as its own inputs.

Now each retained file is bound to what THIS report recorded:
- `neutral-analysis.json` is offered only when its canonical digest equals the `analysis_digest`
  in the report's provenance blocks.
- `prepared.json` is offered only when re-deriving the descriptor from its rows — with the
  report's recorded source identity — reproduces that same digest.
- The download route repeats the same verification server-side and answers 409 otherwise.
- Anything present but different appears under "Current workspace material — differs from this
  report", without a download link.
Test: `test_a_newer_analysis_revision_is_never_presented_as_historical` (generate, reconfirm a
different interpretation, reopen the old report: recorded identity unchanged, no historical
items, both files listed as current, both downloads 409).

### 18.2 Local audit is not blanket raw-record permission

The saved contract distinguishes `permit_values` (numerical findings) from `permit_records`
(contributing records). It records no permission for the raw captured file. Now:
- `neutral-analysis.json` requires `permit_values`.
- `prepared.json` requires `permit_records`.
- `original.bin` is **not offered or downloadable at all**; the panel explains that the contract
  records permission for findings and records, not for the file, which can also contain columns
  the report never analysed.
- Package links are filtered by the same flags and, before anything is offered, the package is
  re-hashed against `package_sha256` recorded at generation; a mismatch withholds every link and
  adds a notice.
Tests: `test_retained_material_is_bound_to_the_report_and_permissions`,
`test_local_audit_without_record_permission_withholds_rows`,
`test_package_links_follow_policy_and_package_digest`. On a real owner report (local-audit with
`permit_records: false`) the panel correctly offers the analysis and withholds both the prepared
rows and the capture.

### 18.3 Restart and post-checks

Restart at 15:54Z: same container `0f29d07c6533…`, image `sha256:1ddf322f…`, three mounts,
`127.0.0.1:2719`, PID 1 at 15:54:14Z. Pre-restart inventory
`pre-restart-inventory-20261031T155344Z` (9 draft files, 15 dataset files, 16 job packages)
hashes identically to `post-restart-inventory-20261031T155445Z`. Served `app.js` equals the file on
disk; 401 → 302 → 200.
Served endpoint checks, read-only:
- actual neutral report `20261031T142337Z-de7c653590`: status succeeded, provenance recorded,
  dataset 03 digest `2e918f…`, policy local-audit, attribution not recorded, analysis offered,
  prepared and capture withheld by the recorded flags, replay `complete_local`.
- actual health report `20261030T071559Z-a6f20056c0`: profile researcher, provenance recorded,
  publisher recorded (FOPH/BAG IDD), snapshot `d0709…`, revision `2938b89…`, replay
  `requires_private_inputs`, no retained neutral material.
The fabricated health fixture remains test coverage only; it is not presented as evidence of any
actual historical report.

### 18.4 Evidence

Focused 89 passed / 2 skipped · suite 880 passed / 4 skipped, R smokes 0
(`suite-20261031T155018Z`) · DOM journey 31/31, conflict 17/17
(`node-20261031T154659Z`) · examples `sources-examples-20261031T154945Z`.

---

## 19. Saved-report history and verified reuse for Your CSV (2026-10-31T17:xxZ)

Bounded feature: open a retained CSV report without rendering, generate with verified reuse,
copy a report's settings into the draft. Data & sources stays attached per report.

### 19.1 Reuse assessment (stakeholder → neutral)

| stakeholder primitive | decision |
|---|---|
| `reuse_components` / `reuse_key` (canonical hash) | **adapt** — same idea, neutral-specific fields |
| `environment_identity` (content hashes + toolchain) | **adapt** — separate neutral file list, cached per process |
| `_reuse_eligible` (key + snapshot + package digest) | **adapt** — plus provenance/dataset/analysis/disclosure checks |
| `confirm_reuse` (validate, then return the existing record) | **adapt** — reuse returns the existing job, no new job |
| saved-report list (`saved()`, `snapshot_summary`, reuse view) | **reuse the pattern**, dataset-scoped and bounded |
| health bundle/manifest identity, audience ids, science | **defer** — not used; health still uses its own path |

No cache system was refactored; the neutral path adds one small identity module.

### 19.2 Effective-request identity (`neutral_identity.py`, schema …/neutral-request-identity/1)

Canonical JSON over: mode + format; source digest, filename and confirmed roles; analysis digest,
calc_version and schema; the ordered composition with **resolved** display settings and titles for
present instances only; disclosure policy with both permissions; renderer identity (content
hashes of the 10 neutral template/helper/module files, software versions, workflow config).
Excluded on purpose: job id, timestamps, output paths, and the runner's own metadata.

Reuse lookup: jobs with mode csv, same dataset digest, status succeeded, identical key; then
validated — frozen request digest, normalised composition equality, package digest and file count,
report.html presence, provenance readability, dataset digest, recorded analysis digest, recorded
disclosure flags. Newest compatible candidate wins on a stable (created_utc, job_id) order.
A hit returns the **existing** job (HTTP 200 with `reused: true` and the original timestamps);
nothing is written and no render is invoked.

### 19.3 History (`GET /api/csv?digest=…` → `history`)

Dataset-scoped by content digest (same filename ≠ same history), newest first, bounded to 20 with
`total`/`truncated`. Each entry carries time, dataset name/digest, recorded titles and blocks,
policy with both permissions, preview flag, reuse state (match / different / unknown /
unavailable with a reason) and the report link. Older reports without a recorded key are marked
"reuse identity was not recorded" and stay openable. No absolute paths appear in the payload.

### 19.4 Open and edit-a-copy

Open is a plain `/reports/<id>/report.html` link: no render, no job, no draft write (tested with a
counting renderer). Edit a copy (`POST /api/csv/edit` action `restore-composition`) loads the
report's frozen composition, refuses a different confirmed interpretation (`context_changed`) or
an edited draft (`draft_has_edits`) unless explicitly confirmed, and never touches the report.

### 19.5 Evidence

Focused 103 passed / 2 skipped · suite 894 passed / 4 skipped, R smokes 0
(`suite-20261031T172334Z`) · DOM journey 37/37, conflict 17/17
(`node-20261031T171819Z`) · owner-fixture renders 34/34
(`presentation-20261031T172208Z`).
Tests cover dataset scoping, equal filenames/different digests, reopen persistence, health
separation, no-render opening, reuse with a render counter, settings/analysis/environment/policy/
permission misses, restore-to-original reuses the first package, corrupt package skipped and kept,
simultaneous duplicates (one render, one 409), draft protection, reinterpretation confirmation,
and stale analysis still blocking.

### 19.6 Limitations recorded

- Reuse is not recorded as an event: a hit performs no writes at all (no event log), so history
  shows the original report once.
- Reports generated before this change have no recorded reuse key; they are openable but marked
  "unknown" rather than deriving an identity after the fact.
- Neutral drafts are per dataset, not named: "Edit a copy" therefore replaces the draft only after
  an explicit confirmation when the draft has edits.
- No cross-dataset deduplication and no equivalence of independently created instance ids.

---

## 20. Visual cleanup pass — shared shell, compact sections, saved reports (2026-10-31T19:xxZ)

Presentation-only pass across both modes. No analysis, disclosure, reuse or provenance logic was
changed; report packages are untouched.

### 20.1 What changed

- Shell: one-line purpose, a single visible "Preview only" statement, clearer tabs. Removed the
  long header paragraph that repeated the disclaimer.
- Health "Data used" card above audience selection: publisher, source, geography, API/retrieval
  wording, the publisher's Wednesday schedule (explicitly separated from local freshness), the two
  source links, and the selected bundle's recorded facts. Snapshot id, analysed period, geography
  and topic count come from the saved bundle; capture and publisher-release dates are **not
  recorded for these bundles** and say so.
- CSV: a compact dataset passport (name, records/groups/periods, interpretation state, Change
  dataset / Review interpretation); upload and preview folded into a details that auto-opens only
  while the dataset is unconfirmed; interpretation form folded and auto-opened while unconfirmed;
  disclosure resting summary (policy + both permissions + consequence) with a Change disclosure
  toggle that opens the native radios; conflicts force the panel open and stay visible.
- Sections (both modes): each row is now a compact card — label, Required/Excluded state badge,
  custom title, factual summary — with reorder/include/duplicate controls in the header and all
  settings behind "Settings and details". Internal instance ids moved into that details.
- Saved reports (both modes): compact rows (title, human time, mode, preview, policy), expandable
  "Show details" with dataset/profile, permissions, reuse state, recipe id and the actions
  (Show here / Open separately / Data & sources / Edit a copy where they exist). One bounded
  scroll area (22rem, 70vh on narrow screens); scope filter "This mode / All reports" on the
  health list; CSV history stays dataset-scoped.
- Status/empty state: preview empty line now distinguishes "No report is currently displayed.
  Previously generated reports are available below." from "No reports generated yet"; CSV gains a
  "Show here" that displays a retained report without rendering; replay command moved under
  "Reproduction details".
- Data & sources: sections became labelled expandable groups (Data, Files, Retained, Source,
  Methods); binding, integrity and disclosure behaviour unchanged.

### 20.2 Explicitly not done in this pass

- No Load more/pagination: the newest-20 history limit and its limitation stand.
- Health history rows do not have "Edit a copy" (the health mode has no equivalent action); CSV
  rows do. No action was invented to make the two look identical.
- The source card cannot show capture/release dates because the site's saved bundles do not record
  them; each report's Data & sources records the exact retrieval dates instead.
- Status unification is partial: the existing job/ready/status elements were kept (so tests and
  behaviour stay stable) and restyled rather than merged into a single element.

### 20.3 Evidence

Focused 103 passed / 2 skipped (`evidence-20261031T185444Z`) · site regression 108 · maintained
suite 894 passed / 4 skipped, R smokes 0 (`suite-20261031T185800Z`) · DOM journey 44/44, conflict
17/17, shared editor 0 (`node-20261031T185408Z`) · owner-fixture real renders 34/34
(`presentation-20261031T190134Z`).
Preservation: drafts, dataset files and all 17 job packages hash identically before/after this
pass (`preservation-20261031T190304Z`). No report bytes changed.

One test was retargeted, not weakened: the chained-append negative control now points at the same
three lines inside the section card body (the code moved), and still proves the harness fails on
the defect.

---

## 21. Visual pass: narrow checks, interaction state, restart (2026-10-31T19:2xZ)

### 21.1 The 25→26 changed-path difference

The additional path is `tests/test_composer_custom_ui.py` (modified, test-only): the chained-append
negative control was retargeted to the same three lines now living inside the section card body.
No product code, schema or data change. Candidate manifest `candidate-manifest-20261031T192303Z`
(26 paths, diff --check 0).

### 21.2 Interaction behaviour (structural checks, not browser acceptance)

- Section cards remember their open state per list element (UI-only `Set`, never in the recipe or
  draft), so editing a setting inside an expanded section keeps it open.
- Focus is restored by control id after the composer re-render; the DOM harness now resolves
  runtime ids like a browser (minidom `getElementById` walks the tree), focuses the section title
  field, edits it and asserts both the open state and the active element.
- Expansion itself issues no request and writes nothing: the harness records requests and the
  check fails on any stray call; reuse identity is computed from the recipe/analysis, which
  expansion never touches.
- Data & sources groups: Data open, Source & attribution / Methods collapsed; the retained group
  opens only when it carries a withheld or integrity-failed state. Notices (package integrity,
  missing provenance) stay outside the groups and always visible.
- Real-browser focus/scroll behaviour is still unverified; the checks above are structural.

### 21.3 Restart and post-checks

Restart at 19:23Z: same container `0f29d07c6533…`, image `sha256:1ddf322f…`, three mounts,
`127.0.0.1:2719`, PID 1 at 19:23:38Z. Pre-restart inventory
`pre-restart-inventory-20261031T192304Z` hashes identically to
`post-restart-inventory-20261031T192412Z` (9 draft files, 15 dataset files, 17 packages).
Served `app.js` equals the file on disk; 401 → 302 → 200; health presets 200; CSV document 200
with dataset-scoped history (4 reports, limit 20, not truncated). No report was generated and no
draft was touched during the checks.

### 21.4 Standing limitations

No pagination beyond the newest 20 reports; status unification is partial; the health source card
cannot show capture/release dates where the bundle does not record them (each report's Data &
sources records the retrieval dates); no new broad accessibility or cross-browser acceptance.

---

## 22. Two CSV layout corrections after visual review (2026-10-31T19:5xZ)

Owner accepted the visual pass (scoped to the exercised desktop/narrow/keyboard behaviour) subject
to these two corrections. Both are static-asset changes only: no Python, schema, analysis,
disclosure or reuse identity changed, and **no restart was needed** — the served app.js / app.css /
index.html already hash-identically to the worktree (verified after the change).

1. Uploaded datasets: `#csv-datasets` now renders a bounded (`9.5rem`) vertical scroll container;
   the selected dataset is marked `is-selected` + `aria-selected`; filenames sit in a truncated
   span whose `title` keeps the full value; a "Show all N datasets" / "Collapse list" toggle
   (UI-state only, no request) expands it. Selecting still goes through `selectDataset`.
2. CSV section rows: one compact grid row — [↑][↓] · name · optional title/scope · Required badge ·
   "Settings" button with `aria-expanded`/`aria-controls`; Remove/Duplicate moved inside the
   details body under the section actions. The details keep the open-state memory and focus
   restoration from §21; the visible summary is now a visually-hidden element with a real name.

Verification: DOM journey 57/57 (`node-20261031T195237Z`), conflict gate 18/18, shared editor 0;
focused 103 passed / 2 skipped (`evidence-20261031T195319Z`); suite 894 passed / 4 skipped, R
smokes 0 (`suite-20261031T195641Z`). Datasets and all 17 packages hash unchanged; drafts changed
only through owner activity in the browser (19:42/19:46 UTC), not by this work.

---

## 23. Work package closed — accepted, committed (2026-10-31T20:3xZ)

### 23.1 Accepted scope

The owner visually accepted, on the exercised desktop and narrow layouts: the P1–P4 presentation
controls, Data & sources, saved-report history and verified reuse, the shared visual pass (shell,
health source card, compact section cards, compact saved reports, Data & sources grouping) and the
two CSV layout corrections (bounded dataset selector with a compact expansion control, single-line
section rows) and the final dataset/structural-preview adjustment.

This is **scoped functional and visual acceptance of the exercised journeys**. It is not
accessibility, cross-browser, large-group, scientific or publication acceptance, and it says
nothing about reports the owner has not seen.

### 23.2 Committed candidate

- Branch `design/contracts`, parent commit `d33d3e10bd5de9a6e2aff982c344bdbb80cc61e6`.
- 26 changed paths (15 modified, 11 new), byte-identical to
  `candidate-manifest-20261031T202637Z` at commit time; `git diff --check HEAD` clean.
- Acceptance covers the whole package, not only the last visual adjustment: neutral CSV capture and
  interpretation, neutral rendering and disclosure model, presentation controls P1–P4, Data &
  sources, saved-report history and verified reuse, and the visual/UI pass.
- Unrelated work and user data were not staged. Nothing was pushed and no history was rewritten.

### 23.3 Authoritative checks at commit time

Focused 103 passed / 2 skipped (`evidence-20261031T201934Z`); site regression 108; maintained suite
894 passed / 4 skipped with both R smokes clean (`suite-20261031T202257Z`); DOM journey 62/62,
conflict gate 18/18, shared editor harness green (`node-20261031T201852Z`); owner-fixture real
renders 34/34 (`presentation-20261031T190134Z`). Runtime: pinned image
`sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8`, R 4.3.2, the image's
`/opt/health-report-venv` Python.

### 23.4 Known limitations (carried, unchanged)

- Structural preview is bounded to the first 100 rows and 20 columns; there is **no paging**, so
  whole-table inspection is not available for larger captures. The UI says so.
- Long preview cells are truncated with a `title` tooltip; there is no copy/open-cell affordance.
- History is capped at the newest 20 reports; no Load more/pagination.
- Status unification is partial; the health source card cannot show capture/release dates where
  the saved bundle does not record them ("Not recorded"; never inferred from a report).
- No broad accessibility, cross-browser or large-group acceptance; DOM checks are structural only.
- Reuse is not recorded as an access event; pre-change reports carry no reuse identity.
- One editable draft per dataset: "Edit a copy" replaces it after explicit confirmation.

### 23.5 Reproduction and review

Focused `bash ~/.state/composer-bootstrap/csv-b-check/run.sh`; suite
`run_suite.sh`; DOM `run_node.sh`; real neutral renders `render_presentation.py` and the disclosure
script; replay `replay_check.py`. Evidence directories remain under
`~/.state/composer-bootstrap/csv-b-check/` and were not pruned. Review access: the running
`composer-site-review` container on loopback 2719 with its launcher-written token file under the
review work root (path not recorded here).

### 23.6 First safe next action

Resume at a separate, scoped task. Candidate follow-ups, in order of user value: preview paging
(bounded range reads from the retained capture, never re-analysis) and history pagination beyond
the newest 20. Neither is started or promised here.
