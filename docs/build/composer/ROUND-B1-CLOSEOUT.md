# Round B1 closeout — durable handoff (naming, section titles, duplicate collections)

Written at the close of the Round B1 work package, for an already-onboarded composer agent.
Read [REVIEW_AND_RESUME.md](REVIEW_AND_RESUME.md) (protocol, F-007 acceptance, B1-* entries),
[HANDOFF.md](HANDOFF.md), [BLOCK-CATALOGUE.md](BLOCK-CATALOGUE.md) and
[requirements.json](requirements.json) before acting. This file records state, not permission.

## 1. Accepted scope (user-reported) and what it does not cover

The product owner reviewed the local workbench and accepted:

- the **shared block names** used in the library, editor rows, report headings and report navigation;
- **optional per-section report titles** (`Report section title`) with the factual summary beside them;
- **duplicate `Annual trends by disease` instances**, each with independent diseases, chart layout,
  chart height, display years, default-open detail, title, order and inclusion.

Explicitly **not** covered by that acceptance: accessibility, keyboard/focus order, narrow layout,
cross-browser/device behaviour, independent scientific review, and any block combination the
reviewer did not exercise. Visual claims remain user-reported only. Automated results below are
author evidence, not acceptance.

## 2. Candidate / worktree identity

- Repository `/home/builder/composer-sandbox`, branch `design/contracts`.
- HEAD `2938b897d21d0ebe15b792151bdcae3d34433ad2`, parent `d2b811b545e055c27cd1381229eb98b46196f05a`.
- Working tree: **17 modified + 6 untracked paths** (one of the six is this document; the accepted
  candidate itself was 17 modified + 5 untracked), index empty, everything **unstaged and
  uncommitted**. `git diff --check` exit 0. Do not commit, stage, reset, stash or delete.
- Key file hashes at closeout:
  `scripts/health_pipeline/config/composer/block-labels.json 1c1019448da1f247…`,
  `scripts/health_pipeline/composer_library.py 5a986b1c7b8bd94b…`,
  `scripts/health_pipeline/composer_workspace.py fef5a8e471ca1644…`,
  `scripts/health_pipeline/publish.py 481f8e2214933ee0…`,
  `scripts/health_pipeline/templates/report_helpers.R b9901e24fca871af…`,
  `src/composer_site.py 853972a3563ac23d…`, `src/composer_web/app.js 7ba76f940f9137df…`,
  `src/composer_web/app.css 53c90c919aa70e5b…`, `src/composer_web/index.html a63955a63ca3996e…`,
  `tests/js/custom_dom_check.mjs 2b830ffb6f4ccdbd…`, `tests/js/minidom.mjs 1443dfad3fcb5d71…`,
  `tests/test_composer_custom.py 2183c25d150ebb98…`, `tests/test_composer_custom_ui.py 7faa47cdf01277a1…`,
  `tests/test_composer_collection.py 00a13de1d265b21d…`.

## 3. Implemented behaviour and invariants

**Shared labels.** `config/composer/block-labels.json` is the single reader-facing name/description
source, read by `composer_library` (composer) and `report_helpers.R` (section `<h2>` and the composed
navigation). Names: Report context · Annual trends by disease · Annual trend for one disease
(historical, not offered) · **Change from the reference year** · Latest observations by disease ·
Coverage and included data · Comparison across analysis choices · Limitations and cautions ·
Reproduction and evidence. The file is in the renderer reuse inputs (`REUSE_FILES`), so wording
changes invalidate reuse. Canonical block ids, recipe fields, topic ids and analytical inputs never
depend on it. Monitored descriptions state: observations across years (annual trends), the latest
saved observation inside the reporting window (monitoring), the saved reporting-year-vs-baseline-year
comparison (reference).

**Section titles.** Optional additive `titles: {"<instance_id>": "<plain text>"}` on
`health-report/composition-recipe/2`. Rules: existing instance ids only; trimmed; non-empty after
trim; ≤ 80 characters; no control characters; blank input removes the override; **opening a draft
never writes**. Rendering: title ⇒ `<h2>` = title, with `stable name · effective summary` beside it;
no title ⇒ `<h2>` = stable name, summary beneath. Text-escaped; the navigation `aria-label` uses a
quote-escaping helper (`esc_attr`). Provenance records `composition.section_titles`. Quarto/pandoc
then applies typographic quotes to displayed text; the stored value is plain ASCII.

**Identity and cache (verified, not assumed).** No identity covers a whole section's presentation.
`series-collection-identity/1` (panels) and `/2` (combined) cover the chart's own inputs — measure,
style, layout, default-open disease, periods, members — and deliberately exclude the section title:
a titled and untitled collection with identical settings produce the same collection identity.
Titles change the recipe bytes, hence the composition digest and the reuse key, and are recorded
separately. Analytical, rows and member instance identities are unchanged by a title. A layout
change moves `panels` (`/1`, byte-identical to the historical payload) to `combined` (`/2`).

**Duplicate instances.** The single-collection-per-recipe rule is lifted; `series-collection` is
repeatable; `reference-comparison` stays a singleton; the legacy `series-trend`/collection exclusion
is unchanged. A duplicate gets a fresh composition instance id, a copy of the source title and its
own settings. Removed instances leave **all** active editor references in one write (exclusions,
pending selection/options, pending replacement state, title) and keep their id in `retired`;
`repair-draft` removes only orphaned references, on explicit action. `display_scope.collections`
lists every section; the legacy `collection_default_topic` describes the first collection in
effective recipe order (an excluded section never supplies it).

**Navigation and links.** Composition navigation always carries `Section i of n: <label>`; visually
identical entries are disambiguated by the compact summary. Editor-only "Copy 2/3" ordinals derive
from the instance id (stable across reordering) and are never published. Monitoring rows link to the
**first included, verified, compatible** collection in effective recipe order (topic, measure,
geography, saved dataset, effective years = monitoring window); an incompatible collection is never
used; reordering compatible collections changes the destination (documented); the link names its
destination section in `aria-label`.

**Period semantics (read-only in the composer).** Reporting window, reference year, geography and
measure come from the bundle's `stakeholder.json`; blocks carry no analytical years. The collection
`years` value is a **display window** inside that window. Reference comparison = reporting year vs
`reference_year` baseline (saved percentage, never recomputed). Monitoring = latest saved annual
observation per disease inside the window, with each row's observation year shown. The editor states
these and where to change them ("generate an analysis with different settings").

## 4. Evidence (authoritative vs superseded)

Evidence root: `~/.local/state/composer-bootstrap/b-round-b1-20261029T232154Z-78941`.

Authoritative:
- `maintained-suite-naming-3.log` — **791 passed, 2 skipped, exit 0** (full maintained suite on the
  final tree).
- `focused-naming-ui-final.log` — DOM harness (real `app.js` + real server transcript) **3 passed,
  exit 0**, run against the final tree after the last code change.
- `r-smokes-naming-3.log` — seven R smokes, exit 0 each; plus `r-composition-titles-2.log`,
  `r-monitoring-caption-2.log`, `r-collection-layout-1.log`, `r-tabular-labels-2.log` (exit 0).
- Real renders + replay, `live-naming-4/`: researcher report with two collections in one report
  (combined "Overview (combined)" + panels `Focus "A" & <B>`), job `20261030T204656Z-3a71b6bfdf`;
  institutional reports with overlapping collections before/after reordering, jobs
  `20261030T204926Z-f55ead2fa7` and `20261030T205050Z-fbdfef422f`; CLI replay package
  `live-naming-4/replay-a/`. Driver `driver.log` = 30 checks / 3 failed string assertions,
  superseded by `verify-2.log` **16 checks, 0 failures** over the same packages.
- Earlier slice still valid for the shared editor and combined chart: `combined-layout-harness.log`
  (49 checks), `live-combined/` with `verify-2.log` (32 checks).

Superseded failures (kept, never rewritten, and **not** counted as passing):
- `live-naming/driver.log` — my driver crashed with `StopIteration` (a dropped response assignment);
  no product defect.
- `live-naming-2/driver.log` — `NameError: heading is not defined` (test helper ordering).
- `live-naming-3/driver.log` — 4 failures: 3 rendered-string assertions (Quarto's `anchored` heading
  class, typographic quotes) and **1 real defect** — the monitoring caption replacement had silently
  not applied; fixed in source, verified by `r-monitoring-caption-2.log` and the final packages.
- `maintained-suite-naming.log` and `-2.log` — 786 passed, 5 errors from
  `tests/test_tabular_presentation.py`: the smoke sources the templates from a temporary directory,
  so the new label file was not found. Fixed by naming the project in that smoke plus a
  project-independent fallback in the loader; `-3.log` is the authoritative run.
- Earlier rounds' logs (`focused-naming-1..5`, `focused-titles-1..5`, `focused-layout-*`,
  `r-smokes-naming-1..2`, `live-naming*` pre-4) remain for their specific corrections.

## 5. Known limitations and deferred items

- Composed reports are HTML-only; no composed PDF.
- The combined chart layout is the default for **newly created** collections; the three maintained
  recipes still render `panels`, and a working copy of a preset keeps that presentation until the
  layout is switched explicitly. Making `combined` the maintained default is a separate follow-up.
- No per-block analytical period controls. A report-level **Analysis settings** workflow (choose
  window/reference year, validate against available data, generate/select the bundle, show affected
  blocks and incompatible display windows, preserve the prior report/draft, record parameters,
  data version and identities) is **design-only**; the site never launches analysis or acquisition.
- `series-trend` remains a supported contract for historical recipes but is not offered as a new
  section; no conversion action exists for drafts that still contain it.
- Browser/visual behaviour of this slice is user-reported for the three accepted behaviours only;
  accessibility, keyboard order, narrow layout and cross-browser remain unverified.

## 6. Review service (local, authenticated, loopback only)

- Container `composer-site-review`, id `e6c0233ca79e`, started `2026-10-30T21:01:28Z`, image
  `sha256:1ddf322f…`, `127.0.0.1:2719 -> 2719/tcp` only, bridge network, not privileged, no Docker
  socket; `/home/builder/composer-sandbox` → `/app` read-only,
  `baseline-lJXSvvGc/output` → `/inputs` read-only, `…/b-round-b1-20261029T232154Z-78941/review` →
  `/review` read-write. **Not restarted at closeout.**
- Access: open `http://localhost:2719/?token=<contents of the token file>` from the Windows browser
  (Brave); the per-run token is in
  `…/b-round-b1-20261029T232154Z-78941/review/work/access-token.txt` (mode 600). Never print the
  token, the authenticated URL or cookies, in chat or shareable logs.
- Preserved user state in that work root: Custom drafts for `researcher` and `health_institution`
  (the researcher draft contains the reviewer's own edits) and **nine** saved reports. Do not move,
  merge, delete or reset them.

## 7. First safe action for the next agent

1. `git -C /home/builder/composer-sandbox status --porcelain=v1 -b` and `git rev-parse HEAD`; compare
   with §2. If the tree moved, reconcile before anything else and do not reuse these results.
2. Read [REVIEW_AND_RESUME.md](REVIEW_AND_RESUME.md) F-007 and the B1-* entries; confirm the
   evidence logs in §4 still exist with the stated outcomes.
3. Pick up only work the product owner authorizes next. The natural candidate is the design-only
   **Analysis settings** workflow; it requires an explicit approval and its own bounded slice.
4. Ask before any write to the review work root, and never mutate a saved report package.

## 8. Prohibited without a new, explicit authorization

Commit, stage, push, tag, merge, rebase, reset, stash, branch switching, deleting or rewriting
evidence, editing the acceptance ledger, changing the three maintained recipes, weakening the
validators, adding dependencies, running acquisition/analysis, restarting or rotating credentials of
the review service, exposing it beyond loopback, and starting the next phase.
