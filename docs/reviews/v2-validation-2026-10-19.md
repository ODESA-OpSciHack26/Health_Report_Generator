# V2 validation and local fixes

Date: 2026-10-19
V1 baseline: 7253baebde65c21d350ab392fe55264585391822
V2 reviewed: eec246b2614913855c3ef8e8d9d2b1499d080431
Environment: Ubuntu terminal on Windows; Docker linux/amd64;
Docker Engine 29.8.1; Compose v5.5.1.

## Summary

V2 retains the core IDD processing modules but changes reporting and local
execution. Unmodified v1 completed all 17 workflow steps. Unmodified v2
failed during researcher HTML rendering. Local corrections restored the
tested IDD workflow, CSV reporting, and researcher browser-upload journey.

## Fixes in this branch

- Correct packaged map-asset lookup.
- Make secondary IDD report provenance select CSV or Parquet consistently
  with the report loader, recording the selected input path.
- Hash the actual packaged report.qmd in secondary provenance, with a
  fallback for standalone audience-template rendering.
- Wrap generated Plotly HTML in a raw-HTML block in CSV Quarto source.
  Supported CSV/TSV fixtures then rendered in approximately 9-11 seconds.
- Move Marimo layout logic that reads source.value into a separate cell
  from the cell creating that control.

## Validation performed

- Both version-specific Docker images built successfully.
- V1 completed 17/17 workflow steps.
- Patched V2 completed the 11 remaining workflow steps, reusing previously
  generated data and analysis; no full clean patched rebuild was performed.
- Snapshot CSV, snapshot TSV, and category-bearing time series imported
  with correct modes, input hashes, row counts, and expected saved values.
- Empty and inconsistent-row inputs were rejected.
- Patched CSV reports retained HTML, editable QMD, data, summary, chart,
  methods, and report-level provenance.
- Researcher CSV upload through patched Marimo succeeded.
- Two browser-generated reports used different timestamped folders;
  the original report checksum remained unchanged.
- Generated reports were accessible in a Windows browser through a
  temporary local HTTP server.

## Remaining issues and limitations

- Primary IDD provenance still identifies the original shared template
  when a different audience template is rendered.
- CSV report provenance lacks input hashes, software/code versions,
  processing rules, and a link to the richer ingestion metadata.
- Institution status counts can classify unknown-baseline indicators
  as normal/low.
- Separate audience templates do not satisfy the single-source reporting
  requirement as currently implemented.
- Restart has no meaningful reset implementation.
- Numeric-only and date/value-only uploads are unsupported.
- No CSV PDF was produced in the tested route.
- Direct output links in Marimo have not been demonstrated.
- V1/V2 numerical equivalence on identical inputs is untested.
- Browser audience switching, browser TSV/time-series uploads, and the
  full automated test suite have not been validated in this review.
- No automated regression tests were added for these fixes.

## Release position

This is a tested local integration-fix candidate, not a complete V2
validation or a release-ready approval. Original failure logs and
incremental test evidence are retained outside the repository.

## Follow-up: CI output-contract fixes

The first GitHub validation exposed missing embedded primary provenance
in the researcher and health-institution HTML reports. After correcting
that locally, output validation exposed missing interactive-table scripts.

Changes in scripts/health_pipeline/publish.py:
- Embed the primary workflow provenance in HTML documents when absent.
- Reuse the existing shared filtering/sorting script for pandas-generated
  tables, adapting its selector to those tables.

Validation:
- An initial container build completed 17/17 steps, then failed the
  interactive-table check.
- After both additions, the incremental container rebuild completed all
  11 scheduled steps.
- check_outputs.py passed: audience outputs and provenance verified.
- verify_release.py passed: release hashes, provenance and rendered links
  verified.
- Output directory: reproduced/provenance-review.
- Browser filtering/sorting behaviour has not yet been confirmed.
- GitHub Actions must rerun on the follow-up commit before CI success
  can be claimed.

Limitations:
- Table-control injection currently requires a supplied provenance record.
- Previously documented provenance-metadata and reporting-design issues
  remain outside the scope of these fixes.
