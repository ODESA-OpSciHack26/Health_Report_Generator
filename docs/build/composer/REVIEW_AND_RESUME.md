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

### Follow-up G1-AUDIENCE-01: composed audience explanations (author-run)

- Anchor commit `67816964f933476cabdb91b8d512c86357937813`; candidate is **uncommitted**.
  Changed paths: `M scripts/health_pipeline/templates/report_helpers.R`,
  `M tests/r_composition_smoke.R`, and this review record. No recipe, instance-id, schema,
  analysis, provenance, CSS or PDF change.
- Mechanism: the existing `presentation_profile(b)$layout` (`technical` / `dashboard` /
  `editorial`) selects one explicit `composition_copy` mapping. The composed
  reference-comparison block emits one visible `audience-explanation` paragraph and the
  limitations block appends one clarification. Values come from the saved block record;
  counts use the existing formatter and the percentage is the saved value (display rounded
  to +20.2%). The inspector, identities and block instance ids are unchanged.
- Content: **researcher** = metric bindings, counts, unit, formula, geography, period type,
  displayed value, and an explicit statement that the block supplies no inferential
  uncertainty estimate and no causal conclusion. **health_institution** = the saved
  monitoring question, observed change, CHFL national scope, reporting years and reference
  year, plus explicit limits: no canton- or institution-specific evidence, no operational
  threshold, no recommendation, and no incidence/severity/significance measurement.
  **public** = plain-language counts/years/percentage, notification ≠ infection caveat and
  "not a statistical test". All three limitations explanations state that automated checks
  test handling/consistency, not completeness or accuracy of source counts; the recorded
  "853 checks" sentence is retained only as an automated-check count, not proof.
- Commands/exits in `~/.local/state/composer-bootstrap/g1-audience-copy-20261028T124210`
  (pinned image, rootless, `--network none`, repo/baseline read-only):
  `focused.log` 122 passed exit 0; `r-composition-smoke.log` exit 0;
  `r-dispatch-smoke.log` exit 0; `maintained-suite.log` 475 passed (29.37s) exit 0;
  `batch.log` exit 0; `rendered-verification.log` exit 0; `rendered-r-checks.log` exit 0 for
  all three audiences; `audience-copy.log` and `audience-copy-isolation.log` exit 0. A first
  run at
  `g1-audience-copy-20261028T123918` preceded a markup-consistency fix (limitations
  explanation `<p>` → `<div>`) and is retained but not used; no log was overwritten.
- Verified on the three rendered HTML files: identical saved comparison in all outputs
  (`+20.2%`, `7,253`, `8,716`); exactly two `audience-explanation` blocks per page; the
  audience-specific sentence present only in its own report; recipe order, instance ids and
  navigation targets unchanged; <instance>-inspect present once; composition/provenance
  identities agree; embedded provenance equals the sidecar; no `href="report.pdf"` and the
  HTML-only note remains.
- Remaining limits: explanation-level copy only. Public still carries the technical
  limitations paragraphs apart from the plain-language quality sentence; health_institution
  has no institution-type indicators beyond national counts; no confidence intervals,
  denominators, adjusted rates or causal explanation are added. Visual, accessibility and
  independent review remain **NOT REVIEWED** (no browser). G0 open; R02 and challenge
  requirements not accepted.

### Candidate entry G1-EVIDENCE-01: published evidence artifacts and explainable warnings

- Anchor commit `fffac88f26893a13fad3a73770a7aad9e4e06455`; candidate is **uncommitted**.
  Changed paths: `M scripts/health_pipeline/publish.py`,
  `M scripts/health_pipeline/templates/report_helpers.R`,
  `M scripts/health_pipeline/templates/audience_reports.R`,
  `M scripts/health_pipeline/templates/methods.qmd`, `M tests/test_composition.py`,
  `M tests/r_composition_smoke.R`, `M README.md`, and this record. No analysis, schema,
  contract-identity, release-verifier, Snakefile or stylesheet change.
- Demonstrated cause of the two dead controls (from disk, not browser): every composed
  `report.html` links `data/stakeholder.json`, `data/bundle.json`, `data/metrics.csv`,
  `data/lineage.csv` (and methods links more `data/*` files), but the published folder held
  only `report.html`, `methods.html`, `provenance.json`. `publish.package()` copied the
  bundle files into the temporary Quarto directory, and `render()` copied only the two HTML
  documents to the output folder, so no `data/` directory was ever published. `provenance.json`
  was co-located and worked. The missing targets are on disk, so this is a packaging defect,
  not a browser behaviour question.
- Repair: one explicit `EVIDENCE_ARTIFACTS` registry (id, bundle file, reader label, path,
  digest) in `publish.py`; `publish_evidence()` copies byte-for-byte from the bundle into
  `<report>/data/`, verifies manifest digests, and copies `bundle.json` as-is without
  inventing a self-digest. `validate_published_evidence()` parses the **published**
  `report.html` and fails on unresolved `data/` (or co-located methods/provenance) links;
  `render()` runs it for HTML after publishing. A missing advertised artifact produces a
  clear failure and a nonzero batch exit.
- Readable evidence: the composed reproduction block now includes
  “Report settings and source files” with the actual saved settings (audience id/title,
  geography, reporting years 2021–2025, reference year 2019, measures, exclusions,
  presentation, effective composition recipe and its digest) plus the manifest file list
  with byte sizes and SHA-256 prefixes. It explains that parameters are the settings that
  produced the report, that the manifest supports integrity checking, and that matching
  hashes do not establish scientific correctness. Raw actions are labelled
  “Download exact audience parameters — JSON” and “Download artifact manifest — JSON” and
  the existing downloads use the `download` attribute. `bundle.json` is explicitly not
  self-digested.
- Warning detail (saved records only): composed limitations gain a “What was flagged?”
  disclosure. Counting semantics are stated explicitly: **853 rows are check evaluations
  (one rule × one dataset), not 853 distinct rules and not 853 affected findings**;
  8 distinct rules, 56 datasets evaluated, 774 PASS, 76 SKIP, 3 WARN, 0 FAIL. The three real
  warnings are all `value_present` (missing values): antibiotic resistance 85.5% missing,
  wastewater sequencing 100.0% missing, wastewater viral load 52.7% missing. Each row shows
  the saved check title/rule meaning, severity, dataset, recorded diagnostic, and the saved
  selection record (“excluded — unclassified: not a classified count series” or
  “excluded — surveillance_signal: not a classified count series”). Exact dataset-id matching
  to `selection.csv` shows none of the flagged datasets is included, so the report says they
  are shown for completeness and makes no claim about an effect on displayed findings.
  Per-audience view sentences differ (technical: saved codes, no rerun; dashboard: selection
  decision, not an operational threshold; public: plain-language notes about source data).
  Unknown check ids keep the raw diagnostic and say no plain-language explanation is
  available.
- HTML-only PDF offer: composed `methods.html` no longer renders the legacy “PDF version”
  navigation link or Quarto's alternate-format offer (`html_only:true` and
  `format-links:false` for the methods document in composed HTML only). The legacy HTML/PDF
  route keeps its links.
- Evidence `~/.local/state/composer-bootstrap/g1-evidence-final2-20261028T132400` (pinned
  image, rootless, `--network none`, repo/baseline read-only): `focused.log` 128 passed
  exit 0; `r-composition-smoke.log` exit 0; `r-dispatch-smoke.log` exit 0;
  `maintained-suite.log` 481 passed (31.12s) exit 0; `batch.log` exit 0;
  `evidence-verification.log` exit 0; `structural-verification.log` exit 0;
  `link-check.log` exit 0; `rendered-r-checks.log` exit 0 for all three; `warning-section.log`
  exit 0; `legacy-researcher/render.log` exit 0. Earlier runs
  `g1-evidence-20261028T131448` and `g1-evidence-final-20261028T132015` are superseded by
  the methods-PDF repair and retained unchanged.
- Verified on the final published folders: all 7 local links per page resolve; 9 manifest
  artifacts are byte-identical to the retained bundle with matching SHA-256; no PDF link in
  composed report or methods pages; 853/8/56/3 semantics match the saved `checks.csv`;
  composition recipe digests and instance identities still agree; embedded provenance equals
  the sidecar; legacy render still produces `data/` and keeps its existing PDF links.
- Remaining limits: warnings are explained and linked to saved selection at dataset level;
  no line-level linkage to the displayed comparison is claimed. Visual, accessibility and
  independent review remain **NOT REVIEWED** (no browser). No ZIP/export system. G0/G1/R02
  unchanged; challenge requirements not accepted.

### Follow-up G1-EVIDENCE-01a: report-to-methods quality route and detailed check results

- Anchor unchanged at `fffac88f26893a13fad3a73770a7aad9e4e06455`; candidate still
  **uncommitted**. Changed in this follow-up: `publish.py`, `report_helpers.R`,
  `tests/test_composition.py`, `tests/r_composition_smoke.R`, `README.md`, this record.
  `audience_reports.R` and `methods.qmd` carry only the earlier link-label / HTML-only
  plumbing.
- Prior corrections checked: dataset-level relevance wording was already present and is
  kept; the final-package link validator covered only `report.html` and is now extended to
  `methods.html`; the artifact manifest explanation now distinguishes the published
  analysis bundle (all files named by `bundle.json` plus the manifest) from the raw source
  snapshot. The earlier counting sentence (“one rule applied to one dataset”) was **wrong**
  and is corrected: `checks.csv` has 853 rows but only 448 distinct (dataset, rule) pairs,
  with 36 repeated pairs (up to 26 rows for aggregation rules that record one row per
  compared measure/period). The UI now says “853 recorded check-result rows covering 8
  distinct rule identifiers and 56 datasets”, explains the repetitions, and does not infer
  affected-record or affected-finding counts.
- Shared preparation: `quality_results()` builds one ordered data frame (severity first) from
  saved `checks.csv`, `selection.csv` and `sources.csv`; `quality_summary_html()` (main
  report) and `quality_methods_html()` (methods) both derive totals, groups and rows from
  it, so the two pages cannot drift. The main report keeps a short “What was flagged?”
  disclosure with the category (Missing values / `value_present`, 3 results across 3
  datasets), audience-appropriate sentence, the relevance statement, a direct
  `methods.html#quality-checks` link and “Download exact check results — CSV”. The methods
  section (`id="quality-checks"`) shows the audience and saved scope, counting definitions,
  per-rule `<details>` explanations, and all 853 rows with status, check name/ID, dataset
  label/ID, recorded diagnostic, selection record and established relevance, plus a return
  link to `report.html#quality-summary`.
- Controls are progressive enhancement: rows are all present without JavaScript (no
  server-side truncation or hiding); the script starts the status filter on “Warnings and
  failures”, provides status/rule selects and dataset search, and updates “Showing N of 853
  recorded check results”. No network access, no new library. Table has a caption and
  `scope="col"` headers; the results area is a labelled, focusable scroll region.
- Downloads: every published artifact is listed with purpose, type, size, digest prefix and
  a direct `Download …` link (bundle.json marked “not self-digested”); the note states the
  folder publishes the 9 files named by the manifest plus the manifest, and that the raw
  source snapshot is not included. Methods quality section adds exact downloads for
  checks.csv, selection.csv and sources.csv.
- Real saved warnings (`checks.csv` rows): `value_present` for antibiotic resistance 85.5%
  missing, wastewater sequencing 100.0% missing, wastewater viral load 52.7% missing. All
  three datasets are recorded as excluded (`unclassified: not a classified count series` /
  `surveillance_signal: not a classified count series`). The summary therefore says:
  “These warnings concern datasets recorded as excluded from this report's selected inputs.
  Finding-level warning relevance has not been evaluated.”
- Evidence `~/.local/state/composer-bootstrap/g1-quality-final-20261028T141424` (pinned image,
  rootless, `--network none`, repo/baseline read-only): `focused.log` 130 passed exit 0;
  `r-composition-smoke.log` exit 0; `r-dispatch-smoke.log` exit 0;
  `maintained-suite.log` 483 passed (29.13s) exit 0; `batch.log` exit 0;
  `quality-verification.log` exit 0 (853 rows per methods page, matching totals on both
  pages, anchors, 9 artifacts byte-identical, warning details); `structural-verification.log`
  exit 0; `rendered-r-checks.log` exit 0 for all three. The earlier run
  `g1-quality-detail-20261028T140009` is superseded by the added audience/scope line and is
  retained unchanged.
- Remaining limits: filtering/keyboard interaction was not exercised in a browser — only
  markup, data and script presence are verified. The methods page is ~1.6 MB because it
  embeds all 853 rows and resources. Finding-level warning relevance remains unevaluated.
  No time-trend block was started. G0/G1/R02 and challenge requirements remain unaccepted.

### Follow-up G1-REPRO-01: evidence actions, reproduction layout and inert-search repair

- Anchor unchanged at `fffac88f26893a13fad3a73770a7aad9e4e06455`; candidate committed at the
  end of this slice. Changed paths: `publish.py`, `report_helpers.R`,
  `audience_reports.R`, `methods.qmd`, `tests/test_composition.py`,
  `tests/r_composition_smoke.R`, `README.md`, this record.
- Demonstrated evidence-link cause: the user's pasted provenance identity (source commit
  `67816964…`, rendered `2026-10-28T12:43:25+00:00`) matches the earlier
  `g1-audience-copy-20261028T124210` package, whose folder contains only `report.html`,
  `methods.html` and `provenance.json`. Every `data/…` target is absent there, while
  `provenance.json` resolves. The later `g1-quality-final-20261028T141424` and this slice's
  package contain `data/` with all manifest files; every action resolves from the final
  folder. This is a stale old folder, not a live defect in the current output; historical
  packages were not edited.
- Inert “Filter rows” diagnosis: `interactive_tables_script()` attached a search input and
  sorting to every `table.report-table`, including the hand-built “Report settings and
  source files” artifact table in the Reproduction block (and the methods quality table,
  which already has scoped controls). Table search is now explicit opt-in: `html_table()`
  emits `data-searchable="true"` and the generic script selects only
  `table.report-table[data-searchable]`. The settings and quality tables carry no such
  attribute, so the Reproduction block no longer gets a search control; the methods
  quality status/rule/dataset controls are unchanged and scoped to `#quality-results-table`.
- Evidence actions are now explicit and single-instance: “View report provenance — JSON”
  (`target="_blank"`, labelled as a view), “Download exact audience parameters — JSON”,
  “Download bundle manifest — JSON”, “Download Metrics — CSV”, “Download Calculation
  lineage — CSV”, “Open methods and source traceability”. Parameters/manifest/metrics/
  lineage appear once, in the existing settings/artifact table; the reproduction section
  links to that panel instead of duplicating raw links. Labels were normalised in
  `provenance_summary()`; the builds fingerprint and build-time input path are labelled as
  build-machine facts (“Build-time input location … readers are not expected to have this
  path locally”).
- Reproduction content is organised as requested: the code disclosure is titled “Show
  code: verify saved-file integrity and inspect results”, states that it checks published
  hashes against the saved manifest, reads saved metrics, does not verify source
  observations and does not rerun the production analysis, and points to existing
  environment instructions rather than a new environment manager. “How this report was
  produced” lists audience/presentation, snapshot, source dates, geography, reporting
  window, reference year, comparison year, measures, exclusions, commit/dirty state and
  render timestamp as separate facts.
- Executable validation: the displayed Python example was extracted from each published
  `report.html`, run with the pinned image from that report directory, with only its
  published `data/` as input. All three exited 0, verified every manifest digest, printed
  the saved group totals and reference changes, and confirmed all manifest files were
  present (`example-researcher.log`, `example-health_institution.log`,
  `example-public.log`).
- Evidence `~/.local/state/composer-bootstrap/g1-repro-final-20261028T200839` (pinned image,
  rootless, `--network none`, read-only inputs): `batch.log` exit 0;
  `repro-verification.log` exit 0; `quality-verification.log` exit 0;
  `structural-verification.log` exit 0; `rendered-r-checks.log` exit 0 for all three;
  `duplicate-link-check.log` exit 0; `maintained-suite.log` 483 passed (30.62s) exit 0;
  example logs exit 0. Superseded runs retained unchanged:
  `g1-quality-final-20261028T141424` (pre-repair), `g1-repro-evidence-20261028T195007`
  (capitalised labels), and the three timed-out/killed batch attempts
  `g1-repro-final-20261028T195619`, `…T200053`, `…T200445`.
- Remaining limits: no browser was available; clicking, tab opening, filtering, keyboard
  and download behaviour were not exercised — only file/path/markup/script checks and the
  executed inspection example. No ZIP/export mechanism, no new block, no analysis change.
  G0/G1/R02 and challenge acceptance remain unchanged.

### Candidate entry G1-SCOPE-01: explicit report scope and recipe v2 topic binding

- Anchor `459e6c7947a014348cfdab48ca124934cc6c7fc2`; candidate is **uncommitted**. Paths:
  `workflow/config.schema.json`, `scripts/health_pipeline/analyse.py`,
  `scripts/health_pipeline/composer_contracts.py`, `scripts/health_pipeline/publish.py`,
  `scripts/health_pipeline/config/composer/component-contract/1.json`,
  `config/composer/compositions/{researcher,health_institution,public}.json`,
  `templates/report_helpers.R`, `templates/audience_reports.R`,
  `tests/{test_pipeline,test_composition,test_composer_contracts}.py`,
  `tests/r_composition_smoke.R`, `README.md`, this record. No Snakefile, verifier,
  scientific-formula, series-contract, block-type or dependency change.
- Scope semantics implemented: optional `include_topics` (non-empty, unique, valid ids) and
  `exclude_topics` (unique, valid ids; default none). Omission keeps the historical eligible
  policy; lists may not overlap; unknown ids fail. Scope is applied before completeness so
  every dataset keeps a recorded decision: 49 of 56 rows in the narrowed run carry
  “Not in include_topics report scope”. `exclude_from_group_totals`, `sensitivity_exclude`
  and `classes_in_main_comparison` are untouched.
- Supported-topic boundary: `scripts/health_pipeline/config/pathogen_class.csv` is the
  catalogue. Identifiers absent from it are “not in supported topic catalogue”, not
  “nonexistent”; a catalogue topic with no snapshot dataset reports “no input dataset in this
  snapshot”; eligible-catalogue topics rejected by completeness/source rules keep their
  reasons; explicit configuration exclusions read “Excluded by exclude_topics report scope”.
  `include_topics` requests must all be fulfilled — otherwise analysis fails listing each
  missing topic and its recorded reason (no implicit partial success).
- Periods/completeness unchanged: the reporting window stays contiguous and annual;
  `reference_year` and `index_base_year` are still unioned into required source years
  (2022–2024 with defaults requires 2019). Empty required class/variant groups fail with the
  class, variant and scope in the message; no synthetic zeros.
- Identity: optional topic scope is hashed only when present; mandatory historical scope is
  unchanged. Topic list order is canonicalised (sorted) for identity and verification.
  Omission versus an empty include list produces different identities; omission on one side
  and a value on the other is a `scope_disagreement`, both directions covered by tests.
- Recipe v2 (`health-report/composition-recipe/2`) requires `topic` for
  `reference-comparison`; v1 remains readable and records `binding:"deterministic"`.
  Explicit bindings validate against saved `selection.csv`, use the saved result metric and
  its `inputs_json` count metrics, and never fall back. Provenance records `topic`,
  `binding:"explicit"`, checked instance id/status/identity; rendered subject equals the
  bound and checked subject. A failed explicit binding renders the honest unavailable panel
  and then fails the report/batch with a nonzero exit. Repeated reference blocks remain
  rejected. The three audience recipes now use v2 with `campylobacteriosis`, preserving
  instance ids, order and values.
- Real narrowed analysis (unchanged baseline, pinned image, `--out /baseline`), exact
  executed command:
  `docker --context rootless run --rm --pull never --user 0:0 --network none
  --cpus 2 --memory 4g --memory-swap 5g --pids-limit 512 -e PYTHONDONTWRITEBYTECODE=1
  -v /home/builder/composer-sandbox:/app:ro
  -v /home/builder/.local/state/composer-bootstrap/baseline-lJXSvvGc/output:/baseline:ro
  -v /home/builder/.local/state/composer-bootstrap/g1-scope-20261028T213031:/evidence:rw
  -w /app sha256:1ddf322f3f7b42394ce7fb1e5b1ab1a5023e2224399d1513c3b2c89d0dc521d8
  python scripts/health_pipeline/analyse.py --out /baseline
  --stakeholder /evidence/narrowed-config.json
  --classes /app/scripts/health_pipeline/config/pathogen_class.csv
  --dest /evidence/narrowed/reports/researcher/data`
  Exit 0. Requested `include_topics` = aids, campylobacteriosis, ehec, gonorrhea,
  hepatitis_a, hepatitis_b, shigellosis (7 included at disease level); 49 of 56 selection
  rows excluded with “Not in include_topics report scope”; series years 2019, 2021–2025.
  The four required groups are retained precisely as: `viral:main` and `viral:sensitivity`
  (members hepatitis_a, hepatitis_b; aids is included at disease level but excluded from
  group sums), and `bacterial:main` and `bacterial:sensitivity` (members
  campylobacteriosis, ehec, gonorrhea, shigellosis) — six diseases in the group sums.
  A rejected config excluding all viral topics exited 1 with “No eligible members for
  viral/main after report scope (include_topics=omitted, exclude_topics=[aids, covid19,
  hepatitis_a, hepatitis_b, hepatitis_c, hepatitis_e, hiv, influenza]); adjust topic scope
  or classes_in_main_comparison”.
- Evidence distinction: the narrowed-analysis **bundle** and its analysis evidence remain
  `~/.local/state/composer-bootstrap/g1-scope-20261028T213031/narrowed/reports/researcher/data`
  with `narrowed-analyse.log`, `rejected-analyse.log` and the demonstration configs; its
  first render (pre-visible-scope-rows) is superseded. The current render of that unchanged
  bundle is `g1-scope-final-20261028T214645/narrowed/report.html` (+ methods, provenance,
  data), where `narrowed-render.log`, verification and link logs are exit 0. The
  `g1-scope-batch-20261028T213858` batch is superseded by
  `g1-scope-final-20261028T214645/batch`; both older directories are retained unchanged.
  Final batch logs: `batch.log` exit 0, structural/quality/repro verification exit 0,
  three executed example logs exit 0, maintained suite 507 passed (31.52s) exit 0.
- **Scoped user review (narrowed methods output, accepted):** the user confirmed the
  six-disease group comparison is correct — seven topics are included in disease-level
  analysis while AIDS is excluded from group sums — and that the visible selection
  explanation distinguishes those meanings; reporting years 2021–2025 and reference year
  2019 are clearly separated. This is scoped user review of the inspected narrowed methods
  output only: it is not comprehensive browser/accessibility review, not a visual/layout
  acceptance and not scientific acceptance. G0/G1/R02 remain open.
- Remaining limits: canonical stakeholder configs keep the omitted-scope default; the
  narrowed run is a separate demonstration config. No per-block measure/period range, no
  time-trend block (Gate B2 not authorized), no browser/visual validation. G0/G1/R02 and
  challenge acceptance unchanged.


Review actual reading flow, distinct presets, graph/table clarity, evidence access, keyboard/focus/expansion, narrow layout and downloads. Scientific review is separately identified. A general PASS has only its supplied scope; do not invent browser/platform details. Screenshot comparison is not numerical/scientific acceptance.

### Candidate entry B2-SERIES-01: saved annual series contract and one researcher trend instance

- Base `29f44f4f772107d8e25880ea657cbcd7b66b9303` on `design/contracts`; candidate is
  **uncommitted** working-tree state and includes the bounded presentation fix below. No
  acceptance status changed; G0/G1/R02 remain open.
- Changed paths and current hashes:
  `M scripts/health_pipeline/composer_contracts.py 22928a268bce9f909713911622131335e28024365d98c313ceb02d3ee3db89ec`,
  `A scripts/health_pipeline/config/composer/series-contract/1.json d69f72739fe7776b5c958df0256492778dd05d3ff107272da7f72f7224c561d8`,
  `M scripts/health_pipeline/publish.py 438c2c2889711610cebf6e7fb71ff1953d0924bc79eb2c5ae5a0269a72a6fb00`,
  `M scripts/health_pipeline/templates/report_helpers.R 70eb7aa614d93b506468afc4c8183032cbd72020af439d23446c8a0df8909b14`,
  `A tests/test_composer_series.py 9e318a6a4ba622430096f4e4e05f5b76be002191d9e6869230b64edf1224d7d0`,
  `A tests/r_series_smoke.R 23b7bf0646a393ded6f3a78ca4cfabbdd797cfd9c88719869d0cc12597280073`,
  `M tests/r_composition_smoke.R 759ed43dc6da59584e67237a6837d6e30c5123b710e335789248938bdbc95560`,
  plus `README.md`, `docs/build/composer/BLOCK-CATALOGUE.md` (status/interface text only).
- Contract/recipe semantics: `health-report/series-component/1` is one self-contained
  document per instance (snapshot/scope, topic/measure/geography/dataset/source,
  requested/effective/missing years, ordered observations with `count_metric_id` and exact
  saved value strings, `series.csv` digest, implementation hashes, presentation unit).
  `series-trend` is a v2-only recipe entry requiring `topic` and `measure`, accepting one
  inclusive `years` range inside the reporting window (defaulting to it) and limited to one
  instance. v1 rejects the type; the repeated-reference restriction is unchanged. Validation
  re-reads saved rows/metrics and checks unique rows, one included dataset/source, metric
  subject/year/unit/value agreement, window containment, missing-period accounting and the
  artifact digest; it recalculates no count. Identity inputs are documented as
  snapshot+scope+method+binding (analytical), ordered saved rows/metrics/values (rows) and
  instance id/periods/artifact/settings (instance); recipe order is not an input. Full
  candidate identities are `bdbaf421…` / `c6ae14b0…` / `5f17e674…`; the narrowed bundle
  (different recorded topic scope) gives `ff340961…` / `4dd5235b…` / `f37d7635…`.
- Presentation defect diagnosed: the composed shell (`.composed-report`) does not inherit
  the `.dashboard .chart-panel>img` sizing rules, and `chart_image()` emits a bare `<img>`
  at intrinsic 1296×648 with no width/height attributes. The composed style had no image
  rule, so the PNG rendered at 1296 px inside a 980 px column (≈884 px inside block padding)
  and overflowed. Fix: wrap the series chart in `<figure class="series-figure">` and add two
  narrowly scoped rules — `width:100%;max-width:680px` for the figure and
  `width:100%;max-width:100%;height:auto;display:block` for its image. Source resolution is
  unchanged at 1296×648; no global image rule, overflow hiding or clipping was added, and
  observations, axes semantics and the zero baseline are unchanged.
- Follow-up wrapping correction from user visual review: the settings value
  `/baseline/snapshots/d0709708…` overflowed its content column. The markup is
  `<dd><code>…</code></dd>` in the composed settings panel; the composed shell is not
  `.dashboard`, and Quarto forces `code{white-space:pre-wrap}`, while inspector
  `.audit-row strong` values are flex items with default `min-width:auto`. The inherited
  `.provenance-list dd` wrap rule was insufficient in the viewed layout. Fix: one narrowly
  scoped composed rule sets `min-width:0;overflow-wrap:anywhere;white-space:normal` on
  provenance settings `code`, settings-table `code`, and audit-row `strong`/`code`. The
  displayed value and its explanation are unchanged, complete and copyable: no inserted
  spaces, ellipsis, clipping, font-size change or provenance-value change.
- Literal Markdown-style links: the published HTML was inspected rather than inferred from
  pasted text. Visible body text in the full and narrowed reports contains **0** `](`
  sequences; the only 7 matches are inside bundled Quarto/Bootstrap JavaScript strings.
  No link-generation defect was reproduced, so no link code was changed.
- Commands/exits (pinned image, rootless, `--network none`, bounded resources, repository
  and baseline read-only, fresh evidence directories):
  `tests/test_composer_series.py` + `tests/test_composition.py` 93 passed exit 0;
  `tests/r_series_smoke.R` exit 0; `tests/r_composition_smoke.R` exit 0; maintained suite
  559 passed (31.08s) exit 0; full and narrowed renders exit 0; both rendered-package
  verifiers exit 0; untrended three-audience batch exit 0; regression comparison against
  the previous batch exit 0; extracted saved-file inspection example exit 0.
- Fresh packages (the earlier `g2-series-20261028T225634` and
  `g2-series-sizing-20261028T232606` presentations are superseded for review but retained
  unchanged): `~/.local/state/composer-bootstrap/g2-series-wrapping-20261028T234411/render-full/report.html`
  and `.../render-narrowed/report.html`, each with `methods.html`, `provenance.json` and
  `data/`; regression batch under `.../batch-regression/reports/`. Logs (`maintained-suite.log`,
  renders, three verification logs) are in the same root.
- Verified in the published packages: exact values 6802/7645/6784/8360/8716 and the
  reference comparison (`+20.2%`, 7,253 → 8,716) are unchanged; figures carry the scoped
  class and rules; the image has no width/height/inline-style attributes; IDs, inspector,
  table and navigation targets are intact and unique; embedded provenance equals the
  sidecar; the series record's presentation digest equals the current `report_helpers.R`
  (`70eb7aa6…`). The untrended batch keeps its section order, reference instance identities
  and values. The build-time path is displayed in full with its unchanged explanation and no
  ellipsis, and the scoped wrap rule is present in both packages. Presentation identities
  were not relabelled: the documented identity inputs do
  not include render-code digests, so they remain unchanged while provenance records the new
  implementation hash.
- Visual review: **NOT REVIEWED**. No browser or headless tooling is installed and none was
  installed. Desktop and 375–390 px viewport overflow, horizontal page scrolling and
  keyboard/focus behaviour remain unverified; the markup/style assertion is not a browser
  or accessibility test.
- Remaining limits: gap, single-observation and malformed-row cases are labelled synthetic
  fixtures, not findings in the retained data; institutional/public trend variants remain
  unimplemented; no component was accepted and no ledger state changed.

### Development note G2-STYLE-01: series presentation style and implementation references

Uncommitted, tests only; no render, ledger or acceptance change in this checkpoint.

- Recovered from the interrupted session, and verified here: the series schema exposes an
  optional closed `presentation.style` plus optional `implementation.contracts`,
  `binding` and `schema` code references; `validate_series`/`check_series_block` path- and
  digest-check those roles, and `check_series_block` records an explicit style in the
  effective settings and trace.
- Bounded extension: a series-trend recipe entry accepts
  `presentation: {"style": "standard"|"compact"}`. Unknown nested keys, a non-object value
  and any other style are rejected by recipe validation and again by the builder, which
  returns a failed record rather than a default. Omitted style emits no style key, so the
  checked document, effective settings, trace and all three identities stay exactly as in
  the B2 candidate. Explicit style is emitted into the checked document and changes only
  the instance identity; analytical and rows identities are unchanged.
- `build_series_block` now records `contracts` (composer_contracts.py), `binding`
  (publish.py) and `schema` (series-contract/1.json) references beside `analysis` and
  `presentation`, in the existing code-reference shape. They are validated against the
  retained files and survive into the provenance `blocks` entry. Implementation
  references are not identity inputs: a document with those roles removed re-checks to the
  same identities.
- Renderer: `report_helpers.R` selects `series-figure--compact` at 2.4in (standard 3.6in)
  and adds a "Presentation style" inspector row only when a style is recorded. Saved
  values, gap segmentation, zero baseline, exact-value table, evidence and limitations are
  identical across styles; the existing 680px max-width, figure padding and long-identifier
  wrapping rules are unchanged.
- Historical evidence correspondence is preserved: the packages and hashes listed under
  B2-SERIES-01 above were rendered from the earlier code and are not re-labelled. Current
  working-tree hashes are `composer_contracts.py bb099147…`, `publish.py f225584b…`,
  `report_helpers.R 26228e6f…`, `series-contract/1.json 99c6afb4…`.
- Checks (pinned image, rootless, `--pull never --network none --cpus 3`, repository
  read-only): `python -m pytest tests/test_composer_series.py tests/test_composition.py -q
  `-p no:cacheprovider` 109 passed, exit 0; `Rscript tests/r_series_smoke.R` exit 0;
  `Rscript tests/r_composition_smoke.R` exit 0. Logs in
  `~/.local/state/composer-bootstrap/g2-style-<timestamp>/`.
- Not done here: no report render, no browser geometry review of the compact variant, no
  "Check rule" dropdown correction, and none of the other B2a–B2e blocks.

### Candidate entry B2-BATCH-01: saved-record composites and persistent audience recipes

- Base `29f44f4` on `design/contracts`; uncommitted working tree continuing B2-SERIES-01 and
  G2-STYLE-01. No acceptance or ledger state changed.
- Persistent recipes now wire the checked core per audience (one shared template, no
  duplicated calculations): researcher intro → series-trend (standard, campylobacteriosis,
  cases) → coverage-selection → sensitivity-comparison → reference-comparison →
  limitations → reproduction; health_institution intro → monitoring-overview →
  series-trend (compact) → reference-comparison → limitations → reproduction; public intro
  → reference-comparison (editorial magnitude variant) → series-trend (standard) →
  limitations → reproduction. All report 2021–2025; 2019 remains a separate comparison
  reference and is never drawn as part of the connected trend.
- The three new blocks are typed saved-record composites built in `publish.py`; no new JSON
  contract. `coverage-selection` counts datasets, topics and saved observations separately
  and takes “displayed topics” from the resolved recipe bindings, not from `series.csv`;
  `monitoring-overview` binds one row per included topic to its latest saved count metric
  and an optional saved reference/period change; `sensitivity-comparison` binds saved group
  totals and reference changes for main versus sensitivity and derives member differences
  from the saved member lists. Each carries analytical/instance identities, file digests,
  implementation references and fails closed.
- Provenance: reference-comparison evidence now records `contracts`/`binding`/`schema` code
  references (component-evidence schema extended additively); series and composite records
  do the same. Identity functions do not hash implementation, verified for both block kinds.
- Dropdown correction: scoped `min-width:0`/flex and full-width control rules on
  `.quality-controls` in methods.html; included in this render rather than a separate
  rebuild. Asserted structurally, not in a browser.
- Checks (pinned image, rootless, `--pull never --network none --cpus 3`, repository
  read-only): focused pytest 127 passed; maintained suite 593 passed; `r_series_smoke.R`
  exit 0; `r_composition_smoke.R` exit 0; three-audience batch exit 0; narrowed researcher
  render exit 0; package verifier 0 problems (typed blocks, digests, embedded provenance,
  unique ids, anchors, downloads); saved-file inspection exit 0. Logs in
  `~/.local/state/composer-bootstrap/g2-batch-<timestamp>/`.
- Verified in the rendered packages: exact series values 6,802/7,645/6,784/8,360/8,716 and
  `+20.2%` (7,253 → 8,716) unchanged; narrowed report shows 49 excluded dataset records
  against 7 included topics; institution uses the compact figure; public uses the editorial
  finding with the standard figure; no literal markdown links in report or methods bodies.
- User review recorded: the previously reviewed report passed the requested presentation
  checks and worked on a phone, except the “Check rule” dropdown, which this entry corrects.
  That review does not extend to the new blocks, other viewports, accessibility or
  cross-browser behaviour, and no browser tooling was installed.
- Still proposed with prerequisites: release/revision comparison (needs a second comparable
  snapshot), topic background (needs curated reviewed content), reusable extracts
  (per-block extract definition). No scientific acceptance.

### Feedback correction G2-BATCH-01a: monitoring bindings, scope semantics and presentation precision

- Monitoring root cause: the resolver collected every saved `reference_change` and
  `period_change` for a topic and treated more than one candidate as “no comparison”. It now
  resolves each type separately (more than one of the same type fails as ambiguous), derives
  the periods from the bound input metrics, and displays every available saved comparison.
  The institutional campylobacteriosis row binds `campylobacteriosis:reference_change`
  (+20.2%, 2019→2025) and `campylobacteriosis:period_change` (+28.1%, 2021→2025), matching the
  reference block for the common period. A topic with no saved comparison shows
  “No saved comparison”, not a plausible link.
- Context and membership: the intro derives included topics, group-sum members, individually
  displayed topics (from resolved composition instances) and group-summary presence from saved
  records; topics included in the analysis but excluded from group sums are named with that
  explanation (AIDS). Analytical selection is unchanged.
- Coverage: individually displayed topics and displayed group summaries (with member topics)
  are separate concepts; source-registry rows, all saved annual observations and
  window-contained observations are counted separately (72 total vs 60 in 2021–2025 for the
  full bundle), and per-dataset exclusion decisions with their reasons stay in a disclosure.
- Formatting: monitoring and sensitivity tables render 8,716 and +21.0% at presentation
  precision; exact saved strings and metric IDs remain in evidence and downloads. Identical
  main/sensitivity membership and results are stated as identical when true.
- Precision: reference blocks now request `digits: 1` in the resolved instance, so effective
  settings, trace and the rendered percentage agree (+20.2%). This changes the composed
  reference instance identity; historical packages keep `digits: 0` and are not relabelled.
  The contract-level default remains 0.
- Sensitivity evidence: a per-class disclosure lists reference/latest total metric IDs, the
  saved change metric ID, member metric IDs and the metrics.csv digest. No new contract.
- Copy: the institutional comparison no longer quotes the “changed most” question; the public
  series block is headed “Reported cases over time”, drops measure/saved-record jargon from
  reader-facing text and states that reported cases are not every infection. Absolute counts,
  periods, limitations and evidence are unchanged. “No source-count or scientific-result
  recalculation” replaces absolute “no calculation” claims.
- Sparklines: not implemented; the institutional overview remains a validated latest-values
  and comparisons table, and per-topic sparklines are recorded as deferred.
- Checks (pinned image, rootless, `--cpus 3`, repository read-only): focused pytest 234
  passed; maintained suite 596 passed; `r_series_smoke.R`, `r_composition_smoke.R` and
  `r_block_dispatch_smoke.R` exit 0; three-audience batch exit 0; narrowed render exit 0;
  package verifier 0 problems; saved-file inspection exit 0. Evidence:
  `~/.local/state/composer-bootstrap/g2-feedback-<timestamp>/`. Narrowed exclusions remain 49
  dataset records; exact series values and +20.2% are unchanged.
- Not verified: browser geometry/interaction at 390/320 px for the corrected blocks,
  accessibility, cross-browser behaviour, independent scientific or source review.

### Feedback correction G2-BATCH-01b: resolved display scope, endpoint evidence and monitoring identity domain

- Display scope: provenance composition now carries `display_scope` derived only from verified
  records — standalone topics (reference/series), monitoring-table topics, their union and the
  group summaries. Intro and coverage read it instead of re-deriving from `series.csv`.
  Institution names the monitoring-table topics; AIDS is described as included in the analysis
  but excluded from group sums, with display depending on the selected blocks (monitoring table
  in the institution, no finding in researcher/public). A monitoring-plus-series recipe with an
  overlapping topic is covered by test.
- Monitoring endpoints: every comparison carries its reference/latest saved count metric id,
  year, value and unit; a compact “Comparison endpoints and bound metrics” disclosure shows
  type, periods, counts, saved percentage and metric IDs. Endpoints are read from the bound
  metrics, never reconstructed from a rounded percentage, and influenza's large period change
  stays visible with its denominator.
- Identity audit: old and corrected monitoring records shared analytical and instance
  identities because the previous instance payload covered only topic/latest year/value; the
  `metrics.csv` digest covered file-level value changes but not which saved comparison was
  bound. Monitoring instance identity is now `monitoring-instance/2`, covering comparison type,
  metric id, endpoint periods and saved value. Analytical identity keeps its documented domain
  (snapshot + scope + method + file digests). Mutation tests show comparison value, binding or
  removal changes the instance identity, latest-value changes do too, presentation formatting
  changes neither, and recipe order changes no per-instance identity. Historical monitoring
  instance identities keep their v1 domain and are not reinterpreted.
- Sensitivity: the binding disclosure lists reference-year and latest-year member metric IDs
  from each saved total's own inputs; no IDs are synthesized, and the identical bacterial
  membership/result note is preserved.
- Public/title: the public intro leads with what the report actually shows and moves scope into
  a disclosure; the effective report title is derived from standalone displayed topics and
  recorded in composition provenance (`Campylobacteriosis: reported cases and saved
  comparisons`), leaving saved stakeholder metadata untouched.
- Commands: the en dash came from Pandoc smart typography inside audit rows; entry-point
  commands now render through entity-escaped code spans, so `snakemake --cores 2` stays literal
  and copyable. No historical core counts were changed.
- Checks: maintained suite 599 passed; focused pytest 138 passed; r_series, r_composition and
  r_block_dispatch smokes exit 0; three-audience batch exit 0; narrowed render exit 0; package
  verifier 0 problems; saved-file inspection OK (endpoint values equal the bound metrics).
- Evidence preservation incident: this round re-used the previous evidence directory and its
  batch/narrowed packages were overwritten in place before the mistake was noticed. Round-1
  logs and rendered claims remain in this record, but the files at
  `g2-feedback-20261029T093534` now contain round-2 output. A labelled copy of the current
  round-2 evidence is at `g2-feedback-r2-<timestamp>`; future rounds must use a fresh directory.
- Not verified: browser geometry/interaction at 390/320 px, accessibility, cross-browser,
  independent scientific or source review. Sparklines remain deferred.

### Methods closeout G2-BATCH-01c: composition-aware traces and limitation disclosures

- Methods traces now follow the resolved composition from provenance: the first verified
  standalone reference-comparison inside the displayed scope is traced (institution and public
  trace campylobacteriosis 2019→2025, 7,253→8,716, saved +20.2%, with bound metric IDs), the
  saved series records the row binding and gap semantics, and the monitoring table's
  reference/period baselines are explained. Viral/bacterial group results are no longer
  presented as traced findings for a recipe without a group block; the legacy group trace
  remains only on the explicit non-composed path.
- Denominator finding: the bundle really does retain 72 population metrics (persons), 72
  incidence metrics (per 100,000) with count+population inputs, and 72 population lineage
  rows; `analyse.py` validates the denominator. The previous generic sentence was replaced by
  wording that says these denominators support saved incidence metrics that this report does
  not display, and that displayed count changes are not population-adjusted. No rates added.
- Classification and completeness are explained from the implemented rules: supported
  analytical classification, source/measure/geography compatibility, required reference and
  window years, annual value preferred with 12-distinct-month aggregation, missing periods
  producing a recorded exclusion, configured source priority, and inclusion separate from
  group-sum membership. “Unclassified” is stated as outside the report's supported
  classification, not absence of disease or data. “Complete compatible series” is distinguished
  from complete ascertainment.
- Comparability: stated plainly that cross-year surveillance-method comparability has not been
  systematically evaluated and that matching source IDs, units or digests are not evidence of
  stable methods.
- Quality: the 50% missing-value threshold is identified as the configured `value_present`
  warning rule (checks.py, missing ≥ .5), distinct from classification/source-type exclusion
  reasons and from finding-level relevance.
- Reproduction: three labelled routes (saved-bundle rendering, original analysis, integrity/
  inspection example), effective recipe digest and pinned-environment record, and an explicit
  limitation that the uncommitted dirty worktree cannot be identified from a Git SHA alone and
  no source archive is published.
- Title: the institutional report now presents “Notifiable disease monitoring overview” with
  subtitle “Switzerland and Liechtenstein · Campylobacteriosis focus”, derived from resolved
  scope and recorded as `effective_title`/`effective_subtitle` in composition provenance;
  saved stakeholder metadata and digests are unchanged. Researcher/public titles are unchanged.
- Checks (pinned image, rootless, `--cpus 3`, repository read-only): focused pytest 139 passed;
  maintained suite 600 passed; r_series, r_composition and r_block_dispatch smokes exit 0;
  three-audience batch exit 0; narrowed render exit 0; package verifier 0 problems; published
  integrity/inspection example OK (all data digests match bundle.json; campylobacteriosis
  endpoints 7,253/2019→8,716/2025 and influenza 440→34,984 period endpoints retained).
- Evidence: a new, verified-empty directory `~/.local/state/composer-bootstrap/g2-methods-<timestamp>/`
  was used; the previous round-2 packages and the recorded overwrite incident are untouched.
- Not verified: browser geometry/interaction, accessibility, cross-browser, independent
  scientific or source review. Sparklines remain deferred.

### Final methods completion G2-BATCH-01d: displayed scope, block accounts and reproduction access

- Methods now open with the resolved `display_scope`: “N topics displayed in this report;
  M contributing to underlying group sums”, instead of leading with the underlying group
  comparison. Institution states its monitoring-table topics plus the standalone
  Campylobacteriosis view and that no group-summary block is displayed; researcher adds
  coverage and the main/sensitivity comparison; public relies on its comparison and annual
  view with underlying detail in disclosures.
- A “Methods for the displayed blocks” section is generated from verified composition
  instances with a small explicit dispatch (reference, series, coverage, sensitivity,
  monitoring). Each entry names the block, its saved inputs/binding method, links to the
  block's actual instance anchor, and states its limitation. Failed records get no narrative.
  Monitoring text records that sparklines are not implemented.
- Reference-selection invariant: only verified reference-comparison records whose subject is
  in the displayed scope are eligible; the enforced single-reference restriction keeps the
  choice unambiguous, and multiple references remain rejected by the existing test.
- Reproduction access now includes published artifacts: `reproduction/composition.json`
  (byte copy of the effective recipe) and `reproduction/reproduction.json` (entry point,
  recipe SHA-256, snapshot id, analysis-bundle file count, input/environment notes, source
  state). Recipe digest equals the provenance composition digest. Methods link both files and
  state what must be supplied separately (checkout, published bundle, original snapshot root);
  raw snapshot exports are not in the package. File-count wording now refers to the files
  listed in bundle.json plus the manifest, not a package-wide total.
- Checks (pinned image, rootless, `--cpus 3`, repository read-only): focused pytest 140
  passed; maintained suite 601 passed; r_series, r_composition and r_block_dispatch smokes
  exit 0; three-audience batch exit 0; narrowed render exit 0; verifier 0 problems
  (scope-aware methods opening, no group-count lead, displayed-block accounts, reproduction
  artifacts and recipe digest, typed blocks, embedded provenance, IDs/anchors/downloads);
  published inspection OK (bundle digests, recipe digest, title/subtitle).
- Evidence: new guarded directory `g2-methods2-<timestamp>` (pointer verified, empty before
  use); earlier packages and the overwrite incident remain untouched.
- Remaining blockers: no portable full replay of the original analysis from the package alone
  (snapshot exports and uncommitted source are not published); browser accessibility/geometry
  and independent scientific review remain open. Sparklines deferred.

### User acceptance and checkpoint readiness G2-ACCEPT-01

- User-reported acceptance: all seven review groups PASS for the candidate rendered at
  `~/.local/state/composer-bootstrap/g2-boundary-20261029T121827` — audience content and
  block composition; numeric spot checks; disclosures/navigation/methods links/downloads;
  findings-to-methods alignment; desktop and phone layout including quality filters;
  published reproduction records and recipes; narrowed-scope consistency. This is
  presentation/functional acceptance, not independent scientific or source review,
  accessibility certification, device/browser certification or full original-analysis replay.
- Source correspondence: provenance implementation references in all four accepted packages
  (three audiences and narrowed) match current files — publish.py `b46ce2b3…`,
  report_helpers.R `a5b124e8…`, composer_contracts.py `bb099147…`, series and component
  schemas unchanged from the accepted run; no relabelling or rerender was needed.
- Final test evidence for the accepted tree: maintained suite run once against the final
  Python tree (previous 601-passed run predated the last publish.py/test edits): 601 passed,
  exit 0, log `g2-checkpoint-20261029T125522/maintained-suite-final.log`; focused pytest 140
  passed; r_methods_boundary_smoke (six composition/reference boundary cases),
  r_series_smoke, r_composition_smoke and r_block_dispatch_smoke pass; batch/narrowed renders
  and package verifier 0 problems in the accepted evidence directory.
- Agent self-review (not independent): reference lookup by type/status/instance; no
  composed-to-legacy fallback for missing requested evidence; monitoring identity domain v2
  covers comparison bindings; no analytical-scope or saved-value changes; publication and
  reproduction artifacts consistent; new files included and whitespace clean. No substantive
  defect found.
- Remaining limitations: independent source/scientific review and accessibility/cross-browser
  certification remain open; cross-year comparability explicitly unevaluated; full
  original-analysis/snapshot replay not possible from the package alone; candidate source is
  uncommitted. Sparklines deferred.
- History preserved: the earlier evidence-overwrite incident (round 2 reusing the round-1
  directory) remains recorded above; the accepted packages and all prior logs are untouched.

### Candidate entry B2-COLLECTION-01: multi-topic annual series collection (author-run)

- Base `6bbca7d399b56644bde785af5aadd4323aa76943`; uncommitted development tree, so every
  render records `source_state: uncommitted`. No acceptance or ledger state changed.
- One new composite block, `series-collection`, over the existing single-topic builder. Each
  member is a separately checked `health-report/series-component/1` record produced by
  `build_series_block`; there is no second resolver, and `series-trend` stays a supported
  single-topic block. A recipe may not combine the two, and at most one collection is allowed.
- Recipe interface (closed): `{block, instance_id, topics: "eligible"|[{topic}], measure,
  years?, presentation?: {style, default_topic?}}`. `eligible` means the saved bundle's
  included topics in ascending topic order; an explicit list keeps author order. Unknown,
  excluded or otherwise unresolvable members fail the collection; there is no partial mode.
  Defaults: style `standard`, default topic = first resolved topic.
- Identity: members keep their own analytical/rows/instance identities (stable under
  reordering and independent of the default topic). A versioned
  `series-collection-identity/1` covers the collection instance, the ordered member
  references/statuses/instance identities, measure, effective periods, style and default
  topic — so reordering or changing the default changes only the collection identity.
  Member block ids are `sc-<10 hex>-<topic tail>` (≤40 chars, digest-stable, no manual map).
- Presentation: one native `<details>` panel per topic, default topic open, all panels
  available without JavaScript, each panel carrying its own heading, chart, exact-value
  table and inspector, reusing `series_body_html`. Panels are independent: no shared axis,
  overlay, normalisation or indexing. Collection inspector lists members, ids and identities.
- Scope/titles: `display_scope` now reports `collection_topics` and
  `collection_default_topic` separately from `standalone_topics` and `monitoring_topics`;
  `displayed_topics` is their union. Titles are collection-aware: researcher “Annual reported
  cases for N notifiable diseases”; institution keeps the monitoring overview with a
  default-topic focus subtitle; public leads with the default topic and labels exploration.
- Recipes: researcher (standard, campylobacteriosis open, coverage/sensitivity/reference),
  institution (compact, monitoring + reference), public (standard, exploration labelled,
  plain-language reference first).
- Checks (pinned image, rootless, `--pull never --network none --cpus 3`, repo and inputs
  read-only): maintained suite 629 passed; `r_collection_smoke.R`, `r_series_smoke.R`,
  `r_composition_smoke.R`, `r_block_dispatch_smoke.R`, `r_methods_boundary_smoke.R` exit 0;
  three-audience batch exit 0 (252 s); narrowed render exit 0 (81 s); package verifier 0
  problems (12/12/12/7 members, one open panel each, unique ids, anchors, member/metric
  binding, display scope, recipe bytes); link check 0 problems; saved-file inspection OK.
- Observed effect: `report.html` grows from ~1.0 MB to ~1.5 MB per 12-topic collection
  (12 embedded PNGs); methods pages are ~1.6 MB. No browser geometry, keyboard or phone
  review was performed — the CSS/summary assertions are structural only.
- Limits: single measure per collection; one collection per recipe; no sparklines,
  monitoring cross-links, configurator, PDF or second-snapshot use. Synthetic gap/zero/
  single-observation cases are fixtures, not findings in the retained data.

### User acceptance B2-COLLECTION-01a: time-trend collection PASS (user-reported)

- User statement: “It works — PASS.” Scope is the time-trend collection portion of the
  Phase B candidate as the user inspected it. No audience, device, viewport size, keyboard
  interaction or individual topic is claimed as checked beyond that statement.
- Reviewed evidence:
  `~/.local/state/composer-bootstrap/g2-phase-b-collection-20261029T134448Z-219075`
  (three audience packages + narrowed researcher case, logs, exits, verifier, checksums).
- Source correspondence: the packages were rendered from the uncommitted working tree on
  base `6bbca7d399b56644bde785af5aadd4323aa76943`, so every package records
  `source_state: uncommitted`. All 84 implementation references (contracts, binding,
  presentation, schema, analysis) and the presentation-helper digests match the current
  files; no reference is missing.
- Gap clarification: the plot preparation groups observations into segments and restarts a
  segment whenever the next year is not adjacent
  (`d$segment <- cumsum(c(TRUE, diff(d$year) > 1L))`, `report_helpers.R`), and the line
  layer draws solid segments only (`geom_line(aes(group = segment))`, no linetype). A missing
  year therefore produces a complete break, not a dashed bridge; `r_series_smoke.R` asserts
  `segment == c(1, 2, 2)` for years 2021/2023/2024 with 2022 missing. The earlier verbal
  description “dashed segment” was inaccurate and appears in no repository text. This PASS
  does not accept the synthetic gap behaviour; that remains fixture-only evidence.
- Verified test-evidence scope: maintained suite 629 passed (14:56), `r_collection_smoke.R`,
  `r_series_smoke.R`, `r_composition_smoke.R`, `r_block_dispatch_smoke.R` and
  `r_methods_boundary_smoke.R` exit 0, batch exit 0 (252 s), narrowed render exit 0 (81 s),
  package verifier 0 problems, link check 0 problems, saved-file inspection OK. Those runs
  cover the final code tree; the documentation-only edits that follow this entry were not
  part of that run and do not affect implementation digests.
- Remaining limitations: no independent source or scientific review; no accessibility,
  cross-browser, keyboard or phone certification; one measure per collection; one collection
  per recipe; no sparklines, monitoring cross-links, configurator, PDF or second-snapshot
  use. This entry records a scoped presentation/functional PASS only — it does not accept
  other Phase B review items or any requirement-ledger state.

### Development entry C1-MONITORING-LINKS: institutional monitoring rows open their series panel

- Base `eb23ed783a01de12e3fcd122cf6a645c19142b97` (`design/contracts`); uncommitted working tree,
  so every package records `source_state: uncommitted` (commit `eb23ed78` with uncommitted changes
  present). No acceptance or ledger state changed.
- Matching rule, presentation only: a row links only when a verified `series-collection` record in
  the same rendered provenance has a member with identical topic, equal measure, equal geography and
  equal saved dataset id, and that collection's effective years equal the monitoring reporting
  window. The href is the member's checked `instance_id`, which is the panel id the collection
  renderer emits from the same record; reader-facing labels, saved CSV order and panel order are
  never used. `publish.py`, contracts, schemas, saved values and every analytical/rows/instance
  identity are untouched — link targets are presentation metadata and enter no identity.
- Unlinked rows keep their plain text plus a short reason: this topic, no saved observation, another
  measure, another source, another period, ambiguous target, invalid target, collection not checked.
  A report with no collection renders the unchanged table (no link, no note, no script). A present
  but failed collection is reported as unchecked, never treated as absent, and the collection
  block's own failure propagation is unchanged.
- Reader behaviour: “View annual series” sits under the topic label in the existing topic cell. The
  same-page href works without JavaScript and reaches the native `<details>` summary; a `<noscript>`
  line states that the panel then needs opening. With scripting, a scoped IIFE (no library, guarded
  against double installation) opens the target panel if collapsed, focuses its summary, keeps the
  fragment, ignores modified clicks and leaves default navigation alone (no `preventDefault`). It
  validates that the target is a `series-panel` `details`, never closes a panel, never imposes an
  accordion, and does not touch unrelated links.
- Methods: the monitoring block account gains one sentence stating the link rule.
- Checks (pinned image, rootless, `--pull never --network none --cpus 3`, repository and inputs
  read-only, `PYTHONDONTWRITEBYTECODE=1`): focused pytest 163 passed; new
  `r_monitoring_links_smoke.R` exit 0 (exact topic identity, reordering, explicit subset,
  no-collection parity, measure/source/window mismatch, failed and ambiguous/invalid records,
  script scope); `r_series_smoke` (monitoring without collection stays unlinked),
  `r_collection_smoke`, `r_composition_smoke`, `r_block_dispatch_smoke`,
  `r_methods_boundary_smoke` exit 0; maintained suite 629 passed; three-audience batch exit 0
  (342 s); subset variant exit 0 (105 s: 3 links, 9 “No panel: this topic”); window variant exit 0
  (117 s: 0 links, 12 “No panel: another period”); `verify_c1.py` 0 problems over all five
  packages (12/12 institution links, every target a checked member with a rendered panel, one open
  panel = default topic, unique ids, resolvable anchors and `data/` targets, embedded provenance
  equal to the sidecar, implementation digests equal to the working tree).
- Unchanged content: researcher and public `report.html` bodies equal the Phase B package except the
  recorded commit, the render-code digest of the edited helper, the render timestamp and the
  container input-root mount name; institution monitoring values, row bindings, section ids and
  report size (1445 KB vs 1442 KB) are otherwise unchanged.
- Limits: no browser is available here (no chromium/chrome/firefox, no playwright/puppeteer, no
  installs), so click, focus, fragment and phone behaviour are structurally asserted only and need
  user review. The collection inspector's own member anchors still jump to a collapsed panel; that
  is pre-existing and deliberately unchanged by this slice.
- Evidence: `~/.local/state/composer-bootstrap/g2-phase-c1-monitoring-links-final-20261029T150158Z-236162`
  (supersedes the intermediate round `…-20261029T143119Z-229032`, kept unmodified). Logs, exits,
  `verify_c1.py`, the two variant recipes and `sha256sums.txt` are in that directory.
- Changed paths (uncommitted, unstaged): `scripts/health_pipeline/templates/report_helpers.R`
  (+165/−6: `read_composed_records`, `panel_link_plan`, `panel_link_cell`, `panel_link_script`,
  the monitoring row cell, scoped CSS and the methods sentence), `tests/r_monitoring_links_smoke.R`
  (new), `tests/r_series_smoke.R` (+4), `docs/build/composer/BLOCK-CATALOGUE.md` §6.6 row-navigation
  bullet. `git diff --check` exits 0.

### User acceptance C1-MONITORING-LINKS-a: browser checks PASS (user-reported)

- Automated/structural results stand exactly as recorded in the entry above and were not rerun for
  this note: focused pytest 163 passed, the six R smokes including `r_monitoring_links_smoke.R`,
  maintained suite 629 passed, the three-audience batch and both variants exit 0, `verify_c1.py`
  0 problems. Those checks cover markup, records and artifacts only.
- User-reported browser review: PASS. All requested checks were completed in Brave — a closed
  non-default topic opens with the panel's summary focused; closing it and activating the same
  monitoring link again opens and focuses again; panels stay independently usable; direct fragment
  arrival and reload open the target without programmatic focus theft; Enter and Space activate
  links with visible focus; modified clicks keep native behaviour; with JavaScript disabled the
  anchor remains usable and the expansion instruction is shown; at roughly 375 px the link stays
  readable and the table overflow stays contained; the subset and mismatched-window variants
  explain unlinked rows accurately. No failures were reported.
- Browser version was not supplied, so none is recorded. This is user-reported presentation and
  functional acceptance of the interaction only — not independent verification, accessibility or
  cross-browser/device certification, and not scientific review.
- Pre-existing limitation, out of scope for C1 and deliberately unchanged: the collection
  inspector's own member anchors and the methods-page topic links still jump to a collapsed panel;
  the enhancement handles monitoring-row links only.
- Evidence note: this closeout is a documentation edit made after the final render round. The
  packages in `g2-phase-c1-monitoring-links-final-20261029T150158Z-236162` and their recorded
  digests predate this text and are retained unchanged; their `sha256sums.txt` does not cover this
  document, and no claim is made that it does.
- Browser review complete. Commit authorization for the five-path C1 scope is still pending.

### Development entry C2a-WORKBENCH: same-audience recipe workbench (author-run)

- Base `d2b811b545e055c27cd1381229eb98b46196f05a` (`design/contracts`); uncommitted working tree,
  so previews record commit `d2b811b` with uncommitted changes present.
- Implemented journey: open a maintained recipe or a published `reproduction/composition.json`
  → save a workspace copy (byte-identical while unedited) → reorder an existing block → set a
  supported presentation option → preview the *saved* recipe → reopen it unchanged → replay the
  printed CLI command. Same-audience only: the recipe audience must equal the bundle's
  stakeholder, and `publish.render` keeps enforcing that.
- Preview/publication boundary, established from the code rather than the function names:
  `publish.publish_evidence` only byte-copies the saved bundle into `<report>/data` and verifies
  digests; it writes no accepted-output pointer, no `release.json` and no catalogue entry. A
  preview is therefore a render inside `<workspace>/previews/<UTC>-<pid>-<12 hex>/` plus one
  marker recorded in three places: provenance (`preview.status`/`accepted_output`/`notice`),
  `preview.json` (`status`, `published: false`) and a single
  `<p class="composed-preview" role="note">` on the page. Default renders carry neither marker
  nor banner, and the CLI replay is an ordinary render.
- Identity effects: reordering and `default_topic` edits change the collection presentation
  identity only; member analytical/rows/instance identities, saved values and bindings are
  unchanged — asserted in unit tests and confirmed on the preview/replay provenances.
- Safety: every write stays inside the named workspace; a workspace is never reused; copies and
  save-as use `O_EXCL` plus a same-directory `os.link`; edits replace only the workspace's own
  file, atomically; targets are resolved with `realpath` and refused outside the workspace; a
  symlinked `previews/` directory is refused; preview directories are unique by time, pid and a
  random token; replay commands are produced as an argv list plus a `shlex.quote`d string and
  never run through a shell.
- Checks (pinned image, rootless, `--pull never --network none --cpus 3`, repository and inputs
  read-only): focused pytest 117 passed; `tests/test_composer_workspace.py` 27 passed;
  `tests/test_composer_ui.py` 5 passed; maintained suite 661 passed;
  `r_composer_preview_smoke.R` exit 0 (banner only with a preview marker, absent by default and
  for a non-preview status); `r_composition_smoke`, `r_collection_smoke` and
  `r_monitoring_links_smoke` exit 0; real preview from the retained researcher bundle exit 0
  (83 s); CLI replay of the same saved recipe exit 0 (85 s); `verify_c2a.py` 0 problems (recipe
  digest, effective recipe, instance identities, collection identity and member ids, banner
  count 1 vs 0, source recipe unchanged, no release/accepted artefacts, anchors and `data/`
  targets resolve in both reports).
- Evidence: `~/.local/state/composer-bootstrap/g2-phase-c2a-workbench-20261029T163445Z-257128`
  (supersedes the first round `…-20261029T163335Z-256855`, kept unmodified: it stopped on a
  driver bug that passed a path where `build_provenance` expects a `{path, sha256}` record).
  Preview package: `…/workbench/previews/20261029T163459Z-1-c4241ecf89ec/` (`report.html`,
  `methods.html`, `provenance.json`, `preview.json`, `composition.json`); replay:
  `…/replay/report.html` with `provenance.json`, `methods.html`, `data/`, `reproduction/`.
- Edited recipe: `…/workbench/researcher-trial.json` — `block-coverage-selection` moved below
  `block-sensitivity-comparison` and the collection's `default_topic` set to `influenza`
  (a checked member of the retained bundle).
- Not reviewed: browser/Marimo interaction, page focus, narrow layout and the live UI run. No
  browser or Marimo session exists in this environment; the UI cells are exercised only by
  AST-level submission tests, and the HTML banner only by a structural R smoke. The preview
  banner appears on `report.html`; the preview's `methods.html` carries no banner (its status is
  in provenance and `preview.json`).
- Changed paths: `scripts/health_pipeline/publish.py` (preview marker; `validate_composition`
  split out of `load_composition`), `scripts/health_pipeline/templates/report_helpers.R` (gated
  banner and CSS), new `scripts/health_pipeline/composer_workspace.py`,
  new `src/composer_ui.py`, new `tests/test_composer_workspace.py`,
  new `tests/test_composer_ui.py`, new `tests/r_composer_preview_smoke.R`,
  plus the catalogue wording above.
- Human journey ready for review, not claimed as accepted. Starting point:
  `marimo edit src/composer_ui.py` from the repository root, with a retained bundle available
  locally; then: inspect the researcher recipe → create a workspace under `results/workbench/`
  → copy `researcher.json` as `researcher-trial.json` → move `block-coverage-selection` down →
  set the collection `default_topic` to `influenza` → **Preview** → expect exactly one
  "Preview — not an accepted publication." banner, the Influenza panel open, and a preview
  directory holding `composition.json`/`provenance.json`/`preview.json` → reopen the recipe and
  confirm the order and topic persisted → run the printed replay command and confirm the same
  order and open panel without a preview banner.
- **Superseded by C2a-SITE-01:** the Marimo page is not the product frontend. `src/composer_ui.py`
  and `tests/test_composer_ui.py` were removed from the working tree and preserved
  byte-identically at `~/.local/state/composer-bootstrap/c2a-supersession-20261029T172320Z-268100`
  (`composer_ui.py ea0259ba…`, `test_composer_ui.py 30fe5c7b…`, with `hashes.txt` and
  `pointer.json`). The workspace service described above is unchanged and is now called by the
  custom website instead. The failure that motivated the change was the Marimo launch itself:
  `c2a-review-20261029T170142Z-263986/marimo-check.log` reported two `critical
  [multiple-definitions]` diagnostics, and the review-live launch bound `0.0.0.0:2719`
  (`c2a-review-live-20261029T170701Z-265868/startup.log`).

## Candidate entry C2a-SITE-01: custom local website (author-run, live review pending)

- Direction: a custom local HTML/CSS/JavaScript website, **no Marimo composer**. The journey is
  choose inputs → explicit **Generate** → bounded background render → polled status → the
  completed report embedded on the same page. The shared composition validator, workspace
  service, renderer, provenance and CLI replay are reused; there is no static-report selector.
- Changed paths and current hashes (uncommitted, on base `d2b811b…`):
  `M scripts/health_pipeline/publish.py 67c2a3ea…` (`PREVIEW_NOTICE`, `preview=True` record,
  `validate_composition` split out of `load_composition`),
  `M scripts/health_pipeline/templates/report_helpers.R 7436f91c…` (gated preview banner + one
  scoped CSS rule), `A scripts/health_pipeline/composer_workspace.py 11e8d197…`,
  `A src/composer_site.py b18a9163…` (after the log-redaction fix below; `e805ad5f…` was the
  snapshot version), `A src/composer_web/index.html 808c116a…`,
  `A src/composer_web/app.css 0edfe597…`, `A src/composer_web/app.js 4627d886…`,
  `A tests/test_composer_site.py b62e2954…`, `A tests/test_composer_workspace.py 6fa806a4…`,
  `A tests/r_composer_preview_smoke.R e4522618…`, plus the catalogue and this record.
  Full hashes are also in `current-source-sha256.txt` of the recovery snapshot. Against it, this
  slice changed only `src/composer_site.py` and `tests/test_composer_site.py` (the log-redaction
  fix), plus this record and the catalogue; `composer_workspace.py 11e8d197…`, the three web
  assets, `publish.py 67c2a3ea…`, `report_helpers.R 7436f91c…`,
  `tests/test_composer_workspace.py 6fa806a4…` and `tests/r_composer_preview_smoke.R e4522618…`
  are unchanged.
- Server protections actually implemented (`src/composer_site.py`): one per-run random token,
  written to `<work-root>/access-token.txt` with mode 0600 and never logged; the only entry is
  `GET /?token=…`, which answers 302 with an `HttpOnly; SameSite=Strict; Path=/` cookie whose
  value is the token's SHA-256 prefix; every page, asset, API and artifact request needs that
  cookie, compared with `hmac.compare_digest`; the request log redacts the query token
  (`token=[redacted]`), because the entry URL is the one place the credential appears in a URL.
  Mutations additionally need a matching `X-Composer-Action` header and, when `Origin` is
  present, agreement with the request `Host` (no preflight is answered). GET never mutates.
  Bodies must be `application/json`, ≤64 KiB, and may not carry unknown fields. The bind is
  loopback-only (`main` refuses any other host);
  `Host` must be in the allowlist for the actually bound port. Workspace names, recipe names,
  job ids and artifact paths are all validated and resolved with `realpath` and refused outside
  their root; symlinked workspaces, preview directories, job directories and artifact targets
  are refused; only known content types are served.
- Job semantics: submission takes the single active-job reservation, copies the saved recipe
  into `<workspace>/.jobs/<job-id>/composition.json`, hashes **that copy** and re-validates it,
  then records the digest, the snapshot's relative path and the quoted replay command before
  the worker starts. A later edit of the saved recipe therefore cannot change the job, its
  rendered recipe or its replay. Any exception during submission releases the reservation; the
  worker always clears it and its thread entry in `finally`. A failed or interrupted render
  leaves earlier previews untouched; on restart, `queued`/`running` records are marked
  `interrupted` with "no report was produced". Internal paths (`workspace`, `snapshot`,
  `preview_dir`) stay server-side; the browser receives a job id and a report URL only.
- Actual post-crash result, not commentary: the first fresh run in the pinned image
  (`focused-1.log`) was **16 failed, 29 passed, exit 1**, and every failure was HTTP 401 — the
  test client never presented the session cookie that the server requires. The previously
  visible `preview_dir` fix was therefore insufficient: it made completed artifacts locatable
  server-side, but the HTTP suite still could not reach a single route. Repair, test-side only:
  the harness now performs the documented token exchange and sends the issued cookie, and new
  tests assert the session is required, that a wrong token or forged cookie is refused, that the
  cookie is HttpOnly/SameSite=Strict, and that a non-loopback bind is refused. No production
  protection was weakened to make tests pass.
- New coverage added with that repair: rendered-recipe equality (the renderer reads the job's
  preview copy, byte-identical to the snapshot, and the recorded digest is those bytes),
  failed-submission reservation release followed by a successful submission, a failed second
  generation leaving the first report byte-identical and served, no leftover render worker, and
  a no-Marimo assertion over the site sources, the web assets and the process command line.
- Checks (pinned image `sha256:1ddf322f3f7b…`, rootless, `--pull never`, `--network none`,
  `--user 0:0 --cpus 3 --memory 4g --memory-swap 5g --pids-limit 512`, repository and baseline
  read-only, `PYTHONDONTWRITEBYTECODE=1`), all in
  `~/.local/state/composer-bootstrap/c2a-site-20261029T181351Z-2034`:
  `focused-1.log` 16 failed/29 passed exit 1 (recorded, pre-repair);
  `focused-4.log` **54 passed, exit 0**; `r-smokes.log` seven smokes exit 0
  (`r_composer_preview`, `r_composition`, `r_series`, `r_collection`, `r_block_dispatch`,
  `r_monitoring_links`, `r_methods_boundary`); `maintained-suite.log` **683 passed (52.85s),
  exit 0**; `live-driver-3.log` **38 checks, 0 failures, exit 0**.
- One real generation through the website, then CLI replay of the *job's own snapshot*
  (`live-3/`): workspace `live-review`, `researcher-trial.json` copied from the maintained
  researcher recipe (byte-identical), `block-coverage-selection` moved below
  `block-sensitivity-comparison`, collection `default_topic` set to `influenza`, Generate, job
  `20261029T182651Z-b05414043a`, status `succeeded`. Verified from served bytes: the job digest
  equals the snapshot digest equals the saved recipe digest at submit time
  (`efb388fb…`); the served `report.html` (`6ea98bf7…`) is byte-identical before and after a
  further edit of the saved recipe (`efb388fb…` → changed, snapshot unchanged); provenance
  records `preview.status=preview`, `accepted_output=false` and the snapshot digest as
  `composition.recipe_sha256`; the page carries the notice exactly once; section order is
  `intro-0001 → researcher-series-collection → block-sensitivity-comparison →
  block-coverage-selection → block-reference-comparison → limitations-0001 → reproduction-0001`
  and the open panel is `sc-59557e6636-influenza`. The replay ran the exact printed argv
  (`replay-command.txt`, `replay.log`, exit 0) and produced `replay-report.html` (`1abe3c46…`)
  with the same recipe digest, the same `effective_recipe`, the same seven checked instances with
  equal `contract_instance_id`/`contract_status`/`instance_identity`, the same section order and
  the same single open panel, and **no** preview marker or banner.
- Two driver-probe defects were found and fixed in the evidence driver only (not in the
  product): the section-id regex assumed `<section id=…>` instead of
  `<section class="composed-block" id=…>`, and the navigation probe required `<nav
  class="composed-nav">` without attributes. Runs `live` and `live-2` are retained unchanged;
  `live-3` is the complete run.
- Not reviewed: no browser was used here. Layout at desktop and narrow widths, keyboard/focus
  order, the embedded-report behaviour in an iframe, the polling status text and the download
  links are asserted structurally only. Live user review is the next step and is not a PASS.
  G0/G1/R02 and challenge acceptance remain unchanged; nothing was committed, tagged, staged or
  published, and no ledger was touched.

### Live review service C2a-SITE-01a: started, awaiting user review

- Container `composer-site-review` from the pinned image (`--pull never`, no build, no install,
  no cleanup of other images/containers). Bounds: `--user 0:0 --cpus 3 --memory 4g
  --memory-swap 5g --pids-limit 512`; repository read-only at `/app`, retained baseline
  read-only at `/inputs`, one writable work root at `/review`; no Docker socket, no privileged
  mode, no host networking. Bridge networking with exactly **one** loopback-published port
  (`127.0.0.1:2719 -> 2719/tcp`); bridge egress is not claimed to be isolated.
- The product still binds loopback only (its guard and its test are unchanged). A published
  container port arrives on the container's own interface, and a probe confirmed that a
  container process bound to `127.0.0.1` is **not** reachable through the published port, so the
  review harness adds one stdlib TCP forwarder (`review/forwarder.py`) bound to the container's
  own address (`172.17.0.2:2719`) that forwards to `127.0.0.1:2719`. The container process list
  is exactly the site and this forwarder — no Marimo process.
- Verified against the running instance from WSL: `/` and `/api/catalogue` answer 401 without
  the session; `GET /?token=…` answers 302 `Location: /` with
  `Set-Cookie: composer_session=…; Path=/; HttpOnly; SameSite=Strict`; the page then returns
  200 (3,515 bytes, digest `808c116a…`, i.e. the shipped `index.html`); `Host: evil.example`
  returns 400; the catalogue lists all three recipes and all three saved bundles as available;
  the token file is 32 characters at mode 600 inside the work root.
- One startup generation through the running instance (default researcher recipe, no edits):
  workspace `startup-check`, job `20261029T183306Z-6eec087d85`, `succeeded` after 83 s,
  `report.html` 1,553,942 bytes with exactly one preview banner. It is left in place as the
  instance's own record.
- Host and access path: same-machine WSL2 verified (`WSL_DISTRO_NAME=ComposerSandbox`, kernel
  `6.18.54.1-microsoft-standard-WSL2`), WSL-side listener `127.0.0.1:2719` owned by
  `rootlesskit`. This is not an SSH or remote-host setup. Windows-side localhost forwarding
  could **not** be exercised from inside this distro: `/etc/wsl.conf` sets
  `interop.enabled=false` and `automount.enabled=false`, so no Windows binary is runnable here
  and no Windows filesystem is mounted. The Windows check is therefore a user action, stated as
  a check and not as a result.
- Access: `http://localhost:2719/?token=<contents of
  ~/.local/state/composer-bootstrap/c2a-site-20261029T181351Z-2034/review/work/access-token.txt>`.
  The `Host` header must be `localhost` or `127.0.0.1`; other host names are refused by design.
- **Token handling fix found during this live check:** the service log had been echoing the full
  entry URL, i.e. the token, into stderr (`GET /?token=…`). It now logs
  `GET /?token=[redacted] HTTP/1.1` (verified on the running instance after a restart), and
  `test_access_token_is_redacted_from_the_service_log` asserts the token never appears in the log
  while the entry request still answers 302. The token is per run: restarting the service issues
  a new one, so the file (not a memorised URL) is the source of truth.
- After that fix: focused service/HTTP tests **55 passed, exit 0** (`focused-5.log`) and the
  maintained suite was re-run rather than reusing the earlier green run — **684 passed
  (52.99s), exit 0** (`maintained-suite-2.log`).

## Candidate entry C2a-SITE-02: preset-first journey, section inclusion and the selector repair

- Scope: the user's scoped review of C2a-SITE-01 — generation works; input/workspace setup is
  unintuitive; the default-open-disease selector is defective. Direction is unchanged: custom
  local HTML/CSS/JavaScript, no Marimo. This candidate is **uncommitted** on `d2b811b…`.
- **Selector defect: reproduced before repair, not inferred.** Driving the shipped API in the
  pinned image (`repro-topic-selector.log`, `topic-selector-repro.json`) showed the exact
  sequence: opening a recipe returned 12 `topic_choices`; after `set-default-topic` the very same
  response returned `topic_choices: null`, while the saved file did contain the chosen disease and
  a reopen listed the diseases again. Root cause: `Site.edit_recipe` rebuilt the editor payload
  with `topics=None`, so every editor rebuild after any edit (including a reorder) dropped the
  option list, and the frontend's `block.topic_choices || []` then rendered only its placeholder —
  "diseases briefly appear ... then the list disappears". The data and the saved value were never
  wrong; only the response was. Repair: the editor document is now built in one place
  (`Site.editor_document`) from the resolved bundle, every mutation returns that document, and
  `test_default_topic_selection_survives_save_and_reopen` pins the whole sequence
  (choose → save → reopen → reorder → style change keeps the list).
- Journey now implemented: four mutually exclusive cards (Researcher, Health institution, Public,
  Custom) as an accessible radiogroup (roving `tabindex`, arrow/Home/End keys, `aria-checked`,
  a visible “✓ Selected” mark in addition to colour, decorative emoji marked
  `aria-hidden`). A standard choice resolves **its own** maintained recipe and its own saved
  bundle; there is no bundle selector, so a mismatched pair cannot be expressed and nothing falls
  back to another dataset. Selecting a standard collapses the editor and leaves *Generate
  preview* as the primary action; nothing renders on load or on selection.
- Editing model: one managed copy per audience under `<work-root>/drafts/<audience>/` —
  `recipe.json` (a byte copy of the maintained recipe) plus `editor.json` (schema, audience,
  exclusions, monotonic revision). The composition schema is unchanged; exclusion is editor state
  held **beside** the recipe, and the renderer receives the recipe minus excluded sections,
  re-validated by `publish.validate_composition`. Opening the editor writes nothing; the first
  *accepted* change creates the copy: the intended edit is validated against the maintained
  recipe before any file is written, so a rejected action leaves no empty copy behind),
  and only then does the Custom card become selected. Switching back to a standard reads the
  maintained recipe untouched and leaves the copy on disk; choosing Custom again resumes it.
- Section control: every saved section is listed with an Include checkbox, up/down controls,
  `Chart style` and, where supported, `Disease expanded when the report opens` with the help
  “Other included diseases remain available in the report.” Unchecking hides the section from the
  rendered recipe but keeps it — with its settings, instance id and position — in the editor and
  in `recipe.json`, so restoring it is exact. `limitations` and `reproduction` are required, with
  the reason shown next to the disabled checkbox; the last included section cannot be removed;
  the shared loader remains the final authority and its message is surfaced. Labels and
  descriptions are a frontend map (`BLOCK_LABELS`) over stable ids; unknown ids fall back to the
  id, and no block type is invented.
- Simplification: the manual workspace/copy form is gone. The page shows one compact source line
  (reporting period, reference year, geography, included disease count, saved snapshot prefix);
  paths, managed copies and earlier reports moved into “Data and saved reports”, which is the only
  panel that loads on toggle and only reads (`GET /api/saved`).
- API: `GET /api/presets`, `GET /api/editor?preset=&mode=`, `POST /api/draft`,
  `POST /api/edit` (moves, include/exclude, style, default disease), `POST /api/generate`
  (`mode: standard|custom`), `GET /api/saved`, the existing job/artifact routes. Preserved and
  re-tested: per-run token → HttpOnly/SameSite session, Host allowlist, action-header + Origin
  agreement, JSON-only bodies, loopback-only bind, realpath containment, symlink refusal, one
  active render, immutable per-job snapshot, preview provenance, failure preservation, bounded
  workers, CLI replay. No dependency, framework, upload, PDF, profile registry, reference-topic
  rebinding, analysis or acquisition change.
- Paths and hashes: `src/composer_site.py 318fac66…`, `src/composer_web/index.html 64111bf8…`,
  `src/composer_web/app.js 3f190d80…`, `src/composer_web/app.css 5a5f9201…`,
  `scripts/health_pipeline/composer_workspace.py 566d1c7d…` (`render_preview` split out of
  `preview`, draft service, pure `edit_plan` + `commit_edit`),
  `tests/test_composer_site.py 48facac4…`, `tests/test_composer_drafts.py de93aef9…`, plus this
  record. `publish.py 67c2a3ea…` and `report_helpers.R 7436f91c…` are untouched by this
  candidate.
- Checks (pinned image, rootless, `--pull never --network none`, `--user 0:0 --cpus 3
  --memory 4g --memory-swap 5g --pids-limit 512`, repository and baseline read-only,
  `PYTHONDONTWRITEBYTECODE=1`), in
  `~/.local/state/composer-bootstrap/c2a-site-20261029T181351Z-2034`:
  `focused-rev1.log` 70 passed / 4 failed exit 1 (first pass of the new suite; the four were test
  fixtures, not product defects — one included topic, a mismatched fixture disease and a
  double-exclusion bobble in `edit_plan`), `focused-rev2.log` **74 passed exit 0**,
  `maintained-suite-rev1.log` **703 passed (61.48s) exit 0**, `r-smokes-rev.log` seven R smokes
  exit 0, `live-rev-driver.log` **50 checks, 0 failures, exit 0**. After the last compatibility
  change (pre-revision job records shown with their historical audience) both were re-run on the
  final tree rather than reused: `focused-rev3.log` **74 passed exit 0**,
  `maintained-suite-rev2.log` **703 passed (58.28s) exit 0**.
- Live journey with the real renderer (`live-rev/`): presets resolve researcher to its maintained
  recipe and report 12 included diseases and reference 2019; the standard editor lists seven
  sections with the required flags; the disease was switched to `influenza`, the rebuilt editor
  still listed all 12, the copy became Custom at revision 1, reopening kept both, and the saved
  copy really stores `default_topic: influenza`; `block-sensitivity-comparison` was excluded and
  `block-coverage-selection` moved below the reference block; excluding `limitations-0001` was
  refused with the required-section explanation; job `20261029T193706Z-c2ad5b9144` rendered the changed composition
  (`succeeded`), its digest equals the editor's effective digest, the rendered recipe omits the
  excluded section, the page shows exactly one preview notice, the section order follows the
  editor and the open panel is `sc-59557e6636-influenza`; the maintained recipe's bytes were
  unchanged afterwards; a later edit left the snapshot and the served report byte-identical; the
  printed replay rendered that same snapshot (exit 0) with the same effective recipe, the same
  recipe digest, identical `composition.instances`, identical section order and the same single
  open panel, and no preview marker.
- Not verified: no browser was used here. Keyboard operation of the radiogroup, focus order,
  narrow layout, the iframe and the visible selected indicator are asserted structurally only.
  Wording uses “disease” because these retained bundles' topics are notifiable diseases; a
  generic-topic bundle would need the neutral “topic” wording and is not supported here.
  Pre-revision job records (from C2a-SITE-01) still list without a stored preset; the panel
  falls back to their historical audience. G0/G1/R02 and challenge acceptance unchanged.
- Handover: the review container was recreated on this candidate, which issues a **new per-run
  token**; the previous chat-exposed token is dead. The replacement is not printed in chat or in
  any log (the access log redacts it); it is readable only from the token file named in the
  startup instructions. The container was recreated rather than only restarted because its log
  history still held two request lines from the run *before* the redaction fix (dead tokens from
  earlier runs); the new container's log holds only the placeholder line and `token=[redacted]`.
  Verified after recreation: 401 without the session, 302 on the token exchange, page 200 with
  the session, four presets served, token file mode 600, zero occurrences of the current token in
  the service log.

## Candidate entry C2a-SITE-03: audience customization, disease subsets and honest history (Round A)

- Scope: the product owner's model change, Round A only (Round B stays a plan). Decisions taken
  as given: the Custom card stays visible but disabled with “Build from the block library —
  coming in the next revision.”; chart height stays under collapsed advanced options; `topics:
  "eligible"` only when it reproduces the default resolved selection *and* order; reset in place
  with confirmation; older history is never falsely classified; one bundle per future custom
  composition; and **no** `composition.origin` or other composition/provenance field in this
  round. No composition schema, maintained recipe, renderer contract or analytical calculation
  was touched.
- Audience model: editing an audience keeps that audience selected. “Customized” is computed, not
  asserted: the server compares the editor's pending composition with the maintained recipe
  (blocks, order, inclusion, topics and order, expanded disease, chart height) and reports
  `customized`. Opening the editor or having a saved copy does not set it; returning every setting
  to the default clears it. Reset rewrites the copy in place from the maintained bytes, clears
  exclusions and pending selection, bumps the revision, and never touches jobs, snapshots or
  reports. The old rule that any edit selects Custom is gone.
- Draft versus renderable recipe (the central correction): `editor.json` moves to
  `health-report/composer-draft/2` with an additive `selection` map
  (`{instance_id: {topics, default_topic}}`) holding the *pending* disease choice. `recipe.json`
  stays the last accepted, always-renderable composition. An empty selection in an enabled block
  is therefore **customized and invalid**: the editor shows the pending empty list (no stale
  disease), `ready` is false, the page shows the blocking sentence, and Generate refuses with
  “Select at least one disease, or turn off ‘Annual trends by disease’.” — never rendering the
  previous valid selection. A successful Generate commits the pending choice into the recipe
  (normalising a full set in bundle order back to `"eligible"`), so the saved copy and the render
  agree. Both concepts are exposed: `customized`/`differences` for “differs from default” and
  `ready`/`blocking_reason` for “ready to generate”.
- Disease checkboxes: one checkbox per saved bundle topic, Select all / Clear over the same list,
  deterministic order (bundle order for Select all, existing order preserved for the rest), and an
  expanded-disease select populated only from checked diseases. Unchecking the open disease moves
  the choice to the first remaining checked disease and returns a structured note; the page
  announces it in a live region and restores focus to the same control after the rebuild, so
  focus is not stolen. With nothing checked the control is disabled and the generation error is
  shown. Excluding the whole section keeps the pending selection; re-enabling restores and
  re-validates it. Select all does not claim to restore defaults: the badge stays while chart
  height, expanded disease, inclusion or order still differ.
- Chart height: the control is now inside a collapsed “Advanced display options” with the label
  “Chart height”, choices Standard / Compact, and help stating that only the figure height changes
  (values, axes, wording and analytical meaning unchanged). The client sends no edit when the
  displayed value is unchanged, existing recipes that record a style keep loading, and replay is
  unchanged. Inspected effect (unchanged from before): figure height 3.6 in → 2.4 in, a margin
  class, and one inspector row; style enters the block instance identity only.
- History: a new job stores site-job metadata `classification` (`default`/`customized`) and
  `classification_basis` (the maintained recipe digest used for that comparison), computed at
  generation time and separate from every scientific identity. History rows show audience,
  classification, time, recipe digest and a snapshot summary read from the job's own snapshot.
  Records written before this round have no classification and are shown as “Customization status
  not recorded” (a recorded `mode: standard` is labelled “Default (standard composition)” because
  that render path used the maintained recipe); nothing is compared with today's default, nothing
  is backfilled, and resetting or regenerating never deletes or replaces an entry.
- Paths and hashes: `scripts/health_pipeline/composer_workspace.py 69364eb7…` (draft/2, pending
  selection, `plan_selection`/`commit_selection`/`commit_pending`, `reset_draft`),
  `src/composer_site.py 5078069c…` (presets with per-audience state, editor document with
  readiness/differences, `/api/reset`, derived render mode, job classification, snapshot
  summaries), `src/composer_web/index.html 9680d743…`, `src/composer_web/app.js 081455e1…`,
  `src/composer_web/app.css da359698…`, `tests/test_composer_site.py 425dd0df…`,
  `tests/test_composer_drafts.py 38530cc6…`, plus the catalogue and this record.
  `publish.py`, `report_helpers.R` and every maintained recipe are unchanged.
- Checks (pinned image, rootless, `--pull never --network none`, `--user 0:0 --cpus 3 --memory 4g
  --memory-swap 5g --pids-limit 512`, repository and baseline read-only,
  `PYTHONDONTWRITEBYTECODE=1`), in
  `~/.local/state/composer-bootstrap/c2a-round-a-20261029T201848Z-33027`:
  `focused-a1.log` 70 passed / 17 failed exit 1 and `focused-a2.log` 83 passed / 4 failed exit 1
  (first passes; the failures were the new suite meeting two real shape bugs — a `_differences`
  key error for non-series blocks and a stale expanded disease after clearing — plus test-side
  tuple/harness slips; both product bugs were fixed before `focused-a3.log` **87 passed exit 0**),
  `focused-a4.log` **87 passed exit 0**, `maintained-suite-a1.log` **716 passed (65.64s) exit 0**,
  `r-smokes-all.log` seven R smokes exit 0, `live-a-driver.log` **57 checks, 0 failures, exit 0**.
- Live journey with the real renderer (`live-a/`): all three audiences available and Custom
  disabled with the approved text; opening the editor reported no draft and no customization; 12
  diseases checked with the default open one among them; a subset
  `[campylobacteriosis, gonorrhea, hepatitis_e]` was checked, chart height set to Compact,
  `block-sensitivity-comparison` excluded and `block-coverage-selection` moved; differences were
  reported (`excluded`, `reordered`, `style`, `selection`); an empty selection was allowed in the
  editor, reported customized **and** not ready with the approved sentence, and Generate answered
  400 with that sentence and created no job; the subset was restored and job
  `20261029T203938Z-fcbf6f1348` rendered (`customized`), its snapshot equal to the editor's
  pending digest, carrying the three-topic list, Compact height, the excluded section absent, and
  one preview notice; the chosen disease opened first; the pending selection was committed into
  the copy; Reset restored a byte-identical maintained copy and left the job and its report
  intact; history kept `classification: customized` with a six-section snapshot summary; the
  printed replay rendered the same snapshot (exit 0) with the same effective recipe, the same
  instance identities, the same section order and the same open panel.
- Not verified: no browser was used here. Focus restoration, the live-region announcements, the
  Reset confirmation, keyboard order and the narrow layout are asserted structurally only; the
  user's browser review is the first visual pass. Legacy records remain unclassified by design.
  Round B is still a plan, not implemented. G0/G1/R02 and challenge acceptance unchanged; nothing
  was committed, tagged, staged or published.

## Candidate entry C2a-SITE-04: reuse a retained matching report instead of regenerating

- Scope: the product owner's follow-up after Round A — when the current settings already match a
  successful, still-valid report, the page offers that report instead of an identical generation.
  Round B is untouched. No composition contract, scientific identity, historical provenance or
  maintained recipe changed; the only additions are site-job metadata and a new POST route.
- **Reuse identity (rules, exactly as implemented).** One key, version 1, computed from four
  groups and nothing else:
  1. *normalised effective composition*: the composition that would be rendered (exclusions
     applied, pending disease choice committed), with equivalent spellings unified —
     `series-collection` `topics` equal to the bundle's eligible list **in bundle order** compares
     equal to `"eligible"`; an absent chart style compares equal to `standard`; an absent expanded
     disease compares equal to the first resolved disease. An intentional order difference stays a
     difference.
  2. *retained input/bundle identity*: `bundle.json` `snapshot_id`, a SHA-256 over the sorted
     `path:sha256` map of every bundle file, and the `stakeholder.json` digest.
  3. *renderer/code/environment identity*: digests of `publish.py`, `report_shared.qmd`,
     `report_helpers.R`, `audience_reports.R`, `methods.qmd`, `dashboard.css`; Python, Quarto and R
     versions; and the workflow-config digest. A renderer or environment change invalidates reuse;
     a frontend-only change does not, because it cannot change the package.
  4. *render parameters*: HTML format, preview marker.
  The key is the SHA-256 of that canonical JSON. Matching never uses a recipe name, an audience
  label, a customization badge, file existence or the recipe digest alone.
- **Job metadata added (site-job only, no schema/provenance change):** `reuse_key`,
  `reuse_components` (the record above, for inspection), `package_sha256` (digest over every
  published file's relative path and digest) and `package_files`. Records written before this
  revision have none of them and are therefore **never auto-reused**; they stay visible and openable
  in history. No version of the composition or provenance schema was bumped.
- **Eligibility (checked at lookup and again at Show here):** status `succeeded`; reuse metadata
  present; key equal; the snapshot exists and hashes to the recorded `recipe_sha256`; the package
  directory exists; `report.html` is present; the published-file digest is unchanged; no symlink in
  the package. Failed, interrupted, incomplete, missing, changed or pre-metadata jobs are skipped.
  Among eligible matches the choice is deterministic: newest `finished_utc`, then the recorded
  creation time in nanoseconds, then `job_id`; the generation time is shown. The nanosecond tie
  break exists because two identical generations can finish inside the same second.
- **UI:** when a match exists, Generate is disabled and the page states “A report matching these
  settings is already available.”, with an enabled **Show here**, an **Open separately** link and
  the retained job's exact replay command. Discovered matches never move the page; activating
  Show here loads the retained URL (no render and no package copy), shows that job's digest,
  timestamp and replay, and moves focus to the labelled report region — with smooth scrolling only
  when the reader has not asked for reduced motion. If the same report is already displayed the
  message says so and Show here still returns to it. Availability refreshes with every editor
  document (audience change, accepted edit, reset, reopen, successful generation); a response
  belonging to an older revision is discarded by the existing intent counter. When the match
  disappears between lookup and activation, Show here explains why, restores Generate and leaves
  the displayed report untouched. An invalid pending selection (empty disease set) offers no match
  at all: matching uses the pending settings, never the last valid `recipe.json`.
- **History:** reuse creates no job, rewrites no record and copies no package. Report bytes,
  generation timestamp, provenance, classification and replay command stay with the original job;
  duplicate identical reports are kept and remain individually addressable. Default/Customized
  classification stays independent of reuse eligibility.
- Paths and hashes: `src/composer_site.py b74bc81d…` (reuse identity and eligibility, `/api/reuse`,
  job metadata incl. `created_ns`/`reuse_key`/`package_sha256`, editor `reuse` field),
  `src/composer_web/index.html 61a40ff9…`, `src/composer_web/app.js c6f9b658…`,
  `src/composer_web/app.css 0482e3d5…` (reuse panel, Show here, report focus, reduced motion),
  `tests/test_composer_site.py e3a8c1e7…` (12 reuse tests). `composer_workspace.py 69364eb7…` and
  `tests/test_composer_drafts.py 38530cc6…` are unchanged from Round A; `publish.py`,
  `report_helpers.R`, the composition schema and every maintained recipe are untouched.
- Checks (pinned image, rootless, `--pull never --network none`, `--user 0:0 --cpus 3 --memory 4g
  --memory-swap 5g --pids-limit 512`, repository and baseline read-only,
  `PYTHONDONTWRITEBYTECODE=1`), in
  `~/.local/state/composer-bootstrap/c2a-round-a-20261029T201848Z-33027`:
  `focused-reuse1.log` 72 passed / 1 failed exit 1 (the failure was a message-ordering expectation,
  fixed by checking the missing report before the package digest), `focused-reuse2.log` **100
  passed exit 0** (workspace + drafts + site), `focused-reuse3.log` re-check of the ten reuse tests
  after the ordering fix (10 passed, 44 deselected), and the final coherent runs on the settled
  tree after that fix: `focused-reuse-final2.log` **100 passed exit 0**,
  `maintained-suite-reuse2.log` **729 passed (82.13s) exit 0**, `r-smokes-reuse2.log` seven R
  smokes exit 0, `live-reuse-driver-2.log` **29 checks, 0 failures, exit 0**. The earlier
  `focused-reuse-final.log` / `maintained-suite-reuse.log` / `r-smokes-reuse.log` are retained
  unchanged; the focused one is the run that caught the same-second ordering bug (two identical
  generations in one second were ordered by random job id), which the nanosecond tie break fixes.
  That earlier suite run printed 729 passed but straddled the fix, so it is not used as the
  evidence for the final tree.
- Live journey with the real renderer (`live-reuse-2/`): no match before any generation; a real
  default generation (`20261029T212447Z-41bb74ca8f`) then matched itself; changing the chart height
  removed the match; Reset to default restored it; Show here returned the retained URL, digest,
  timestamp and replay command with no new job, no record rewrite and byte-identical report; a
  real customized generation (`20261029T212611Z-924a1c283d`, three diseases + compact) matched
  itself after the settings were changed away and restored; an empty selection offered no match and
  Show here was refused with the approved sentence; a synthetic newer duplicate
  (`20260101T000000Z-cccccccccc`, clearly labelled) won when intact, was skipped once its files
  changed (Show here refused with “the published files have changed”), and won again after the
  original bytes were restored; a still-valid older match was still accepted on explicit request.
- Limits: reports generated before this revision are intentionally not auto-reusable; no browser
  was used here, so the focus move, the reduced-motion branch, the disabled-Generate state and the
  panel wording are structurally asserted only. G0/G1/R02 and challenge acceptance unchanged;
  nothing was committed, tagged, staged or published.
- **Evidence correction (requested, recorded honestly):** the Round A handover said no evidence was
  overwritten. That was inaccurate for exactly one file. `r-smokes-all.log` was truncated and
  rewritten by the corrective run after the first malformed `docker run` invocation had written only
  `docker: Error response from daemon: No such image: sh:latest` (exit 125) into it. The replaced
  content was that single error line — no test result was lost — and the failed attempt is still
  preserved in the session's background-process record for that invocation. The surviving log holds
  the corrected seven-smoke run. No historical evidence was recreated or relabelled.

## Candidate entry C2a-SITE-05: Researcher reuse diagnosis, report navigation and honest labels

- Scope: the user's follow-up — Health institution reuse worked; Researcher was not offered although
  a “Standard/Default” entry was visible; Show here in the saved list should move to the report
  heading. Diagnosis came first; no render, no reset of the user's draft and no backfilled history
  were used to make the match succeed.
- **Diagnosis (verified, read-only copy of the review work root;
  `diagnose-researcher.log`, `review-inspect/`).** The current Researcher settings are the default
  composition: the draft has no exclusions and no pending selection, and its recipe is
  byte-identical to the maintained recipe (`customized` false, `ready` true). Two Researcher
  reports are retained:
  - `20261029T183306Z-6eec087d85`: its snapshot is byte-identical to the maintained recipe, its
    normalised composition equals the current one, and recomputing the full reuse identity from
    that snapshot gives **the same key as today** — but the job has no `reuse_key` and no
    `package_sha256`, so eligibility returns “generated before reuse metadata existed”.
  - `20261029T185127Z-342d640c13`: a different composition (it would not match even with
    metadata) and also pre-metadata.
  No Researcher report was generated after the reuse revision existed, so there was nothing
  eligible. **This is an intentional exclusion, not a matching defect**: the key was not weakened,
  the old record was not backfilled, and the report remains openable.
- **Label defect found while verifying (fixed, smallest change).** `public_job` filled a missing
  render `mode` with `"standard"`, so a record that never recorded a mode was displayed as
  “Default (standard composition)” — exactly the misleading appearance the user described. The
  guess is removed; the audience still comes from the recorded bundle id, and pre-revision rows now
  read “Customization status not recorded”. The API row for the old Researcher report therefore
  reports `mode: null`, `classification: null`, `status: succeeded`, and a reuse reason of
  “Older report: reuse metadata was not recorded.”
- **Interface.** “Data and saved reports” is split: **Saved reports** (history only, always visible)
  and **Data and source locations** (paths and managed copies, behind a disclosure). Every
  successful row shows the audience and classification, generation time, status and recipe digest,
  the sections it actually rendered (from its own snapshot), a reuse chip — “Reusable now” or “Not
  reusable now” with a short reason (`Older report: reuse metadata was not recorded.`,
  `Different settings, saved input, or renderer version.`, `Not reusable: the published files have
  changed.`, `This report did not complete.`) — and a composition-only note when its sections or
  diseases differ from the editor. A Default/Customized label describes the report's settings and
  never implies reuse eligibility; a report that fails the reuse check keeps `status: succeeded`
  and its Open/Show here actions.
- **Navigation.** One `displayReport` now serves both the automatic-match **Show here** and the
  history **Show here**: it loads the retained URL, updates the displayed digest, timestamp and
  replay command, then `focusReport` scrolls to and focuses the labelled outer report section
  (smooth only without `prefers-reduced-motion`). Repeated activation of the already-displayed
  report still navigates and says so. Refreshing matches or history moves no focus. Opening history
  changes no editor state and generates nothing.
- Paths and hashes: `src/composer_site.py 3e0a1337…` (mode guess removed, per-report reuse view,
  composition match, saved payload), `src/composer_web/index.html 4ea27370…` (sections split),
  `src/composer_web/app.js 6ffb1054…` (shared display/navigation, reuse chips),
  `src/composer_web/app.css 8f5e1cae…`, `tests/test_composer_site.py 3e31e38d…`. `publish.py`,
  `report_helpers.R`, the composition schema, the reuse key and every maintained recipe are
  unchanged.
- Checks (pinned image, rootless, `--pull never --network none`, `--user 0:0 --cpus 3 --memory 4g
  --memory-swap 5g --pids-limit 512`, repository and baseline read-only,
  `PYTHONDONTWRITEBYTECODE=1`), in
  `~/.local/state/composer-bootstrap/c2a-round-a-20261029T201848Z-33027`:
  `diagnose-researcher.log` (read-only diagnosis), `focused-history1.log` **60 passed exit 0** (site
  tests before the label fix), `live-history-driver.log` 22 passed / 1 failed exit 1 — the failure
  was the label assertion that exposed the guessed `mode` — `focused-history2.log` **106 passed
  exit 0** (workspace + drafts + site, after the fix), `maintained-suite-history1.log` **735 passed
  (78.38s) exit 0**, `live-history-driver-2.log` **23 checks, 0 failures, exit 0**.
- Live journey (`live-history-2/`, on a copy of the review work root): Researcher settings valid
  and equal to the default, no reuse offered; the retained report present, successful, unclassified
  and openable, with the “reuse metadata was not recorded” reason and a composition match; the
  retained snapshot’s recomputed key equal to today’s (diagnostic only) and no recorded key; one
  fresh real generation (`20261029T223803Z-d53d54dfca`) then offered for reuse and marked
  “Reusable now”; the older report kept its status and reason; repeated Show here returned the same
  report with no new job, no draft change and no revision change; both reports still open.
- Limits: no browser was used here, so the focus move, the chip rendering and the section split are
  structurally asserted only; pre-revision reports remain non-reusable by design. G0/G1/R02 and
  challenge acceptance unchanged; nothing was committed, tagged, staged or published.

## Feedback and revision

Use F-001 onward. Record candidate, affected requirement/block, requested change, rationale and blocking/nonblocking status. Classify presentation, behavior, scientific/contract, disclosure or scope; assign one owner and acceptance check. Never change metric meaning to satisfy visual preference.

Presentation fixes may reuse unchanged verified analysis but require correct render/evidence identity. Analytical changes require fresh appropriate analysis. Approve contract/scope/disclosure changes explicitly. Link each response to a revision commit and actual render; preserve old reviews rather than relabel them. No automatic screenshot-baseline acceptance or tolerance inflation.

### F-001 — scoped user review of C2a-SITE-01

Reviewer: the user, on the local website. Scope: the stated items only; this is not blanket
acceptance of the earlier browser checklist, and it is not scientific or accessibility review.
Candidate addressed: C2a-SITE-02 (uncommitted, same base `d2b811b…`).

| Id | Report | Class | Blocking | Disposition | Acceptance check |
|---|---|---|---|---|---|
| F-001.1 | Input/workspace setup is unintuitive | presentation | no | Addressed: preset cards replace the recipe/bundle/workspace/copy form; managed copies are created on demand; paths and earlier reports moved under “Data and saved reports” | page contains no workspace/copy controls; `GET` routes write nothing |
| F-001.2 | Preset-first navigation wanted | presentation | no | Addressed: four exclusive cards, standard choice resolves its own recipe and bundle, generation stays an explicit action | presets API + card semantics tests |
| F-001.3 | Section inclusion wanted | behavior | no | Addressed: Include checkbox per section, excluded sections recoverable with settings and ids, effective recipe omits them, required sections explained and refused | include/exclude/restore tests, live exclusion |
| F-001.4 | Clearer section labels wanted | presentation | no | Addressed: frontend label/description map over stable ids; control renamed “Disease expanded when the report opens” with its help line | label-coverage test |
| F-001.5 | Default-open-disease selector: list appears, then vanishes or reverts to “Choose a bundle to list topics” | behavior defect | **yes, for this review** | **Reproduced, then repaired.** Recorded as unresolved at feedback time; the reproduction is in `repro-topic-selector.log` / `topic-selector-repro.json`. Cause: the edit response dropped `topic_choices` (`topics=None`), so every rebuild after any edit lost the list while the saved value was correct. Every mutation now returns the rebuilt document from one place | `test_default_topic_selection_survives_save_and_reopen` (choose → save → reopen → reorder → style) and the live run's “still lists every disease” checks |

The selector item was treated as open until it was reproduced here; the earlier “works well”
statement is not extended to it, and no PASS is recorded for the checklist items the user did not
mention.

### F-002 — product-owner model change: audience customization, disease subsets, honest history

Reviewer: the product owner. Scope: the customization model only; Round B was explicitly left as a
plan. Candidate: C2a-SITE-03 (uncommitted, base `d2b811b…`). Every decision was taken as stated,
including the prohibited items.

| Id | Request | Class | Disposition |
|---|---|---|---|
| F-002.1 | Editing must keep the audience selected; show “Customized” on that card; Reset to default | behavior | Done: the old edit-selects-Custom rule is deleted; the badge is computed from the pending composition versus the maintained default; reset rewrites the copy in place after confirmation |
| F-002.2 | Customized means the effective composition differs, not that the editor opened or a copy exists | behavior | Done: opening the editor and creating the copy leave the badge off; exact return clears it (tests: reorder and back, style and back) |
| F-002.3 | Reset affects the draft only, asks before discarding, never deletes reports | behavior | Done: inline confirmation; jobs, snapshots and reports are separate immutable entries and survive |
| F-002.4 | Disease checkboxes, Select all, Clear, expanded disease only from checked | behavior | Done on the existing collection-subset contract; ordering preserved; `"eligible"` only when the checked set and order reproduce the default |
| F-002.5 | Empty selection blocks generation with the exact sentence, without weakening the recipe contract | behavior/contract | Done: the empty choice lives in editor state; the saved recipe stays renderable; Generate answers 400 with the approved sentence and creates no job |
| F-002.6 | Inspect Compact/Standard and either remove or move to advanced options | presentation | Done: inspected (figure height 3.6→2.4 in, margin class, inspector row; no wording or value change); kept under collapsed “Advanced display options” with the label “Chart height” and explicit help; existing recorded values still load and replay |
| F-002.7 | Saved history must describe the generated snapshot, never the current draft; older records must not be falsely classified | disclosure | Done: new jobs store `classification` + `classification_basis` at generation time; older records show “Customization status not recorded” with their snapshot summary; nothing is backfilled or compared with today's default |
| F-002.8 | No composition `origin`/schema/provenance field in this round | contract | Honoured: the only additions are site-job metadata and the draft editor-state schema (`composer-draft/2`); the composition schema, `publish.py`, `report_helpers.R` and maintained recipes are untouched |

Two product bugs were found and fixed during this round's own verification, not by the user: the
differences helper assumed every block carried topic fields (KeyError on non-series blocks), and
clearing the disease selection left a stale expanded disease visible in the editor. Both are
recorded in `focused-a1.log`/`focused-a2.log` and fixed before the green runs.

### F-003 — Round A user review (scoped) and the reuse request

Reviewer: the product owner. **User-reported PASS is recorded for exactly two things**: Reset and
the related customization behaviour, and the empty-disease warning shown correctly as “Select at
least one disease, or turn off ‘Annual trends by disease’.” Nothing else from the earlier browser
checklist is inferred as tested; keyboard order, focus restoration, announcements, the Reset
confirmation dialogue and the narrow layout remain unverified by the user. The disabled Custom card
was understood as the intentional Round A limit; Round B was not requested.

| Id | Request | Class | Disposition |
|---|---|---|---|
| F-003.1 | When the effective settings already match a successful, still-valid report, do not offer an identical generation: disable Generate, explain, offer Show here | behavior | Done: `/api/reuse` + one centralised key; the editor document carries the deterministic newest match; Generate is disabled with “A report matching these settings is already available.” and Show here is enabled |
| F-003.2 | Define safe matching first over composition, bundle, renderer/code/environment and render parameters — never by name, badge, existence or recipe digest alone | contract/disclosure | Done: reuse key v1 over those four groups; documented below |
| F-003.3 | Exclude failed, interrupted, incomplete, missing, tampered or incompatible jobs; older metadata that cannot establish compatibility is ineligible but stays in history | disclosure | Done: eligibility re-checks status, metadata, key, snapshot digest, report presence and the published-file digest; pre-metadata jobs are skipped and remain listed |
| F-003.4 | Show here must load the retained report, not rerender or copy it; show digest, timestamp and replay; move focus to a labelled region; respect reduced motion; never auto-jump | behavior/accessibility | Done: POST returns the job's own URL/replay; no job is created and no package is touched; focus moves only on activation; smooth scrolling only without `prefers-reduced-motion` |
| F-003.5 | Revalidate on activation; a failure must not remove the displayed report | behavior | Done: Show here re-checks the key and package for the requested job; failures explain the reason, refresh availability and leave the on-screen report alone |
| F-003.6 | Invalid pending settings must not match stale valid ones | behavior | Done: matching uses the pending composition; an empty disease set offers no match and Show here is refused with the approved sentence |
| F-003.7 | Preserve history and provenance; no new job or claim of a new generation | disclosure | Done: reuse writes nothing; bytes, timestamps, provenance, classification and replay stay with the original job; identical duplicates are kept |
| F-003.8 | Correct the earlier evidence-overwrite claim honestly | process | Done: the Round A handover's “no overwrite anywhere” was wrong for `r-smokes-all.log`; see the correction in C2a-SITE-04 |

Smallest metadata change: site-job level only (`reuse_key`, `reuse_components`,
`package_sha256`, `package_files`, reuse version 1 inside the components). No composition or
provenance schema version was introduced, and no historical record was rewritten.

### F-004 — reuse review: Researcher match, report navigation, section naming

Reviewer: the product owner. **User-reported PASS is recorded for exactly one thing**: the Health
institution report was correctly reused. The Researcher result was a failure report, not a pass,
and no blanket reuse PASS is recorded.

| Id | Report/request | Class | Disposition |
|---|---|---|---|
| F-004.1 | Researcher was not offered/reused although a Standard/Default entry exists | behavior/diagnosis | Diagnosed: intentional exclusion (the retained Researcher report predates reuse metadata; its composition, bundle and renderer identity all match). No key weakening, no backfill, no reset |
| F-004.2 | A Default/Standard label must not imply reuse with today's environment | disclosure | Fixed: the guessed `mode` for pre-revision records is gone; rows now show classification separately from a reuse chip with a reason |
| F-004.3 | Saved reports Show here should move to the report heading | behavior/accessibility | Done: one shared `displayReport` + `focusReport` for both the match panel and history; repeated activation still navigates; refreshes never move focus |
| F-004.4 | Rename "Data and saved reports" or separate source information | presentation | Done: “Saved reports” (history only) and “Data and source locations” (paths, managed copies, behind a disclosure) |
| F-004.5 | Distinguish openable from reusable; explain ineligibility without exposing internals | disclosure | Done: per-row reuse codes/reasons (`no_metadata`, `different_identity`, `artifact`, `not_completed`, `settings_not_ready`), status never demoted |
| F-004.6 | Opening history must not change the draft or trigger generation | behavior | Done: history display is client-side over the retained URL; verified against draft bytes and revision |

### Final user acceptance F-005 — C2a custom local workbench (closeout)

Reviewer: the product owner. **User-reported PASS** is recorded for the reviewed
generation/reuse workflow **for all three audiences** (Researcher, Health institution, Public),
for the Saved reports **Show here** navigation, and for the audience/customization behaviour
reviewed earlier (Reset, the Customized badge, and the empty-disease warning). No browser version,
screenshot, independent scientific review, accessibility certification or additional browser test
is claimed or invented; items the user did not exercise (keyboard order, focus restoration, live
announcements, the Reset confirmation dialogue, narrow layout) remain **as previously recorded —
structurally asserted only**. The disabled Custom block-library composer is an intentional
remaining scope limit: Round B is neither implemented nor accepted.

Candidate and evidence. The accepted candidate is the working tree on `d2b811b545e055c27cd1381
229eb98b46196f05a`, committed immediately after this entry as
`feat(composer): add local report workbench with audience presets and reuse`. Its final source
hashes are `composer_site.py 3e0a1337…`, `index.html 4ea27370…`, `app.js 6ffb1054…`,
`app.css 8f5e1cae…`, `composer_workspace.py 69364eb7…`, `test_composer_site.py 3e31e38d…`,
`test_composer_drafts.py 4a2000b8…` (a trailing blank line was removed at EOF before
commit; the 38530cc6… hash in the C2a-SITE-04 entry describes that earlier state), with the two
shared-service edits in
`publish.py 67c2a3ea…` and `report_helpers.R 7436f91c…`. Evidence is retained unchanged in
`~/.local/state/composer-bootstrap/c2a-round-a-20261029T201848Z-33027` and the earlier
`c2a-site-20261029T181351Z-2034`; the review service runs from these sources on loopback.

Automated results, as already recorded on this tree: focused service/workspace/draft tests
**106 passed exit 0** (`focused-history2.log`), maintained suite **735 passed (78.38s) exit 0**
(`maintained-suite-history1.log`), and the live reuse/navigation run **23 checks, 0 failures,
exit 0** (`live-history-driver-2.log`). The seven R smokes were last run green on the same R
sources (`r-smokes-reuse2.log`, all exit 0).

Real-render and R evidence carries its **original source scope**: those packages were produced
from the then-uncommitted working tree, not from this commit. Specifically, the live-generation
records (`job 20261029T203938Z-fcbf6f1348` in `live-a/`, `20261029T212447Z-41bb74ca8f` and
`20261029T212611Z-924a1c283d` in `live-reuse-2/`, `20261029T223803Z-d53d54dfca` in
`live-history-2/`) each record `source_state: uncommitted` in their provenance and are **not**
relabelled as committed-source builds; every report package and the review work-root reports keep
their original provenance bytes.

Known limits carried forward: the block-library Custom composer is deferred (the card is visible
and disabled); reports generated before the reuse revision remain intentionally ineligible for
automatic reuse while staying openable in Saved reports; the disease wording assumes
notifiable-disease topics; one measure and one series collection per composition; no composed PDF,
upload, second-snapshot comparison or sparklines; no independent scientific, accessibility or
cross-browser review. The earlier evidence-overwrite correction stands as recorded in
C2a-SITE-04: the Round A handover's “no overwrite anywhere” was inaccurate for one
`r-smokes-all.log` containing only a failed docker invocation's error line.

This is scoped product acceptance of the reviewed workflow only. It is **not** whole-project
acceptance, not G0/G1/R02 or G6 acceptance, not scientific acceptance and not release approval;
no ledger, tag or deployment is changed by this entry.

## Resume record

Before pausing persist actual branch/commit/worktree status, owned uncommitted paths, task/dependencies, checked artifacts, failures/repair attempts, unresolved decisions, locks/other writers, next executable action and prohibited shortcuts. Raw/private logs remain in approved storage. Commit durable decision/checkpoint summaries at useful boundaries, not every transient thought.

On resume fetch/read current refs, inspect other writers, validate candidate/manifests and reconcile intervening changes. Never reset/stash/delete shared work or reuse stale success. Open questions are not implicit approvals.

## Runner opening instruction

Read this protocol, HANDOFF.md, requirements.json, five task briefs and governing product documents. Verify seed/frozen refs; establish preparation dispositions and current baseline; report unrun/failed checks. Assign the earliest unblocked minimal task before editing. Use its design branch from the current build tip. Preserve source/request contracts and workflow policy. Produce tested incremental commits and independently reviewed internal PRs to build/composer. At visual checkpoints supply actual rendered output and pause acceptance for human feedback. Continue only independent unblocked work. Do not merge the umbrella PR, modify frozen/main/releases or claim an unattended runner started merely by reading these instructions.

## Final acceptance

Required requirements have implementation and independent evidence; optional/deferred/decision-required items have explicit disposition. Existing routes are preserved or have approved parity-tested migrations. Actual UI/CLI complete the same supported request/replay journey. Inspectable inputs/methods/plotted results/code agree. Failure/tamper/path/cache/export checks pass. Latest clean candidate/environment are recorded, not inherited green checks. Human final review resolves or explicitly accepts issues. Promotion requires separate authorization.
