# Reproduce the opt-in supplied-table reports

The canonical Snakemake command is unchanged. This optional command prepares one
explicitly mapped UTF-8 CSV/TSV and renders all three audiences from report_shared.qmd.
Use only synthetic or reviewed open data; original source bytes are retained.

## Setup and version identity

Follow [the project setup](../GETTING_STARTED.md) and use the report container.
Run from the repository root on the matching source revision. The example source
version is pinned by SHA-256 in examples/tabular/request.json. Software and
preparation/render code hashes are machine-generated in the resulting provenance.
The current validated contract is Python 3.11.6, pandas 2.2.3 and Quarto 1.3.353;
workflow/toolchain.json and locked requirements remain authoritative.
A new source release requires a deliberately updated request checksum, not bypassing it.

## One command: source to three audience reports

```bash
docker compose run --rm --no-deps report python scripts/health_pipeline/tabular_run.py build --input examples/tabular/observations.csv --request examples/tabular/request.json --output reproduced/tabular-example
```

The command creates a missing output parent after validation. It never replaces
an existing output. Pick a new output name for a repeat demonstration. The initial
example has three rows, including one missing date and one missing numeric value.
All observations are retained; no sums, averages or percentage changes are computed.

Expected output beneath reproduced/tabular-example:

- bundle/: captured source, typed prepared rows, preparation provenance and manifest.
- researcher/: report.html, methods.html, provenance.json.
- health_institution/: the same document names with the institutional profile.
- public/: the same document names with the public profile.
- render_manifest.json: exact artifact hashes and sizes.

```bash
docker compose run --rm --no-deps report python scripts/health_pipeline/tabular_run.py verify --output reproduced/tabular-example
```

Requests contain exactly schema, source_sha256, mapping, mode and period. A snapshot
request maps category and measure, uses mode snapshot and period null. Time series
also map time and explicitly select year, month, week or day. Missingness is empty
or whitespace-only fields; literal NA/null strings are not automatically missing.
No scientific units, geography, denominators, classifications or alerts are inferred.
Negative values are permitted without declaring them scientifically appropriate.
Numeric precision follows pandas, not exact decimal arithmetic.

## Provenance and repeatability limits

All three audiences consume the same independently verified captured bytes and rows.
Audience communication differs, not the calculation. The shared-source renderer
fingerprints the one-command entry point as well as preparation/presentation code.
Generation timestamps vary; do not promise byte-identical forced HTML rerenders.
Verification is strict about preparation software and code identity: changing the
code/environment can require an explicit migration. Use the recorded matching
revision/environment to verify historical artifacts. Hashes are not signatures.
A fully replaced, internally consistent source+bundle needs an external trust anchor.

## Browser review

Follow [the focused browser checklist](m4-browser-review.md). Unit tests and HTML
source inspection do not establish browser, accessibility or offline acceptance.

## Clean-checkpoint evidence and archive

After tests and review, checkpoint the source. Generate a new canonical release and
new one-command example from that clean commit; never overwrite the earlier runs
or edit their sidecars to pretend they were generated after the commit.
Archive only reviewed, explicitly selected evidence paths. The archiver requires a
clean source worktree and an output outside the repository. It includes a manifest
of file hashes and the local source commit; remote commit availability is not claimed.
The archive contains original source bytes and logs. Review for sensitive content
before setting the acknowledgment flag; this is not a secret scan or privacy approval.

Example, after creating a writable archive directory in Ubuntu home:

```bash
mkdir -p "$HOME/m4-handover"
docker compose run --rm --no-deps --volume "$HOME/m4-handover:/handover" report python scripts/health_pipeline/evidence_archive.py create --include reproduced/tabular-example --output /handover/tabular-example.tar.gz --acknowledge-content-review
docker compose run --rm --no-deps --volume "$HOME/m4-handover:/handover" report python scripts/health_pipeline/evidence_archive.py verify /handover/tabular-example.tar.gz
```

Use additional --include arguments for each reviewed canonical run, gate evidence
folder or human-review record. Do not select all of reproduced/ by default. Archive
verification reads members as streams and never extracts them. It checks internal
integrity, not authenticity, evidence completeness or browser success. No hostile
archive resource-limit/security acceptance is claimed. Transfer a reviewed archive
and its separately recorded checksum through an agreed channel; do not commit it.

## Automated local gate runner

Run on the Ubuntu host from the repository root; it invokes the report container
and captures logs without installing pipeline dependencies into the host Python.

```bash
python3 scripts/ci/check_tabular_handover.py --phase precommit --name m4-handover-precommit-01
```

This captures new/full tests, pinned lint and the real one-command example.
After reviewing and checkpointing the source, run the clean phase:

```bash
python3 scripts/ci/check_tabular_handover.py --phase clean-release --name m4-handover-clean-01
```

The clean phase additionally builds/verifies a new canonical release, runs the
researcher packaged-app smoke tests and requires a no-op rebuild. Names must be
new: existing evidence is never overwritten. Each phase records source hashes,
commit/worktree state, stage results and explicit browser/image-build limitations.
It does not build a new image, push Git history or perform browser review.

The archive source_commit identifies the clean archiver checkout, not a claim that
all included historical runs were generated from that commit. Preserve each run's
original provenance and generation revision; never relabel older evidence.
