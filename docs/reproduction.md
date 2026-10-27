# Reproduction guide

How to set up the toolchain, build the reports, and reproduce an archived build exactly. The README has the short version; this is the full detail.

## Setup and run

Run commands from the repository root. The version policy is recorded in
`workflow/toolchain.json`: Python 3.11.18, Quarto 1.10.19 and uv 0.8.14.

### Recommended: Docker

The report image is built for the computer's own processor: amd64 (Windows, Linux,
Intel Mac) or arm64 (Apple-chip Mac). Docker and Docker Compose must be
installed, and the Docker daemon must be reachable.

```sh
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
docker compose build report
docker compose run --rm report          # snakemake --cores 2
```

Building the image downloads software. The report command reads committed
reference data and requires no GitHub token. It does not download new IDD data.
The same image runs the web page (`docker compose up app`).

### Alternative: native setup

Install [Quarto 1.10.19](https://quarto.org/docs/download/) and
[uv](https://docs.astral.sh/uv/). Then:

```sh
uv venv --python 3.11.18 .venv-pipeline
uv pip install --python .venv-pipeline/bin/python -r scripts/health_pipeline/requirements.txt
.venv-pipeline/bin/python -m snakemake --cores 2
```

On Windows use `.venv-pipeline\Scripts\python.exe`.

### One report with a selection

```sh
python scripts/health_pipeline/render_quarto.py --report researcher --results results \
  --output results/site/researcher-2019-2025.html --data-root data/reference \
  --years 2019-2025 --topics influenza,ehec,campylobacteriosis
```

`--topics` keeps the order given; it sets the order of rows, panels and columns. The
cleaned table must exist first: `snakemake --cores 2 results/harmonised.csv`.

## Reproduce a specific archived build

```sh
snakemake --cores 2 --config \
  snapshot_manifest=results/snapshots/REPLACE_WITH_SNAPSHOT_ID/manifest.json \
  out=reproduced
```

This mode verifies and reads only that archived snapshot, without requiring the live `data/reference/` tree or any API. Retain the snapshot **and** the code, configuration and environment versions with the report. Hashes cannot recover deleted data. Paths inside a snapshot are relative, so the archive can move between computers.

For an update, place a new release in `data/reference/` and run the ordinary workflow. It creates a new content-addressed archive rather than replacing the old snapshot. Building never contacts the network. Downloading from the public IDD API is a separate step: `src/sync_idd_exports.py` (run weekly by `.github/workflows/refresh-idd-data.yml`, or `docker compose run --rm sync`) writes each export into `data/reference/<DATASET>/` together with a `retrieval.json` recording the source URLs, retrieval time and hashes; changes are committed so every data update is a reviewable change.

## Verify a build

```sh
python -m pytest -q
snakemake --dry-run --cores 1     # after a build: "Nothing to be done"
```

Each report's Provenance section, and `provenance_<report>.json` beside it, names the snapshot id, the SHA-256 of `harmonised.csv`, every raw file's checksum, the Git commit and the tool versions. Two builds from the same snapshot, code and toolchain give the same figures; only the render time differs.
