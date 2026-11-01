# R-free supplied-table pilot (experimental)

Status: experimental pilot on `experiment/rfree-tabular-pilot`; not a product release and not a
claim that the product is R-free. The default renderer for the supplied-table route remains R.

## Scope

- Route: supplied-table HTML only, three audiences (`researcher`, `health_institution`, `public`).
- Selection: `--renderer python` is explicit. `--renderer r` remains the default. There is no
  fallback from Python to R; a missing pilot dependency is an actionable error.
- Everything else remains on R: canonical HTML/PDF, custom/selected reports, composer health and
  neutral CSV, the Shiny app, R smokes and the production image.

## Experimental dependency ownership

- `scripts/health_pipeline/requirements.pilot.in` is the pilot input: the production lock plus
  `matplotlib==3.11.2`.
- `scripts/health_pipeline/requirements.pilot.lock.txt` is the frozen resolution generated during
  the pilot preparation step. `Dockerfile.report.pilot` installs only this frozen file.
- Production `requirements.lock.txt`, `Dockerfile.report`, `compose.yaml` and CI are unchanged.
  The pilot image tag is `health-report:rfree-pilot`; it contains no R, renv, Rscript, knitr or
  TeX. The base tag names Python 3.11.6; the resolved base digest is recorded in the pilot
  evidence and must be pinned before an acceptance build.

## Commands

```sh
docker build --file Dockerfile.report.pilot --tag health-report:rfree-pilot .
docker run --rm --volume "$PWD:/app" --workdir /app health-report:rfree-pilot \
  python scripts/health_pipeline/tabular_run.py build \
    --input tests/fixtures/tabular/f1_ordinary.csv \
    --request tests/fixtures/tabular/f1_ordinary.request.json \
    --output reproduced/pilot-candidate/f1 --renderer python \
    --source-identity /app/reproduced/<identity>.json
docker run --rm --volume "$PWD:/app" --workdir /app health-report:rfree-pilot \
  python scripts/health_pipeline/tabular_run.py verify --output reproduced/pilot-candidate/f1
```

`verify` checks saved-package integrity and schema without requiring the original checkout.
`verify --verify-source` additionally rebuilds the renderer/environment record and compares the
recorded source-content digest with the current checkout. Replay still requires a matching
checkout and the original input/snapshot; package-only rendering is not claimed.

## Provenance

Python candidate outputs use `health-report/tabular-render/2`: the v1 fields plus
`code.source_identity` (P1 public summary), `code.renderer` (entry point and file hashes) and
`code.environment` (base/pilot lock hashes, Python, Quarto and matplotlib versions). v1 packages
keep their original schema and verifier behaviour and are never backfilled.

## Exit criteria

Automated parity for the fixture matrix, no-R execution evidence, package integrity and replay,
measured image/build/storage effects, and a human visual-review checklist. A human reviewer must
accept the visual result before any default switch or R retirement; neither is authorized by this
pilot. See the branch evidence under `reproduced/` (gitignored).
