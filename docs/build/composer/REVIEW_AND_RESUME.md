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
