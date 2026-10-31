# Neutral CSV integration — scoped plan and baseline record (Slice A)

Status (historical, 31 October 2026): Slices A and B are complete; the neutral CSV composer was
accepted and committed as `6ccc58177ccda018a3ff39efe9106ed965da5c65`. Slices C–E remain not
started. Current status: [HANDOFF.md](HANDOFF.md) §9.

Written by the implementation lead, 2026-10-31, branch `design/contracts`, HEAD
`d33d3e10bd5de9a6e2aff982c344bdbb80cc61e6`, single worktree, working tree CLEAN at the time of
writing (git status empty). Baseline checks: the preserved evidence already records the current
tree's maintained suite 791 passed / 2 skipped (pre-commit and local-recovery runs) and Node-gated
DOM harness 3+1 passed at this commit; nothing was rerun for this record.

Governing brief: "Neutral CSV integration — consolidated implementation prompt"
(prepared 2026-10-30). Decisions in its §3 register are binding defaults. Governance: changes stay
UNSTAGED and UNCOMMITTED by default; remote publication remains pending (no host credential);
no reset/stash/force-push; no PR merge, promotion, release, deployment, token rotation or service
restart without separate permission. The existing review service (e6c0233ca79e, 127.0.0.1:2719)
is untouched and serves the old sources from the installed bundle; newly written code will be
exercised through tests and pinned-image renders, not by replacing the live service.

## Current architecture (verified by reading source, d33d3e1)

- Site `src/composer_site.py` (1887 lines): four health audiences under `inputs/<audience>/data`,
  JSON-only POST bodies (`_body()` rejects non-JSON), single render slot, immutable per-job
  composition snapshots, `replay_command` via `composer_workspace.replay_command` →
  `publish.py html --bundle <audience>/data --composition <snapshot>`.
- Workspace `scripts/health_pipeline/composer_workspace.py`: shared recipe validator entry
  `publish.validate_composition` (single validator, `KNOWN_BLOCKS` list in publish.py),
  `render_preview`/`preview`, drafts (audience schema 2, custom schema 3 with
  `origin=composer-library`), `replay_command`.
- Renderer: `publish.render` packages the bundle, builds per-block provenance records
  (`build_block`/`build_series_*`/`build_coverage_*`/`build_monitoring_*`/
  `build_sensitivity_*`), writes provenance.json, renders `report.qmd`+`methods.qmd` via the
  pinned Quarto, then `publish_evidence` (bundle `data/` → package `data/`) and
  `validate_published_evidence`.
- `report_shared.qmd` is the shared entry; `report_helpers.R` has `composition_registry` mapping
  block types → render closures; `compose_report_html` drives sections/navigation/section
  titles from the recipe; `read_bundle` requires `stakeholder.json` (health-only).
- Block labels live in `config/composer/block-labels.json` (single source, read by Python and R).
- Tabular foundations exist and are tested but NOT wired to the workflow: `tabular_input`
  (inspect + normalize_periods), `tabular_prepare`, `tabular_bundle`, `tabular_describe`
  (SCHEMA health-report/descriptive-analysis/1, inclusive quartiles, sample SD), `tabular_run`,
  `tabular_render`, `tabular_report.R` path in report_shared.qmd (`input_kind='tabular'`),
  1001 lines of tabular tests. The prompt's claim that a generic renderer "hard-codes
  researcher/health-institution/public outputs" is accurate only for the tabular route; the
  composed route is block-driven.

## Ownership (exact paths for this slice)

| Path | Owner | Allowed change |
|---|---|---|
| scripts/health_pipeline/neutral_describe.py | NEW: neutral capture/interpretation/prepare/describe | create |
| scripts/health_pipeline/neutral_library.py | NEW: neutral block vocabulary/qualifications | create |
| scripts/health_pipeline/composer_workspace.py | add neutral dataset store + capture limits | bounded add |
| scripts/health_pipeline/publish.py | `KNOWN_BLOCKS` + neutral provenance hook | bounded add |
| scripts/health_pipeline/templates/report_helpers.R | neutral block renderers + neutral compose | bounded add |
| scripts/health_pipeline/templates/report_shared.qmd | neutral input_kind branch | bounded add |
| src/composer_site.py | CSV mode routes/uploads/drafts | bounded add |
| src/composer_web/{index.html,app.js,app.css} | mode switch + CSV journey | bounded add |
| scripts/health_pipeline/config/composer/block-labels.json | neutral block names | additive |
| tests/test_neutral_*.py, tests/r_csv_smoke.R | new tests | create |
| docs/build/composer/ROUND-CSV-*.md | slice status records | update later, not in this pass |

NOT owned / untouched by this slice: `tabular_input/prepare/bundle/describe/run/render` semantics,
the health bundle contract, maintained recipes, `composition-recipe/2` schema, review service,
preservation evidence. No health schema renames. `composition-recipe/2` is reused for neutral
recipes (audience = neutral profile id `neutral-overview` for Slice B).

## Slice B scope (this pass, per brief §16)

1. Bounded multipart capture (no JSON-only assumption for the upload endpoint), immutable
   dataset store keyed by content digest, resource-limit config (20 MiB / 100k rows / 100 cols /
   5M cells / 64 KiB cell / preview 100×20).
2. Compact interpretation confirmation: proposed roles (category, optional time, measure+unit)
   with explicit unresolved ambiguity; confirmation writes immutable interpretation.json;
   suggested-only values are visible draft state, never verified output.
3. Neutral prepared-rows + descriptive analysis descriptor (no pooling by default; explicit
   declared methods; inclusive quartiles/sample SD reused; no invented inference).
4. Neutral block vocabulary and ability gating: `data-overview` (primary), `values-by-group`,
   `values-over-time` (only when time eligible), `data-quality`, plus reused `intro`,
   `limitations`, `reproduction`; labels added to block-labels.json.
5. Neutral default recipe (`neutral-overview`): intro, data-overview, values-by-group (or
   values-over-time when eligible), data-quality, limitations, reproduction.
6. Site CSV mode: upload→confirm→compose, dataset passport, saved CSV draft per dataset,
   generation through the existing single-slot job machinery, CLI replay command recorded.
7. Renders: real composed HTML for a snapshot CSV and a time-series CSV through the pinned
   image; semantic checks (section ids, values, no health vocabulary in generated copy).
8. Tests: neutral describe unit tests; site CSV flow over real HTTP loopback with stub render;
   CLI replay ejection; R smoke render. All unstaged/uncommitted.

Slices C–E (explicit ungrouped/count modes, multiple measures/group candidates, filter
predicates, missing tokens beyond blank, Detailed/Brief profiles, new-dataset versions,
replacements, batch publication) are REQUIRED target scope of the brief but are not started
here; the mandatory human browser review gate must be released before their dependent work.

## Slice B execution status (2026-10-31, worktree still uncommitted)

Implemented and verified (evidence root ~/.state/composer-bootstrap/csv-b-check/):

- Data layer: `neutral_describe.py` (bounded capture, compact interpretation, prepared rows,
  explicit descriptor, repeatable verification) — 13 focused tests green.
- Vocabulary: `neutral_library.py`; shared label file registers the four neutral blocks;
  `composer_library` registers them non-composable so the health editor never offers them.
  A health R smoke assertion was updated (deliberately) to the new exact label set.
- Renderer: neutral branch in `report_shared.qmd`/`methods.qmd` (doc titles parameterized:
  health default untouched), `report_helpers.R` neutral registry + renderers, `publish.py`
  `_render_neutral`, `neutral_publish.py` provenance builders.
- Site: `/api/csv` (document), `/api/csv/upload` (bounded multipart), `/api/csv/confirm`,
  `/api/csv/generate`; immutable dataset store under work-root csv-datasets/<digest>/;
  `composer_workspace.render_preview` is neutral-aware.
- Checks: `test_neutral_describe.py` (13) + `test_composer_csv.py` (10) all green; site and
  workspace regression files green (108 + 46); full maintained suite **814 passed, 2 skipped**
  (the two skips remain the Node-gated harness, covered by the pre-commit Node run);
  `r_composition_smoke.R` and `r_composer_preview_smoke.R` green.
- Real render: one neutral time-series dataset rendered through `publish.render` with the
  pinned image → HTML package with sections csv-data-overview / csv-values-over-time /
  csv-data-quality / limitations / reproduction / intro; provenance sidecar with
  data-overview + values-over-time blocks, audience neutral-overview; report and methods
  titles are "Supplied dataset | …"; no disease vocabulary in generated copy (17/17 checks).
  Package retained at `~/.state/composer-bootstrap/csv-b-check/rendered/rendered/work/out/`.

Not yet done (still required by the brief's Slice B, blocked on session scope, NOT skipped as
optional): the frontend "Health reports / Your CSV" switcher and the CSV journey screen
(app.js/index.html modes) — the API and render paths are complete and exercised over HTTP in
tests, but the browser-facing journey still needs the UI work and its human visual review.
Slice C–E dependent work and the mandatory human browser review gate remain ahead.

## Slice B frontend completion (2026-10-31, second pass)

The frontend journey is now implemented: top-level "Health reports / Your CSV" route tabs in
index.html; app.js gains `switchRoute`, dataset capture list + upload (bounded multipart),
structural preview, confirmation card (role selects, measure label/unit/meaning, declared
missing tokens), dataset passport summary, section composer with the neutral vocabulary
(include/exclude, reorder, duplicate, per-section title) backed by a per-dataset draft store
(`/api/csv/edit` → `csv_draft_edit`/`csv_recipe_for`), generation through the shared single-slot
job loop with safe failure status, and CLI replay disclosure. Health panels and controls are
unchanged; the health composer never sees neutral blocks (composer_library registers them
non-composable, library.inventory() never offers them, and the neutral recipe validator refuses
health blocks — verified by `test_csv_capability_separation`).

Evidence-discrepancy correction: the earlier checklist line "Data quality: 1 missing period
value" was a mistranscription. The saved analysis for the 4-row time-series fixture records
`missing: {measure: 0, group: 0, periods: 0}` and `repeated_group_period_keys: 0` (all years
present, no repeats). The report/checklist now state the recorded values.

Disclosure hardening: the neutral package now withholds row-level observations by default —
values-over-time renders "not disclosed" placeholders (cell availability from the saved
analysis; the value withheld unless an explicit disclosure choice exists), the values-by-group
inspection table is removed, and the shareable provenance record no longer carries the absolute
recipe path. Summary statistics remain (they are the requested descriptive stats); the local
audit/replay vs shareable-output distinction is recorded in the package and the methods copy,
and the disclosure scan script now passes with only expected findings.

Checks on this state (final, all re-run on the merged tree, exits in each evidence dir under
~/.state/composer-bootstrap/csv-b-check/):
- focused suite (neutral-describe + test_composer_csv incl. journey/edit/capability): 28+ passed,
  1 Node-gated skip inside pytest;
- Node-gated DOM harness suites (the four CSV journey checks + the existing shared-editor and
  rendering harness checks) run green in the approved Node-bearing setup (Node 26.12.1 bound
  read-only into the pinned image; no image/lock change);
- full maintained suite 818 passed, 3 skipped (skips are exactly the Node-gated harness tests);
- R smoke scripts r_composer_preview_smoke and r_composition_smoke green;
- real neutral render 17/17 checks and the disclosure scan clean (see below).

Remaining: real-browser review of the journey (reachable via the preserved checkout under the
unchanged review arrangement), and then slices C–E.

## Review-service note (2026-10-31)

Container e6c0233ca79e (the Round B1 review service) was accidentally removed by this session
while clearing the CSV review-scaffolding containers; its runtime state was never touched (the
work root with the two Custom drafts, the researcher preset draft and the nine saved reports is
intact on disk). The service was re-created immediately with the preserved launcher
(b-round-b1-20261029T232154Z-78941/review/start.sh and forwarder.py), the same container name,
the same bind mounts and the same loopback-only port 2719; only the per-run token file was
regenerated (the service writes a fresh one on every start by design). No credentials rotated,
no saved state modified. This is a restore of the preserved service, not a different deployment;
the CSV review scaffolding containers were removed and are not run again.

Reachability limitation for browser review: from inside this session the rootless Docker daemon's
published ports (2719 included) are not reachable through the sandbox loopback, so no live
browser review of the service is possible here. The rendered artifacts are reviewable as static
files (same content the service serves):
- report: ~/.state/composer-bootstrap/csv-b-check/rendered/rendered/work/out/report.html
- methods: ~/.state/composer-bootstrap/csv-b-check/rendered/rendered/work/out/methods.html
- provenance: …/out/provenance.json · evidence: …/out/data/ · recipe: …/out/reproduction/composition.json
The frontend journey is structural-tested by the Node DOM harness (real app.js + real server
transcript) and remains pending real-browser review per the milestone gate.

Command reference for the evidence runs (each step with recorded exit in `exits.txt` inside
each evidence dir):
- Focused: `bash ~/.state/composer-bootstrap/csv-b-check/run.sh`
- Full suite + R smokes: `bash ~/.state/composer-bootstrap/csv-b-check/run_suite.sh`
- Real neutral render: `docker run … /opt/health-report-venv/bin/python /render.py`
  (script in csv-b-check/, NEUTRAL_WORK points into /evidence).

## Compliance notes (brief §15/§17/§18)

Neutral IDs never alias health stakeholder IDs (`neutral-overview` etc. — no "fifth audience").
No composition-recipe/3. No generic PDF claim. Captured source is never included in the
shareable package by default; the neutral package publishes analysis + evidence, not raw rows.
Health tabular v1/v2 untouched. All new evidence paths under
~/.local/state/composer-bootstrap/csv-b-<timestamp>.
