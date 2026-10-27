# Focused local browser review (not yet performed)

Status: PENDING. No browser result is inferred from unit tests or generated HTML.
Use only the synthetic example or reviewed public data. The result contains the
original input bytes and should not be exposed as an upload/public hosting service.

## Open locally

After generating reproduced/tabular-example, run from the repository root:

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory reproduced/tabular-example
```

Open http://127.0.0.1:8000/researcher/report.html in your browser. This server is
local-only and for synthetic development review, not production. Stop it with Ctrl+C.
Review report.html and methods.html for researcher, health_institution and public.

## Record actual observations

For each check record PASS, FAIL or NOT TESTED, with browser/version, OS, UTC review
time, source revision, render-manifest SHA-256, audience/document and any screenshot.
Store the record/screenshots in a separate reviewed reproduced/ evidence folder.
Do not mark checks passed from this checklist alone.

1. Audience wording: correct title, profile and source label; no inherited FOPH
   attribution, epidemiological claims or inferred units/geography for supplied data.
2. Data: the example's three observations are initially in source order, with
   Gamma's missing date/value visible and no invented snapshot date or aggregation.
3. Filter: search Alpha, then clear; rows disappear/reappear without changing the
   saved bundle. Ensure labels explain that filtering changes the view only.
4. Sort: click a heading twice; verify both directions. Focus a heading with Tab
   and activate with Enter. Inspect category, numeric and missing-value behavior.
   If missing cells fall back to lexical sorting, record it; do not assume a fully
   type-aware missing-value sort policy.
5. Navigation and downloads: findings/methods links, render provenance, preparation
   provenance and bundle manifest all open/download from each audience folder.
6. Offline: keep the localhost server running, disconnect external internet and
   reload. Check styling, tables, filter/sort and local downloads. Inspect the
   browser network panel for external requests or failed resources.
7. Layout: review desktop and narrow viewport, readable tables and visible caveats.
   Check visible keyboard focus and basic labels. This is not a formal accessibility
   conformance audit; record untested assistive-technology checks explicitly.
8. Safety: synthetic HTML-like category text, if tested, must display as text, not
   execute or create image/script elements. Do not use sensitive data for this test.

Any FAIL is a finding to preserve, not something to hide by editing the acceptance
record. The evidence archive never asserts browser acceptance automatically.
