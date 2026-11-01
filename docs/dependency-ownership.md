# Dependency ownership and supported environments

## Authoritative files

| File | Role |
|---|---|
| `workflow/toolchain.json` | Declared runtime-version policy |
| `scripts/health_pipeline/requirements.lock.txt` | Production Python dependency resolution |
| `pyproject.toml` | Project metadata and Ruff/pytest configuration; not a runtime installer |
| `renv.lock` | R dependency record consumed by project restoration |
| `scripts/ci/requirements-lint.txt` | Separate pinned lint dependency |
| `workflow/environment.yml` | Convenience environment, not an additional authoritative lock |

## Report runtime

`Dockerfile.report` installs the production Python lock and checks dependency
consistency, required executables and the pandas version. It retains R,
Quarto and TinyTeX. Python package downloads use a BuildKit cache mount.

The local and GitHub-backed Marimo interfaces are retired. Their Dockerfile,
project lock and report-environment UI overlay are removed. Do not use
`uv sync` as a substitute for installing the production pipeline lock.

The project dependency list is intentionally empty. This does not mean the
application has no dependencies: install the reporting environment through
the documented pipeline lock and runtime setup.

## Cache compatibility

Custom-report cache version 2 fingerprints `Dockerfile.report` instead of the
retired UI overlay lock. New requests receive new keys. Existing version-1
cache entries and report provenance are not rewritten or deleted.

This is cache invalidation, not a claim that historical reports were generated
under the new environment. Reproduce older outputs with their recorded source
revision and runtime.

## Validation and changes

Keep package versions and runtime declarations unchanged during structural
cleanup. Change locks deliberately, not by editing generated hashes to satisfy
tests. Validate installation, scientific results, provenance and rendering.

The no-Marimo comparison runtime passed the earlier automated suite and the
three-audience supplied-table HTML rendering/verification check. Subsequent
source cleanup requires fresh tests. Four Node-dependent DOM tests were not
exercised in that runtime. Browser, full PDF and packaged-app acceptance remain
separate checks.
