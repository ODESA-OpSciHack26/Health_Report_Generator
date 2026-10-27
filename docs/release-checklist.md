# Release checklist

## Integration acceptance is not release publication

The steward-ready integration branch is `integration/steward-ready-v1`.
Merging an integration PR does not promote it to `main`, publish a site,
or authorize a new tag. See [handover](handover.md) for recorded evidence.

Before acceptance, identify the exact candidate commit and require a clean
worktree. Verify CI for that candidate; do not treat an earlier feature
head's green checks as a new test of a later merge commit.

## Fresh-checkout verification

Clone the current repository and select the integration line:

```sh
git clone --branch integration/steward-ready-v1 [https://github.com/ODESA-OpSciHack26/Health_Report_Generator.git](https://github.com/ODESA-OpSciHack26/Health_Report_Generator.git)
cd Health_Report_Generator
git rev-parse HEAD
git status --short
```

For a frozen candidate, check out its recorded commit before testing.
Follow [setup](../GETTING_STARTED.md) and [reproduction](reproduction.md).

1. Build the report image and generate into a previously unused output folder.
2. Run output checks, release verification, Python tests, app smoke checks
   and an unchanged no-op dry run against that same output.
3. Require the applicable `fast`, `secrets`, `container` and `full` CI jobs
   to succeed; record the tested SHA and CI run identity.
4. Confirm three standard audience folders, each containing report/methods
   HTML and PDFs, provenance sidecars, analysis data and the packaged app.
5. Check source, snapshot identity, applied filters, effective parameters,
   shared-template hash and timestamps. Preserve warnings and limitations.
6. Inspect all audience HTML pages and PDFs, navigation, controls and downloads.
   Record visual-review findings separately from automated checks.
7. If accepting the optional local form, test real browser submission and
   cache behavior separately. The GitHub connector has its own acceptance
   checklist in [connector setup](../CONNECTOR_SETUP.md).

## Data, software and evidence

- Record the exact code commit, configuration, runtime and dependency versions,
  image identity, data snapshot and selected parameters.
- Preserve the complete audience folders, `release.json` and matching
  snapshot archive. Hashes alone cannot recover missing data or reports.
- Confirm that the archive can be used with the recorded code/environment.
  Retain any manifests needed for archived-input reproduction.
- Review [scientific policy](scientific-policy.md),
  [limitations](limitations.md), and [citation metadata](../CITATION.cff).
- The tracked [LICENSE](../LICENSE) is MIT for the software.
  Confirm attribution and the separate [source-data terms](../data/README.md);
  do not describe the software licence as licensing the source data.
- Run the pinned history scanner after the final commit. Review findings
  before adding any exact-fingerprint exception; do not suppress whole
  evidence paths or scanner rules.

## Maintainer release decision

Publication requires a separate maintainer decision about the target branch,
version, release notes, citation metadata and distribution of verified artifacts.

Preserve the original `release/v1.0.0` reference and any existing `v1.0.0`
tag. Never move or recreate an existing version to label this integration.
Choose a new, unused version only after approval, then tag the approved
commit and attach its matching verified artifacts and reproduction inputs.

This checklist intentionally provides no automatic tagging, promotion,
deployment or overwrite command.
