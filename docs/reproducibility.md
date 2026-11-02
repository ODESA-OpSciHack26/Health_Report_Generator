# Reproducibility and provenance

Reports are reproducible from the recorded inputs, settings and software versions. Byte-identical
HTML/PDF is not promised (generation timestamps and renderer builds change), but the inputs,
parameters, versions and artifact hashes are recorded and can be checked.

## Authoritative versions and dependency ownership

| Contract | File |
|---|---|
| Runtime policy (Python, R, Quarto, uv, TinyTeX) | `workflow/toolchain.json` |
| Python orchestration lock (production resolution) | `scripts/health_pipeline/requirements.lock.txt` |
| Project metadata (`requires-python`, lint rules, test markers) | `pyproject.toml` |
| R package resolution | `renv.lock` (restored by `workflow/restore_r.R`) |
| Lint tool pin | `scripts/ci/requirements-lint.txt` |
| Convenience environment declaration | `workflow/environment.yml` |

`workflow/environment.yml` is a convenience declaration, not a second authoritative lock. Do not
substitute project metadata or a historical UI environment for the production pipeline lock. The
report image installs the lock and runs `uv pip check`; it asserts the pinned pandas version.

## Data version

Committed FOPH exports live under `data/reference/`; each dataset directory carries `retrieval.json`
with the source URL, retrieval time, byte hashes and row count. The publisher updates weekly on
Wednesdays and may revise recent counts. Reports record the content-addressed snapshot id computed
from the exact input files, not the publisher's "latest" claim. Attribution and terms:
[data/README.md](../data/README.md).

Acquisition is a separate step: `src/sync_idd_exports.py` (weekly workflow
`.github/workflows/refresh-idd-data.yml`, or `docker compose run --rm sync`). Report generation
itself never fetches new IDD data.

## Provenance in every output

Each canonical report embeds a JSON record (`<script id="report-provenance">`) and writes a sidecar
next to the page:

- source identity and the captured snapshot id;
- filters (geography, years) and effective stakeholder parameters;
- software versions (Python, R, Quarto) and generation timestamp in UTC;
- shared-template path and hash, output format and document list.

`results/release.json` records artifact hashes and sizes, code-file hashes, Git state, runtime
versions and the release identity. Composed, custom and supplied-table outputs are outside
`results/release.json` and carry their own provenance files.

Verify a build without rendering:

```sh
python scripts/health_pipeline/check_outputs.py                 # audiences, provenance, presentations
python scripts/health_pipeline/verify_release.py --out results  # hashes, links, embedded provenance
python -m pytest -q                                             # in the report image
```

`check_outputs.py` confirms exactly one HTML report per configured audience, embedded and sidecar
provenance, and distinct presentations. `verify_release.py` fails on tampered artifacts, missing
anchors, broken links, remote assets or drift between embedded and sidecar records.

## Reproduce an archived release

A snapshot manifest pins the exact inputs used by an earlier build:

```sh
snakemake --cores 2 --config snapshot_manifest=results/snapshots/<id>/manifest.json out=reproduced/archived
```

The archived inputs are verified before use; a mismatch stops the build. Use the same code revision,
configuration and runtime versions as the release you are reproducing. To package a result set for
transfer or later verification:

```sh
python scripts/health_pipeline/evidence_archive.py create \
  --include reproduced/tabular-example --output /tmp/report-evidence.tar.gz \
  --acknowledge-content-review
python scripts/health_pipeline/evidence_archive.py verify /tmp/report-evidence.tar.gz
```

`create` requires the explicit content-review acknowledgement and a clean source worktree: commit or
stash local changes first. Include paths must stay under `reproduced/`, so place the result
directory there before archiving. `verify` checks the archive's hashes and refuses a modified or
unexpected member set. The tool does not depend on which renderer produced the result.

## Source identity for linked worktrees

A linked Git worktree stores its administration directory outside the checkout. When the report
container mounts only the checkout, the runtime cannot resolve `git`, so it records the source state
as unknown. Record the identity on the host and let the runtime verify it:

```sh
python3 scripts/health_pipeline/source_identity.py collect \
  --out reproduced/source-identity-<UTC>.json
docker compose run --rm \
  -e HEALTH_REPORT_SOURCE_IDENTITY=/app/reproduced/source-identity-<UTC>.json \
  report snakemake --cores 2
```

`--config source_identity=<path>` is equivalent for direct Snakemake runs; `publish.py` and
`release.py` accept `--source-identity` for hand-driven renders. The collector uses only the
standard library.

The record separates what is verified from what is asserted:

- **Verified in the runtime:** every declared execution input (`Snakefile`, `.Rprofile`,
  `renv.lock`, `pyproject.toml`, `Dockerfile.report`, `scripts/`, `workflow/`, `src/`) is re-hashed
  and compared with the supplied path set, per-file digests, count and canonical digest. Added or
  removed inputs, symlinks and unreadable files fail the run.
- **Host-reported:** the commit, HEAD tree and staged/unstaged/untracked classification. The runtime
  has no Git object database and cannot prove that a commit describes these bytes.
- **Outside this claim:** data snapshots (recorded by snapshot id and bundle digests), dependency
  locks, the container image and external tools.
- **Boundary:** inputs are verified before provenance is written and again before publication. A
  later change, or a change to a file outside the declared inputs, is not observed. This is not
  complete source attestation.

An explicitly supplied record that is malformed, oversized, unreadable or mismatched fails with a
nonzero exit before any report or release is published. With no record supplied, the runtime records
its own Git observation or an honest unknown state.

Verify a record without rendering:

```sh
python3 scripts/health_pipeline/source_identity.py verify \
  --project . --identity reproduced/source-identity-<UTC>.json
```

## Release discipline

- Only a completed build plus matching `release.json` defines a release. A failed build can leave
  older reports in place; preserve earlier accepted artifacts separately and check the exit status.
- An unchanged successful build must produce a no-work dry run:
  `snakemake --dry-run --cores 1` reports "Nothing to be done".
- CI gates are `fast`, `secrets`, `container` and `full`. The `full` job builds every audience and
  uploads artifacts only after checks pass; CI does not deploy a production site. The `container`
  job additionally runs the `report_runtime` integration tests.
- Branch protection, tags, deployment and release publication are maintainer decisions outside this
  repository's code. Documented checks are not proof that branch protection is configured.
- Historical green checks are not evidence for a later commit.
