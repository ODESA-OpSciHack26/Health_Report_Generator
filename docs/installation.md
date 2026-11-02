# Installation and setup

Run every command from the repository root, which contains `Snakefile`. The authoritative version
policy is `workflow/toolchain.json`: Python 3.11.6, R 4.3.2, Quarto 1.3.353, uv 0.8.14 and
checksum-pinned TinyTeX 2026.10.

## Recommended: Docker Compose

Prerequisites: Docker with a reachable daemon, Docker Compose, and a Linux/amd64 host or emulation.
Native Windows and other architectures have not been validated.

```sh
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
docker compose build report
docker compose run --rm report snakemake --cores 2
```

`docker compose build` downloads software and restores pinned R packages; report generation itself
reads `data/reference/` and needs no network access. `Dockerfile.report` is the only supported
image.

The Compose file also defines `sync`, which runs the separate data-acquisition step
(`src/sync_idd_exports.py`). It is not part of report generation:

```sh
docker compose run --rm sync
```

Partial targets are available when you do not need a complete release:

```sh
docker compose run --rm report snakemake tables --cores 2
docker compose run --rm report snakemake html --cores 2
docker compose run --rm report snakemake pdf --cores 2
docker compose run --rm report snakemake shiny --cores 2
```

A partial target does not establish that a complete release works.

## Alternative: native environment

Use a dedicated pipeline environment with the production lock. Do not substitute project metadata
or a historical UI environment for it.

```sh
uv venv --python 3.11.6 .venv-pipeline
uv pip install --python .venv-pipeline/bin/python \
  -r scripts/health_pipeline/requirements.lock.txt
Rscript workflow/restore_r.R
```

Quarto and a TeX distribution are still required for PDF output. Install the declared Quarto
version, and inspect `scripts/ci/install_tinytex.sh` before running it — it replaces
`$HOME/.TinyTeX`:

```sh
bash scripts/ci/install_tinytex.sh 2026.10
export PATH="$HOME/.TinyTeX/bin/x86_64-linux:$PATH"
.venv-pipeline/bin/python -m snakemake --cores 2
```

The installer verifies the archive digest and required KOMA-Script class. Quarto's automatic TeX
package installation is disabled in the template.

## One-command wrapper

In the configured native environment:

```sh
bash scripts/health_pipeline/run_all.sh            # data/reference -> results
bash scripts/health_pipeline/run_all.sh data/reference out
```

The first argument overrides `data_root`, the second overrides `out`; `CORES` defaults to 2 and
`QUARTO` overrides the renderer path.

## Local composer

The composer is a separate local web application and needs the same Python dependencies, R
libraries and Quarto:

```sh
.venv-pipeline/bin/python -m snakemake tables --cores 2
.venv-pipeline/bin/python src/composer_site.py \
  --work-root "$HOME/.local/state/health-report-composer" \
  --inputs-root results/reports --data-root data/reference
```

See [composer](composer.md) for the access-token flow, input layout and limitations.

## Checking the installation

```sh
docker compose run --rm report python -m pytest -q --strict-markers -m "not report_runtime"
docker compose run --rm report snakemake --dry-run --cores 1
```

The full suite, including report-runtime and presentation tests, needs the report image:

```sh
docker compose run --rm report python -m pytest -q
```

If setup fails, see [troubleshooting](troubleshooting.md).
