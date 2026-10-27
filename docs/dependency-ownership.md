# Dependency ownership and supported environments

## Decision

Keep the existing environment boundaries. M2 does not merge lock files,
regenerate dependency resolutions, upgrade packages, or alter runtime policy.

| File | Authority and scope | Principal consumer |
|---|---|---|
| `workflow/toolchain.json` | Authoritative runtime-version policy, not a package lock | Environment contracts and provenance |
| `scripts/health_pipeline/requirements.lock.txt` | Production Python pipeline dependency resolution | Native pipeline CI and `Dockerfile.report` |
| `scripts/health_pipeline/requirements.ui.in` | Direct input for the report-environment UI overlay | Overlay lock compilation |
| `scripts/health_pipeline/requirements.ui.lock.txt` | Resolved UI overlay constrained by the production pipeline lock | `Dockerfile.report` |
| `pyproject.toml` and `uv.lock` | Separate optional Marimo/connector project environment | `Dockerfile`, using `uv sync --locked` |
| `renv.lock` | R dependency record used by project restoration | `workflow/restore_r.R` and `Dockerfile.report` |
| `scripts/ci/requirements-lint.txt` | Pinned lint tool, separate from report dependencies | Validation CI |
| `workflow/environment.yml` | Alternative convenience environment; not another authoritative lock | Native setup |

## Report environment

`Dockerfile.report` installs the pipeline lock first, then the UI overlay
into the same report virtual environment. The overlay header records its
compilation command and the production lock used as a constraint.

The image currently includes Marimo. That does not make a GitHub account or
the optional connector necessary for local report generation. Removal of
the overlay from the report image is a separate design/validation change,
not part of this cleanup.

Packages shared by the pipeline lock and overlay must retain the same pinned
versions. The image also runs dependency consistency checks. Static lock
agreement tests do not substitute for successful installation and image tests.

## Optional UI environment

The `pyproject.toml` / `uv.lock` environment has its own dependency resolution.
Do not install it over the report environment or treat its package versions
as replacements for the production pipeline lock. Shared runtime policy does
not require identical package versions in isolated environments.

`Dockerfile` runs `uv sync --locked`; `Dockerfile.report` uses the two
requirements locks instead. Keep these installation paths distinct.

## Change ownership

A pipeline dependency change requires review of the production resolution,
the constrained overlay where affected, installation checks, analysis
regressions and full report validation. An optional UI dependency change
requires its own lock and environment checks.

Runtime changes must follow `workflow/toolchain.json` and its environment
contract tests. R changes must use the project's restoration process and
render/smoke validation. Do not hand-edit generated package hashes merely
to satisfy a test.

M2 leaves all existing lock bytes and runtime declarations unchanged.
Dependency-owner roles describe technical scope, not named people or
invented approval responsibilities.
