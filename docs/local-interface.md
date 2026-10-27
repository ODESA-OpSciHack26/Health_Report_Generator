# Local report interface

This optional Marimo form runs on a trusted Linux/WSL host and invokes
the existing Docker Compose report service. It does not use GitHub artifact
downloads, credentials, or workflow dispatch. The GitHub-backed interface
in `src/ui.py` remains separate and unchanged.

## Setup and launch

Requirements: a local checkout, working Docker Compose access, and uv
installed on the host. Initial software installation requires internet.
From the repository root:

```sh
docker compose build report
uv sync --locked
uv run --locked marimo run src/local_ui.py --host 127.0.0.1 --port 2719
```

Keep the terminal running and use the local URL printed by Marimo.
Do not expose the server to a network or run it as a public service.
Do not use the existing `ui` Compose service for this host-side adapter.
Stop with Ctrl+C.

## Request and result

Choose one of four existing audience parameter sets and an inclusive
year range within 2021–2025. Geography remains CHFL; the comparison and
index baseline remain 2019. This form does not offer disease selection.

Each submission records its request and execution log under
`results/local-ui/runs/<unique-id>/`. Successful output is in that run's
`report/` folder. Open `report.html` from the local filesystem and retain
the complete folder. No report files are served by this form.

Rendering reuses `custom_report.py`, its validation, shared template,
and cache at `results/cache/custom_reports`. The form reports hit/miss
and cache identity only after the adapter checks the expected outputs.
A cached report retains its original rendering provenance and timestamp.
The backend substitutes a request-derived `custom_...` stakeholder ID.

The adapter serializes its own submissions using a host file lock.
Do not run the direct custom-report CLI concurrently against the same cache.
This is not a multi-user scheduler or hardened web service.

## Validation status

Unit tests mock container execution and exercise the submit cell.
They do not prove browser startup, widget operation, or real Docker
execution through this adapter. Record those checks separately before
claiming end-to-end success. Standard release outputs and release.json
are not modified by this custom-report route.

## Date-consistent wording

The local adapter regenerates the request title and question from the
selected years and the audience's existing comparison/index baselines.
It preserves all other source settings and does not modify the source
audience JSON files. Single-year requests use a single year in the wording.

Earlier local smoke runs revealed that copying the source question verbatim
could retain a 2025-specific question for a 2023–2024 request. Those earlier
outputs are diagnostic evidence, not the corrected implementation's outputs.
The corrected wording changes the request's cache identity; old cached
reports are preserved but are not reused for the corrected request.
