# Troubleshooting

Start with the diagnostic commands, then match the symptom. Commands assume the repository root.

```sh
docker compose run --rm report python -m pytest -q --strict-markers -m "not report_runtime"
docker compose run --rm report snakemake --dry-run --cores 1
docker compose run --rm report python scripts/health_pipeline/check_outputs.py --out results
docker compose run --rm report python scripts/health_pipeline/verify_release.py --out results
```

## Setup and environment

**`docker compose build` fails or is very slow.** The report image restores pinned R packages and
Quarto/TinyTeX; the first build downloads a lot. Ensure the daemon is reachable, the host is
Linux/amd64 (or emulation is configured), and the network allows the pinned sources. Report
generation after the build needs no network.

**`Rscript: not found`, missing R packages, or `renv` errors.** Use the report image, or restore the
pinned R library with `Rscript workflow/restore_r.R`. Do not install arbitrary latest R packages:
`renv.lock` is the resolution.

**PDF target fails with missing LaTeX classes.** Install the pinned TeX bundle
(`bash scripts/ci/install_tinytex.sh 2026.10`) and put `$HOME/.TinyTeX/bin/x86_64-linux` on `PATH`.
The installer replaces `$HOME/.TinyTeX`; inspect it before running. Quarto's automatic TeX
installation is disabled in the template.

**`snakemake` cannot be found or imports fail.** Use the pipeline environment created from
`scripts/health_pipeline/requirements.lock.txt`. Activating an unrelated virtualenv reproduces
neither the versions nor the flags the workflow expects.

**`Permission denied: .snakemake`** inside a container: the mounted checkout is not writable by the
container user. Export `LOCAL_UID`/`LOCAL_GID`, or make the disposable copy writable. Never make a
shared production checkout world-writable.

## Generation and data

**`No raw datasets in <root>`.** `data_root` does not contain the expected `data.csv` files. Use
`data/reference`, or pass `--config data_root=<dir>`; do not point it at `results/`.

**A quality check fails the build.** The blocking gate stops analysis with the failing rule and
dataset named. Fix or exclude the dataset through supported settings — do not bypass the gate.

**`Source bytes differ from the checksum-pinned request` (supplied table).** The CSV/TSV no longer
matches `source_sha256` in the request file. Regenerate the request for the intended bytes; do not
edit the digest to match a changed file.

**`Unsupported tabular renderer` or `invalid choice: 'python'`.** Only the R/Quarto renderer is
supported in this release. Omit `--renderer`, or pass `--renderer r`. The tool never falls back
silently.

**`v2 artifacts were produced by the retired Python pilot renderer`.** Supplied-table reports made
by the old pilot renderer can be integrity-checked (`tabular_run.py verify --output <dir>`) but their
source cannot be verified against this checkout, and this release cannot regenerate them. Rebuild
them with the R renderer if you need current provenance.

**`FileExistsError` on the output directory.** Supplied-table and composer renders never overwrite.
Choose a new destination; existing packages are left untouched on failure.

## Provenance and verification

**`verify_release.py` reports a hash or link mismatch.** The output tree was modified after
generation. Regenerate rather than editing artifacts; provenance is not meant to be patched.

**Embedded provenance differs from the sidecar.** A page was edited after rendering. Rebuild that
audience; the embedded record and sidecar are written together.

**"unknown" source state in provenance.** The runtime could not resolve Git (common in a linked
worktree mounted without its admin directory). Collect an identity on the host and pass it with
`HEALTH_REPORT_SOURCE_IDENTITY` or `--config source_identity=<path>`; see
[reproducibility](reproducibility.md#source-identity-for-linked-worktrees).

**A supplied identity is rejected.** Malformed, oversized or mismatched records fail before any
render by design. Verify the record with `source_identity.py verify` and recollect if the inputs
changed.

## Composer

**The page does not load or the token is rejected.** The server binds only `127.0.0.1`/`localhost`.
Read the access token from `<work-root>/access-token.txt`; it is intentionally not printed at
startup. Open the address the server prints, exactly.

**No inputs are listed.** Default input roots (`/inputs/reports`, `/inputs`) are environment
defaults, not directories created by a fresh clone. Pass `--inputs-root` pointing at the parent of
the audience directories.

**"A render is already running".** The composer runs one render at a time. Wait for the active job;
do not start a second server against the same work root.

**A render failed and no report appears.** Failed renders never replace an earlier package; read the
recorded error and retry into a new package.

## Documentation and CI

**A documented command is rejected.** The release documents the supported surface only. Options from
older development branches (pilot renderer selectors, retired interfaces) are intentionally absent.

**Link checks fail in tests.** `tests/test_docs_contract.py` and `tests/test_release_docs.py` verify
that documentation links resolve and that only the supported repository/branch identity appears.
Fix the link or the statement; do not delete the check.

**CI `fast` fails on a test that needs R or Quarto.** Such tests are either marked `report_runtime`
(container job) or must not be selected by the fast job. Do not move a runtime test into fast by
weakening its assertions.
