# Reproduction guide

How to set up the toolchain, build all audience reports, and reproduce an archived release from recorded inputs and settings. This does not promise byte-identical rendered HTML or PDF files. The README has the short version; this is the full detail.

## Setup and run

Run commands from the repository root. The version policy is recorded in
`workflow/toolchain.json`: Python 3.11.6, R 4.3.2, Quarto 1.3.353,
uv 0.8.14, and checksum-pinned TinyTeX v2026.10.

### Recommended: Docker

The current report image targets Linux/amd64. Docker and Docker Compose
must be installed, and the Docker daemon must be reachable.

```sh
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
docker compose build report
docker compose run --rm report snakemake --cores 2
```

Image creation downloads software and restores packages.
The report command reads committed reference data and requires no GitHub
token, fork, or GitHub Actions. It does not perform an IDD data update.

`Dockerfile.report` provides the report environment.
The former optional UI Dockerfile and dependency environment are retired.

### Alternative: native setup

Install the declared R and Quarto versions and required TeX toolchain.
Use a dedicated pipeline environment with the production dependency lock:
Do not substitute project metadata or a historical UI environment for the production pipeline lock.

With uv installed:

```sh
uv venv --python 3.11.6 .venv-pipeline
uv pip install --python .venv-pipeline/bin/python \
  -r scripts/health_pipeline/requirements.lock.txt
Rscript workflow/restore_r.R
```

Inspect `scripts/ci/install_tinytex.sh` before running it:
it replaces `$HOME/.TinyTeX`. To intentionally install the pinned bundle:

```sh
bash scripts/ci/install_tinytex.sh 2026.10
export PATH="$HOME/.TinyTeX/bin/x86_64-linux:$PATH"
.venv-pipeline/bin/python -m snakemake --cores 2
```

The installer verifies the archive digest and required KOMA-Script class.
Quarto's automatic TeX package installation is disabled in the template.

### Targets and wrapper

For Docker, replace the final command with any partial target:

```sh
docker compose run --rm report snakemake tables --cores 2
docker compose run --rm report snakemake html --cores 2
docker compose run --rm report snakemake pdf --cores 2
docker compose run --rm report snakemake shiny --cores 2
```

Partial targets do not establish that a complete release works.

The native wrapper
`bash scripts/health_pipeline/run_all.sh [data_root] [out_dir] [extra snakemake args]`
runs Snakemake from PATH. Activate `.venv-pipeline` before using it:

```sh
source .venv-pipeline/bin/activate
bash scripts/health_pipeline/run_all.sh
```

Set `QUARTO` to override the renderer path and `CORES` to change parallelism.
See GETTING_STARTED.md for complete output and verification instructions.

## Reproduce a specific archived release

```sh
snakemake --cores 2 --config \
  snapshot_manifest=results/snapshots/REPLACE_WITH_SNAPSHOT_ID/manifest.json \
  out=reproduced
```

This mode verifies and reads only that archived snapshot, without requiring the live `data/reference/` tree or any API. Retain the snapshot **and** code/config/environment versions with the report. Hashes cannot recover deleted data. Paths inside a snapshot and its lineage are relative, so the archive can move between computers. Original source record numbers count CSV records (header = 1), not physical lines in multiline CSV fields.

For an update, place a new release in `data/reference/` and run the ordinary workflow. It creates a new content-addressed archive rather than replacing the old snapshot. The analysis uses the selected local inputs rather than acquiring new IDD data. This is not evidence of network isolation; software setup requires downloads. Acquisition from the public IDD API is a separate step: `src/sync_idd_exports.py` (run weekly by `.github/workflows/refresh-idd-data.yml`, or manually) downloads each export into `data/reference/<DATASET>/` together with a `retrieval.json` recording the source URLs, retrieval time and hashes; changes are committed so every release is a reviewable change to `data/reference/`.

## Verify a build

```sh
python scripts/health_pipeline/check_outputs.py
Rscript tests/shiny_smoke.R results/reports/researcher/app
python -m pytest -q
```

`check_outputs.py` confirms exactly one HTML report per configured audience, embedded and sidecar provenance, and distinct presentations. Compare `results/release.json` (artifact and code hashes, Git state, runtime versions) with the one you expect.

## Source identity for linked worktrees

A linked Git worktree stores its administration directory outside the checkout. When the
report container mounts only the checkout, the runtime cannot resolve `git`, so it records
the source state as unknown. Record the identity on the host and let the runtime verify it:

```sh
python3 scripts/health_pipeline/source_identity.py collect \
  --out reproduced/source-identity-<UTC>.json
docker compose run --rm \
  -e HEALTH_REPORT_SOURCE_IDENTITY=/app/reproduced/source-identity-<UTC>.json \
  report snakemake --cores 2
```

`--config source_identity=<path>` is equivalent for direct Snakemake runs, and
`publish.py`/`release.py` accept `--source-identity` for hand-driven renders. The collector
uses only the standard library, so it runs with the host Python rather than the report
environment.

The record separates what the runtime can verify from what it cannot:

- **Verified in the runtime:** every declared execution input (`Snakefile`, `.Rprofile`,
  `renv.lock`, `pyproject.toml`, `Dockerfile.report`, `scripts/`, `workflow/`, `src/`) is
  re-hashed and compared with the supplied path set, per-file digests, count and canonical
  digest. Files are hashed even when Git ignores them; symlinks, unreadable files and
  added or removed inputs fail the run.
- **Host-reported, an external assertion:** the commit, HEAD tree and the
  staged/unstaged/untracked classification. The runtime has no Git object database, so it
  cannot prove that a commit describes these bytes.
- **Outside this content claim:** data snapshots (recorded by snapshot id and bundle
  digests), dependency locks, the container image and external tools (recorded separately).
- **Boundary:** inputs are verified before provenance is written and again before the
  report is published. A change between those points fails the render; a change after the
  final check, or a file outside the declared inputs, is not observed. This is not complete
  source attestation.

An explicitly supplied record that is malformed, oversized, unreadable or mismatched fails
the generation with a nonzero exit before any report or release is published. When no
record is supplied, the runtime records its own Git observation or an honest unknown state.
Untracked files outside the declared inputs are counted and named as outside the content
claim; the worktree is not described as unconditionally clean. The published provenance
carries commit, counts and content digest only; detailed path lists stay in the local
identity file. Historical packages without these fields remain readable and are never
backfilled. The supplied-table route does not record source identity in this slice.

Verify a record without rendering:

```sh
python3 scripts/health_pipeline/source_identity.py verify \
  --project . --identity reproduced/source-identity-<UTC>.json
```

## Integration handover and optional local form

See [handover](handover.md) for the recorded integration baseline,
validation identities, retained evidence and remaining acceptance limits.
The [local browser form](local-interface.md) uses the separate locked UI
environment on the host and invokes the Docker report service.
It does not replace the standard three-audience release build.
