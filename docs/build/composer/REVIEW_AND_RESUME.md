# Review, revision and interruption protocol

Status: templates only; no execution/review asserted by existence. Read [HANDOFF.md](HANDOFF.md) and [requirements.json](requirements.json).

## Candidate review record

For G2/G4/G6 record review ID, source commit, base/build/task branch, fixture/input and resolved recipe identities, render/evidence manifest hash, runtime/browser/viewport, actual output location, desktop/narrow and collapsed/expanded screenshots, commands/exits, automated outcomes, checked actions, reviewer/time, PASS/ISSUE/NOT REVIEWED per item, requirement/task IDs, known limits and next revision/decision owner.

## Candidate entry G1-REFBLOCK-01 (author-run, visual review pending)

- Base commit `8b748d7d07ee524d5d9d980ed11a1bbda1326536` on `design/contracts`; candidate is **uncommitted** working-tree state (no commit SHA exists for it). No acceptance status changes.
- Candidate file hashes: `publish.py 02d1688a67a527aa9fe800ecf1f8160a46c5958848033258dd56fefc06a781e4`,
  `report_shared.qmd dba6251aeef7899f0e22693a1c7069cd20e12e5cdc9e8a599d6389991a5ed8ea`,
  `report_helpers.R cc581508b1fa3724efdef8d67b32eb354ccb137f2dd5127b413f1d20d9460462`,
  `audience_reports.R 22a989ee8d484d0a72618ac1c7ed63cbdc3b538979607fb71dde565b4e24745a`,
  `test_render_block.py 8f70f205a502a25db8c2aafb77ca0ea320bd44e53f0dad4176526e0108dee3ce`,
  `r_block_dispatch_smoke.R 843dfe731508b27a00b2bb76066c25a38debcf905888c1a8dfa4f1f1d57cd6c5`.
- Input: retained baseline `~/.local/state/composer-bootstrap/baseline-lJXSvvGc/output`, researcher bundle, snapshot `d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee`, unchanged. Subject `campylobacteriosis`, saved value `20.170963739142426`.
- Evidence paths:
  - Checks `~/.local/state/composer-bootstrap/g1-block-checks-20261028T063456` (focused.log, r-dispatch-smoke.log, maintained-suite.log) and earlier failed first pass `~/.local/state/composer-bootstrap/g1-block-checks-20261028T063123`.
  - Failed render (Quarto `unused argument (evidence_file)`, exit 1): `~/.local/state/composer-bootstrap/g1-block-render-20261028T063228/render1|render2/render.log`.
  - Successful renders: `~/.local/state/composer-bootstrap/g1-block-render-20261028T063605/render1` and `/render2` (report.html, methods.html, provenance.json, render.log).
- Commands/exits: focused Python 100 passed, exit 0; R dispatch smoke passed, exit 0; maintained suite 453 passed (31.57s), exit 0; render1 exit 0; render2 exit 0. Image `sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8`, rootless, `--network none`, `--cpus 2 --memory 4g --memory-swap 5g --pids-limit 512`, repository and baseline read-only.
- Automated outcomes: blocks identical across both renders and full provenance identical excluding `rendered_at_utc`; embedded provenance equals sidecar in both renders; one block section and one inspector per render; analytical and result identities equal the standalone record `g1-real-bundle-20261028T062425/resolved.json`, instance identity differs because the wiring label `block-reference-comparison` replaces `real-campylobacteriosis`.
- Regression accounting against the baseline `report.html`: 211 changed lines, 200 added, 11 removed, all classified — 1 navigation line (one added `#reference-block` entry, no link removed), 8 provenance/metadata values (canonical_root, git_commit, git_worktree_clean, rendered_at_utc ×2, three presentation/source digests — all expected from the changed files and the render invocation), 2 further metadata duplicates of canonical_root and timestamp inside the embedded JSON. Section order unchanged except the inserted `block-reference-comparison` between `diseases` and `reproduction`; no existing section removed or re-nested.
- **ISSUE (unexpected regression, not repaired):** the new navigation entry emits `href="#reference-block"`, but no element carries `id="reference-block"`; the block section carries `id="block-reference-comparison"`. The navigation anchor is therefore dangling. Expected fix is to align the section entry id with the helper's section id (or drop the navigation entry); deliberately left for the owning writer.
- Visual review: **NOT REVIEWED**. No browser, headless renderer, Playwright or Selenium is installed on the host, and `Dockerfile.report` declares no browser dependency; no screenshots exist. Desktop/narrow viewports, inspector open/closed, keyboard activation, focus visibility, overflow and offline expansion remain unverified.
- Scientific/independent review: **NOT REVIEWED**. Author-run only; no independent verifier, no publication approval, no G1 acceptance. G0 remains open.

### Follow-up G1-REFBLOCK-01a: dangling navigation anchor repaired

- Repair: the section-list entry in `templates/audience_reports.R` now uses
  `id='block-reference-comparison'`, matching the helper's section id. The navigation
  entry was kept and no other section id changed. Base commit unchanged at
  `8b748d7d07ee524d5d9d980ed11a1bbda1326536`; the candidate remains uncommitted.
- Changed-file hashes now: `publish.py 02d1688a67a527aa9fe800ecf1f8160a46c5958848033258dd56fefc06a781e4`,
  `report_shared.qmd dba6251aeef7899f0e22693a1c7069cd20e12e5cdc9e8a599d6389991a5ed8ea`,
  `report_helpers.R cc581508b1fa3724efdef8d67b32eb354ccb137f2dd5127b413f1d20d9460462`,
  `audience_reports.R 719f9018c62d432b0addcac55b9614e1bbc4c9ecf915d0aa6c212020b88803cd`,
  `test_render_block.py 8f70f205a502a25db8c2aafb77ca0ea320bd44e53f0dad4176526e0108dee3ce`,
  `r_block_dispatch_smoke.R 9428ab2044b2f64e3cb03c66fd5db1a087b77b5dba68655ad40d47965cb5409d`.
  The earlier hashes in the entry above remain the historical candidate record.
- Rendered-output regression check added to `tests/r_block_dispatch_smoke.R` as an
  optional argument: given a produced `report.html` it asserts the navigation href is
  `#block-reference-comparison`, exactly one element carries
  `id="block-reference-comparison"`, `href="#reference-block"` is absent, and the
  inspector id occurs exactly once. It is a rendered-HTML check, not a source-text one.
- New evidence: `~/.local/state/composer-bootstrap/g1-block-render-anchor-20261028T064123`
  with `focused.log`, `r-dispatch-smoke.log`, `rendered-anchor.log`,
  `render/{report.html,methods.html,provenance.json,render.log}`.
- Commands/exits: focused Python (test_render_block.py + test_composer_contracts.py)
  100 passed, exit 0; R dispatch smoke exit 0; one researcher render exit 0; rendered
  anchor checks exit 0. Embedded provenance equals the sidecar; nav href 1, obsolete
  href 0, block id 1, inspector id 1; block `verified`, subject `campylobacteriosis`,
  value `20.170963739142426`.
- Not rerun for this bounded change: maintained suite (earlier 453 passed run remains the
  record for the pre-repair candidate) and a second determinism render.
- Visual and independent review remain **NOT REVIEWED**. Human review file:
  `~/.local/state/composer-bootstrap/g1-block-render-anchor-20261028T064123/render/report.html`.
- User-reported feedback (after inspecting the anchor-repaired candidate): the rendered
  HTML "works as wanted". This is recorded as **user-reported functional satisfaction for
  the inspected candidate only**. It is not a desktop/narrow-layout acceptance, not an
  accessibility review, not keyboard/focus verification, and not scientific acceptance;
  no viewport screenshots exist and no independent verifier was involved.
- Direction recorded with that feedback: the existing canonical report is an integration
  scaffold. The product direction remains a block-composed report, so further panels
  should not be accumulated in the old layout; the next slice is block composition, not
  another planning round.

## Candidate entry G1-COMPOSE-01: first block-composition slice (author-run, visual review pending)

- Base commit `09b1fea60693274101cee7787001580a06ea1def` on `design/contracts`; candidate is
  **uncommitted** working-tree state. No acceptance status changed.
- Changed paths (6 implementation/test files, all uncommitted):
  `M scripts/health_pipeline/publish.py db50d0bb6412635bca6c1b9fae94e4d57a0f5a86f45ccd3e7a30b06210dc4b50`,
  `M scripts/health_pipeline/report_shared.qmd ca9f63d417d258aac0cd1a68d3acca027e726aa18ecaa16b5ae462b94ef26b76`,
  `M scripts/health_pipeline/templates/report_helpers.R c4897781bf3ce120036feba711227dadd4b1aa433b974f7852b88b68825c91ff`,
  `A scripts/health_pipeline/config/composer/compositions/researcher.json b627a058f211ec42be9e5880eba3c67f482f5c98f94b620e55c6b875386b5c2d`,
  `A tests/test_composition.py 18fa7fefd79d618f3617a84f17eaf4d41d306cd07539917eafc7ff32cdf3ee03`,
  `A tests/r_composition_smoke.R 405c47d38ecf6459cdfc04adbeefaf80f25a575b8812d2ad0f5b7cfe843fa6cf`.
  (Earlier turns' six-path count for G1-REFBLOCK-01 referred to a different candidate; this entry
  lists the composition candidate's actual paths.)
- Composition mechanism: recipe document `health-report/composition-recipe/1` with ordered
  `{block, instance_id}` entries; `publish.load_composition` rejects unknown fields, wrong
  contract, empty list, unknown block type, unsafe or duplicate instance ids; `publish.render`
  forwards `-P block_recipe:<absolute path>` to `report.qmd` only; `report_shared.qmd` dispatches
  to `compose_report_html` when a recipe is supplied and otherwise to the unchanged legacy
  `findings_html` route; `composition_registry` in `report_helpers.R` holds four renderers
  (`intro`, `reference-comparison`, `limitations`, `reproduction`) that reuse existing helpers;
  navigation is derived from the rendered section ids.
- Recipe handoff is an explicit CLI parameter (`--composition`), not a stakeholder setting:
  `workflow/config.schema.json` has `additionalProperties: false` and `analyse.load_config`
  rejects unknown keys, so the stakeholder schema was **not** changed and no `composition` key
  was added to `config/stakeholders/*.json`. Provenance records `composition.mode`,
  `recipe_path`, `recipe_sha256` and `effective_recipe`.
- Commands/exits (recorded image `sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8`,
  rootless, `--network none`, `--cpus 2 --memory 4g --memory-swap 5g --pids-limit 512`,
  repository and baseline read-only):
  - `~/.local/state/composer-bootstrap/g1-compose-checks-20261028T065016/focused.log`
    — 107 passed (2.52s), exit 0
  - `~/.local/state/composer-bootstrap/g1-compose-checks-20261028T065016/r-composition-smoke.log`
    — `r-composition smoke passed`, exit 0
  - `~/.local/state/composer-bootstrap/g1-compose-checks-20261028T065016/maintained-suite.log`
    — 460 passed (30.82s), exit 0
  - `~/.local/state/composer-bootstrap/g1-compose-render-20261028T065107/composed/`
    — researcher composition render, exit 0 (`report.html`, `methods.html`, `provenance.json`, `render.log`)
  - `~/.local/state/composer-bootstrap/g1-compose-render-20261028T065107/legacy/`
    — explicit legacy-mode render, exit 0 (same artifacts)
- Composed verification: sections in recipe order
  `overview → block-reference-comparison → limitations → reproduction`; navigation targets equal
  those four ids; exactly one reference-comparison section; embedded provenance equals the
  sidecar; provenance `composition.mode = composed` with `effective_recipe` in the same order and
  `recipe_sha256` starting `b627a058f211`.
- Legacy verification: section ids and order identical to the pre-composition researcher render;
  no `composition` record in provenance; 16 changed lines (8 added, 8 removed), attributable to
  git commit, template/helper digests and render timestamps; embedded provenance equals the
  sidecar. The legacy route therefore remains available and retains its prior content.
- Human review files: composed
  `~/.local/state/composer-bootstrap/g1-compose-render-20261028T065107/composed/report.html`;
  legacy `~/.local/state/composer-bootstrap/g1-compose-render-20261028T065107/legacy/report.html`.
- **Limitation recorded plainly:** recipe `instance_id` values are validated for syntax and
  uniqueness, but the renderer dispatch does **not** consume them — every renderer still emits a
  fixed DOM id (`overview`, `block-reference-comparison`, `limitations`, `reproduction`).
  Repeated block types with distinct instance ids have therefore **not** been demonstrated as
  safe (duplicate DOM ids and duplicate navigation targets would occur). This is a known gap of
  this slice, deliberately not repaired here.
- Also unproven: per-instance parameters beyond the block type (no block-level option objects),
  block-local ordering inside a type, and any second audience composition. Health institution and
  public remain on their existing shared-template route.
- Visual review: **NOT REVIEWED** — no browser or headless tooling is available; viewport,
  keyboard/focus, inspector open/closed and overflow checks remain pending. Independent review:
  **NOT REVIEWED**. G0 remains open; R02 is not accepted; "rendered successfully" is not a
  scientific verification claim.

### Follow-up G1-COMPOSE-01a: visible block-based composition (author-run, visual review pending)

- Design-direction correction recorded: the first candidate "is now a well rendered old
  report". Rendering and recipe ordering worked; the block experience was not visible.
- Changes (same six paths, uncommitted; `dashboard.css` deliberately untouched, no new
  production path): 1) `compose_report_html` no longer uses `presentation_open`,
  `report_metadata` or the legacy `dash-footer`; it emits a self-contained
  `<div class="composed-report">` shell with an inline `<style>` scoped to `.composed-*`
  classes, a short introduction line and a block navigation. 2) The section wrapper and
  its navigation target are now produced by the composer from
  `composition_section_ids` (no substring extraction, no nested `<section>`). 3) The
  registry returns block *body* only; each block is wrapped in a `composed-block` card
  with a kicker (“Primary finding” / “Supporting block”) and a readable heading from
  `composition_labels` (Context, Reference comparison, Limitations, Reproduction).
  4) `reference_block` gained `variant='composed'`; the default `'legacy'` output is
  unchanged and still used by the legacy route. 5) The composed variant returns body
  content only: large saved percentage, subject, comparison years, counts and units, a
  caution that notification changes do not establish disease severity or statistical
  significance, and one secondary native `<details>` “Inspect this block” carrying the
  existing metric ids, formula, availability, snapshot, effective settings,
  implementation digests, identities, reproduction entry point and lineage record.
- Known limitation retained unchanged: recipe `instance_id` values are validated but not
  consumed by the renderer; fixed DOM ids per block type remain, so repeated block types
  with distinct instance ids are still not demonstrated safe. Not resolved here.
- Evidence (recorded image, rootless, no network, read-only repo/baseline):
  - `~/.local/state/composer-bootstrap/g1-compose-visual-checks-20261028T070316` —
    `focused.log` 107 passed (exit 0), `r-composition-smoke.log` exit 0,
    `r-dispatch-smoke.log` exit 0, `maintained-suite.log` 460 passed (exit 0). The first
    smoke attempts failed on test-side fixtures only (navigation regex attribute, and a
    style-block occurrence count); both were fixed in the smoke, not in the renderer.
  - `~/.local/state/composer-bootstrap/g1-compose-visual-render-20261028T070414` —
    `composed/render.log` exit 0, `legacy/render.log` exit 0.
- Verified on the actual composed HTML: sections `overview → block-reference-comparison →
  limitations → reproduction` (recipe order); navigation reads “Context / Reference
  comparison / Limitations / Reproduction” with hrefs equal to the section ids; exactly one
  primary card and three supporting cards; exactly one “Inspect this block” disclosure;
  finding value `+20.2%`; caution text present; no duplicate DOM ids in this recipe;
  embedded provenance equals the sidecar for both views. Legacy HTML contains no
  `composed-report`/`composed-block` markup and keeps its prior section sequence.
- Human review file (composed):
  `~/.local/state/composer-bootstrap/g1-compose-visual-render-20261028T065107/composed/report.html`
- Visual review and independent review remain **NOT REVIEWED**; no screenshots or browser
  checks were produced. G0 remains open; no acceptance status changed.

### PDF diagnosis after the composed candidate (G1-PDF-01, author-run)

- User-reported feedback recorded for scope: the block-based direction looks good;
  expandable data information is useful where appropriate; rendering/layout quality is poor
  but functionality has priority; PDF export no longer works. This is **not** visual or
  accessibility acceptance, and no styling work was performed.
- What the user-facing action is: the composed page carries no PDF control of its own. The
  only PDF action is Quarto's automatic "Other Formats → PDF" link
  (`<a href="report.pdf">`) injected by Quarto from the `pdf:` format declaration in
  `report_shared.qmd`; it appears inside `#quarto-alternate-formats`, not from the
  templates. The composed shell's blocks add only CSV, methods and lineage links.
- Demonstrated failure cause: that link resolves to `report.pdf` in the same directory, and
  the composed evidence directory
  `~/.local/state/composer-bootstrap/g1-compose-visual-render-20261028T070414/composed/`
  contains only `report.html`, `methods.html`, `provenance.json` and `render.log` — no
  `report.pdf`. The link is therefore dead in any HTML-only render. This is a missing
  co-located artifact for the preview, not evidence that the PDF renderer broke.
- Canonical PDF generation still works: `publish.py pdf` with the retained bundle ran once
  in `~/.local/state/composer-bootstrap/g1-pdf-diagnose-20261028T071159` (created by this
  turn's single PDF run) and exited 0, producing a 40,544-byte `report.pdf`, a 30,790-byte
  `methods.pdf` and `provenance.pdf.json`. Text extraction tooling (`pdftotext`) is absent in the image, so
  the PDF's pagination/content was **not** independently inspected; content type below is
  established from source, not from the artifact.
- Composed PDF is **not supported**: `report_shared.qmd` dispatches the composer only under
  `knitr::is_html_output()`. For LaTeX output the researcher (`technical`) layout goes to
  `audience_document_pdf(b)` and the editorial layout to its own LaTeX branch, so a PDF is
  always the legacy document even when `--composition` is supplied. `publish.py` does pass
  `-P block_recipe:` to the `report` document for both formats, but the PDF path ignores it.
  Linking a composed HTML to that PDF without a label would misrepresent the artifact.
- Smallest proposed repair (not implemented in this turn, because it cannot be
  render-verified within the remaining budget): in `compose_report_html`, next to the
  composer's closing note, state plainly that the PDF export is the legacy layout and is
  only present when the release route generates it; alternatively suppress the alternate
  formats block for composed renders via the `report_shared.qmd` format options. Both stay
  inside existing candidate paths. A composition-aware PDF would require a separate
  LaTeX/PDF renderer path and an explicit format decision, which is out of scope here.
- Evidence for this diagnosis:
  `~/.local/state/composer-bootstrap/g1-compose-visual-render-20261028T070414/composed/report.html`
  (verified path, exists) and the PDF run directory named above.

### Follow-up G1-PDF-01a: composed report is HTML-only (author-run)

- Decision: the composed report is HTML-only. Its HTML must not offer the legacy PDF as if
  it exported the composed report, and the diagnostic PDF was **not** copied beside any
  preview to make a link resolve. The legacy HTML/PDF route and its existing PDF link
  behaviour are unchanged.
- Implementation (existing candidate paths only): `publish.render` passes
  `-M format-links:false` to the `report` document when a recipe is supplied and the
  format is HTML, which suppresses Quarto's automatic alternate-format offer for composed
  HTML without removing the `pdf:` format globally and without CSS hiding or HTML
  post-processing. The reproduction block now carries the visible note “PDF export of this
  composed report is not yet available.” An explicit PDF request with `--composition`
  raises `ValueError('PDF export of a composed report is not supported; omit
  --composition for the legacy PDF')` before any renderer runs, so the recipe cannot be
  silently ignored.
- Checks: `~/.local/state/composer-bootstrap/g1-pdf-htmlonly-checks-20261028T071548` —
  focused Python 110 passed (exit 0), R composition smoke exit 0, R dispatch smoke exit 0.
  (New tests: composed HTML sends `format-links:false` to `report.qmd` only, composed PDF
  is rejected before `package`/`run`, legacy PDF still renders without the flag.)
- Renders: `~/.local/state/composer-bootstrap/g1-pdf-htmlonly-render-20261028T071601` —
  composed exit 0, legacy exit 0. On the actual HTML: composed has **0** `href="report.pdf"`
  links, contains the availability note once, and embedded provenance equals the sidecar;
  legacy still has its 2 PDF references (navigation header plus Quarto alternate formats)
  and embedded provenance equals the sidecar. An empty `#quarto-alternate-formats`
  container remains in the composed page but carries no PDF offer.
- No PDF rerun in this turn; the earlier diagnostic PDF run at
  `~/.local/state/composer-bootstrap/g1-pdf-diagnose-20261028T071159` remains the record,
  with its stated limitation that PDF content was not text-extracted.
- Composed HTML for review:
  `~/.local/state/composer-bootstrap/g1-pdf-htmlonly-render-20261028T071601/composed/report.html`.
- Visual, accessibility and independent review remain **NOT REVIEWED**; styling and the
  instance-ID limitation are untouched; G0 open.

### Checkpoint commit and follow-up G1-INSTANCE-01: recipe instance identity (author-run)

- Checkpoint: commit `8ad03556c485f79be0cede28a5ea2fd690ffd13d` (parent
  `09b1fea60693274101cee7787001580a06ea1def`, message
  `feat: compose researcher HTML from an ordered block recipe`) stages exactly the seven
  candidate paths: `docs/build/composer/REVIEW_AND_RESUME.md`,
  `scripts/health_pipeline/publish.py`, `scripts/health_pipeline/report_shared.qmd`,
  `scripts/health_pipeline/templates/report_helpers.R`,
  `scripts/health_pipeline/config/composer/compositions/researcher.json`,
  `tests/r_composition_smoke.R`, `tests/test_composition.py`. `git diff --cached --check`
  exited 0. The only text correction at checkpoint time replaced the truncated human-review
  path with the existing
  `~/.local/state/composer-bootstrap/g1-pdf-htmlonly-render-20261028T071601/composed/report.html`.
  No test or render was rerun for the checkpoint; the earlier evidence labels above are
  unchanged history.
- This follow-up is **uncommitted** on top of that commit and touches four paths
  (`publish.py`, `report_helpers.R`, `tests/r_composition_smoke.R`,
  `tests/test_composition.py`). No schema, analysis, metric, CSS, block-type or
  audience-recipe change.
- Changes: every composition registry entry now carries explicit metadata
  (`label`, `primary`, `render`) and the renderer is called with the recipe entry. The
  section DOM id is the recipe `instance_id` and navigation is built from that metadata, not
  from parsed HTML. `reference_block(variant='composed')` requires an instance id, selects
  the matching checked record by `instance_id`, and emits `#<instance_id>-inspect`; the
  legacy variant keeps its first-record selection, `#block-reference-comparison` panel and
  `-inspector`/`block-data`/`block-method`/`block-implementation`/`block-reproduction` ids.
  `publish.build_block` receives the recipe instance id, and
  `provenance.composition.instances` records each entry's `contract_instance_id`,
  `contract_status` and `instance_identity`. Repeated stateless blocks are allowed with
  distinct ids; a second `reference-comparison` entry is rejected in both Python and R
  (`Repeated reference-comparison blocks are not supported yet`) rather than reusing or
  relabelling one checked record.
- Commands/exits (image `sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8`,
  rootless, `--network none`, `--cpus 2 --memory 4g --memory-swap 5g --pids-limit 512`,
  repository and baseline read-only), all under
  `~/.local/state/composer-bootstrap/g1-instance-20261028T120255`:
  `focused.log` 114 passed exit 0; `r-composition-smoke.log` exit 0;
  `r-dispatch-smoke.log` exit 0; `maintained-suite.log` 467 passed (29.23s) exit 0;
  `composed/render.log` and `legacy/render.log` exit 0;
  `rendered-verification.log`, `composed-rendered-checks.log` and
  `legacy-rendered-checks.log` exit 0.
- Verified on the rendered files (`composed/report.html`, `legacy/report.html`,
  `provenance.json` in the same directory): composed section ids and navigation targets are
  `intro-0001 → block-reference-comparison → limitations-0001 → reproduction-0001`, each
  href and id exactly once, one primary card of four blocks, one
  `block-reference-comparison-inspect`, no legacy `-inspector` id, no `href="report.pdf"`
  and the availability note present. Embedded provenance equals the sidecar for both routes.
  `composition.instances` order equals the recipe; the reference entry's
  `contract_instance_id` equals its recipe id, its `instance_identity` equals the checked
  block record, and that identity string appears in the composed HTML. Legacy section ids
  are `overview, parameters, coverage, quality, methods, totals, trends, diseases,
  block-reference-comparison, reproduction, limitations, provenance` — identical to the
  previous legacy render; the only normalised differences are the render-code digest, git
  commit and render timestamp. Legacy still carries its two PDF references.
- Known limitations retained: repeated reference-comparison is refused rather than
  supported (no per-instance subject/options); no per-block option objects; no second
  audience composition; PDF remains legacy-only. Visual, accessibility, keyboard/focus and
  independent review remain **NOT REVIEWED** (no browser or headless tooling); "rendered and
  checked" is not a visual or scientific acceptance claim. G0 remains open; R02 is not
  accepted.

### Candidate entry G1-BATCH-01: three-audience one-command composed batch (author-run)

- Anchor commit `2cf666f0fb9cf501d7b09b32be76b5f5d0f57a95` on `design/contracts`; candidate
  is **uncommitted** working-tree state. No acceptance status changed.
- Changed paths: `A scripts/health_pipeline/config/composer/compositions/health_institution.json`,
  `A scripts/health_pipeline/config/composer/compositions/public.json`,
  `M scripts/health_pipeline/publish.py`, `M tests/test_composition.py`,
  `M tests/r_composition_smoke.R`, `M README.md`, and this review record. `researcher.json`
  is unchanged; no schema, analysis, release-verifier, Snakemake or CSS change.
- Insertion point: `publish.py` gains `render_composition_batch` and a `batch` CLI action
  that calls the existing `render()` per audience. Recipes are validated by the existing
  `load_composition`; `recipe.audience` must equal the requested audience, and a composed
  `render()` now also rejects a recipe whose audience differs from the bundle's
  `stakeholder.json.id`. Bundle input is `<bundle-root>/<audience>/data`; no audience falls
  back to another audience's bundle. Failures are collected per audience, printed, and turn
  into a nonzero exit; partial outputs are not reported as a complete batch.
- Audience differences are real inputs plus order, but the rendered bodies are largely
  shared (see the follow-up below): each audience uses its own saved bundle
  (`presentation.layout`/`detail_level`, title, question, `outputs`, checks) and its own
  recipe instance ids. researcher keeps intro → reference-comparison → limitations →
  reproduction; health_institution is decision-first (reference-comparison → intro →
  limitations → reproduction); public is caveat-first (intro → limitations →
  reference-comparison → reproduction). Every recipe keeps `limitations` and `reproduction`
  (evidence access). All three share the same saved campylobacteriosis reference comparison
  (`+20.2%`), which is the same underlying scope — it is not recomputed or relabelled per
  audience.
- Command (pinned image, bounded rootless setup, `--network none`, repo/baseline read-only):
  `python scripts/health_pipeline/publish.py batch --bundle-root /baseline/reports
  --output-root /evidence/reports
  --data-root /baseline/snapshots/d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee
  --workflow-config workflow/config.yaml`. README documents the host equivalent over
  `results/reports` → `results/composed`.
- Evidence `~/.local/state/composer-bootstrap/g1-three-audience-20261028T121823`:
  `focused.log` 122 passed exit 0; `r-composition-smoke.log` exit 0; `r-dispatch-smoke.log`
  exit 0; `maintained-suite.log` 475 passed (28.08s) exit 0; `batch.log` exit 0 (three
  audiences rendered); `batch-failure.log` exit **1** with
  `1 of 3 composed reports failed: public` and two other reports left in
  `failure-reports/`; `rendered-verification.log` exit 0; `rendered-r-checks.log` exit 0 for
  all three audiences; `legacy-researcher/render.log` exit 0.
- Outputs: `reports/researcher/report.html`, `reports/health_institution/report.html`,
  `reports/public/report.html` (each with `methods.html`, `provenance.json`). Verified per
  audience: section ids and nav targets equal the recipe instance ids in order, each href/id
  exactly once, no duplicate `id` attributes in the page, one primary card, one
  `<instance>-inspect` and no legacy `-inspector`, checked record and
  `composition.instances` agree (`contract_instance_id`, `contract_status=verified`,
  `instance_identity` equals the block record and appears in HTML), embedded provenance
  equals the sidecar, `effective_parameters.id`/presentation/title/question equal that
  audience's bundle, and no `href="report.pdf"` while the HTML-only note is present.
  Legacy researcher render keeps its prior section ids and two PDF links and has no
  `composition` record.
- Not done / limitations: this is presentation-only rendering of unchanged retained bundles;
  no acquisition, harmonisation or analysis was run. Repeated reference-comparison, per-block
  options, a second non-composed audience route and composed PDF remain unsupported. Visual,
  accessibility, keyboard/focus and independent review are **NOT REVIEWED**; no browser was
  used. G0 remains open; R02 and challenge requirements are not accepted.

### Follow-up G1-BATCH-01a: documented command correction and audience-claim check

- README defect corrected: the batch example passed a host-expanded
  `$(pwd)/results/snapshots/<snapshot-id>` as `--data-root`, but `compose.yaml` mounts the
  repository at `/app`, so that host path does not exist inside the container. The example
  now uses `/app/results/snapshots/<snapshot-id>` and states that these are container paths.
  No code, schema or orchestration change.
- The retained-baseline demonstration was re-run once with the exact command below into a new
  evidence directory; previous evidence and logs were not overwritten.
  `~/.local/state/composer-bootstrap/g1-three-audience-doc-verify-20261028T123032`:
  `batch.log` exit 0 (three audiences rendered), `rendered-verification.log` exit 0 (same
  recipe-order, instance-identity, provenance-equality and no-PDF checks as above).

```sh
E=~/.local/state/composer-bootstrap/g1-three-audience-doc-verify-20261028T123032
mkdir -p "$E"
docker --context rootless run --rm --pull never --user 0:0 \
  --network none --cpus 2 --memory 4g --memory-swap 5g --pids-limit 512 \
  -e PYTHONDONTWRITEBYTECODE=1 -e HEALTH_REPORT_PROJECT=/app -e R_PROFILE_USER=/app/.Rprofile \
  -v /home/builder/composer-sandbox:/app:ro \
  -v /home/builder/.local/state/composer-bootstrap/baseline-lJXSvvGc/output:/baseline:ro \
  -v "$E":/evidence:rw -w /app \
  sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8 \
  python scripts/health_pipeline/publish.py batch \
    --bundle-root /baseline/reports --output-root /evidence/reports \
    --data-root /baseline/snapshots/d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee \
    --workflow-config workflow/config.yaml
```

- This block is a retained-bundle presentation demonstration: it re-renders the saved bundles
  under `/baseline/reports` with bounded, network-disabled Docker and writes only to the new
  `/evidence` directory. It does not acquire source data and does not re-run harmonisation or
  analysis; full analysis reproduction remains `snakemake --cores 2`.
- Audience-claim check on the rendered bodies (`audience-body-diff.log` in the same new
  evidence directory): **public** is the only audience with body-level plain-language
  adaptation — its Limitations quality sentence is rewritten for
  `detail_level=plain_language` ("Before this summary was made…"). **researcher** and
  **health_institution** share identical Limitations, reference-comparison body, counts and
  caution, reproduction prose/code sample and evidence fields apart from the block instance
  id and instance identity; the Context block differs only by the profile label
  (`Researcher · technical presentation` vs `Health institution · dashboard presentation` vs
  `General public · editorial presentation`). health_institution otherwise differs by title,
  block order, instance ids and provenance metadata, not by monitoring-specific wording. The
  finding, counts and caution are identical because the saved scope is identical.
- Therefore audience communication refinement is **pending**, not complete: monitoring wording
  for health_institution and plain-language treatment beyond the quality sentence are not
  shipped. No content redesign was attempted in this turn.


Review actual reading flow, distinct presets, graph/table clarity, evidence access, keyboard/focus/expansion, narrow layout and downloads. Scientific review is separately identified. A general PASS has only its supplied scope; do not invent browser/platform details. Screenshot comparison is not numerical/scientific acceptance.

## Feedback and revision

Use F-001 onward. Record candidate, affected requirement/block, requested change, rationale and blocking/nonblocking status. Classify presentation, behavior, scientific/contract, disclosure or scope; assign one owner and acceptance check. Never change metric meaning to satisfy visual preference.

Presentation fixes may reuse unchanged verified analysis but require correct render/evidence identity. Analytical changes require fresh appropriate analysis. Approve contract/scope/disclosure changes explicitly. Link each response to a revision commit and actual render; preserve old reviews rather than relabel them. No automatic screenshot-baseline acceptance or tolerance inflation.

## Resume record

Before pausing persist actual branch/commit/worktree status, owned uncommitted paths, task/dependencies, checked artifacts, failures/repair attempts, unresolved decisions, locks/other writers, next executable action and prohibited shortcuts. Raw/private logs remain in approved storage. Commit durable decision/checkpoint summaries at useful boundaries, not every transient thought.

On resume fetch/read current refs, inspect other writers, validate candidate/manifests and reconcile intervening changes. Never reset/stash/delete shared work or reuse stale success. Open questions are not implicit approvals.

## Runner opening instruction

Read this protocol, HANDOFF.md, requirements.json, five task briefs and governing product documents. Verify seed/frozen refs; establish preparation dispositions and current baseline; report unrun/failed checks. Assign the earliest unblocked minimal task before editing. Use its design branch from the current build tip. Preserve source/request contracts and workflow policy. Produce tested incremental commits and independently reviewed internal PRs to build/composer. At visual checkpoints supply actual rendered output and pause acceptance for human feedback. Continue only independent unblocked work. Do not merge the umbrella PR, modify frozen/main/releases or claim an unattended runner started merely by reading these instructions.

## Final acceptance

Required requirements have implementation and independent evidence; optional/deferred/decision-required items have explicit disposition. Existing routes are preserved or have approved parity-tested migrations. Actual UI/CLI complete the same supported request/replay journey. Inspectable inputs/methods/plotted results/code agree. Failure/tamper/path/cache/export checks pass. Latest clean candidate/environment are recorded, not inherited green checks. Human final review resolves or explicitly accepts issues. Promotion requires separate authorization.
