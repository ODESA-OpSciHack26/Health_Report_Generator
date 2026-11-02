# Local report composer

The experimental composer is a local browser application for preparing report
compositions and generating report packages. It supports captured health-report
inputs and a neutral CSV workflow.

The former GitHub-backed interface and host-local Marimo form are retired.
A GitHub token is not the composer's local access credential. The custom-report
CLI and its cache remain available; the canonical pipeline and supplied-table
routes are unaffected.

## Requirements

Run from the repository root in a configured reporting environment. Python alone
is not sufficient for report generation: rendering also requires the project's
Python dependencies, R libraries and Quarto.

See [installation](installation.md) and
[reproducibility](reproducibility.md). The authoritative runtime contract
is `workflow/toolchain.json`; use the appropriate dependency locks rather than
installing arbitrary latest versions.

The former Compose `ui` service has been removed. There is currently no
composer service in `compose.yaml`; use the native launch command below.

## Start the service

For the native pipeline environment described in the [installation guide](installation.md):

```bash
.venv-pipeline/bin/python src/composer_site.py \
  --work-root "$HOME/.local/state/health-report-composer"
```

This command assumes that environment and its rendering dependencies already exist.
It is not a fresh-install command.

The default address is:

```text
http://127.0.0.1:2719/
```

The server accepts only `127.0.0.1` or `localhost` as its bind address. Do not
publish it as a network service or use it as a patient-data hosting service.

The default input paths are `/inputs/reports` and `/inputs`. These are environment
defaults, not directories automatically supplied by a fresh clone. Health-report
operation requires appropriately prepared inputs. The command above is not a
claim that a fresh installation or all input routes have been validated.

## Open the authenticated page

At startup the server prints its address and the path to a local access-token
file. It does not print the token itself.

The file is:

```text
<work-root>/access-token.txt
```

Its permissions are set to owner read/write only. Open the URL in a private local
browser session, replacing the placeholder with the file's contents:

```text
http://127.0.0.1:2719/?token=<local-access-token>
```

This is a local service credential, not a GitHub personal access token. Do not
share it, include it in screenshots, commit it, or publish a URL containing it.
Treat browser history containing the URL as sensitive.

## Command-line settings

| Option | Environment variable | Default |
|---|---|---|
| `--host` | `COMPOSER_BIND` | `127.0.0.1` |
| `--port` | `COMPOSER_PORT` | `2719` |
| `--work-root` | `COMPOSER_WORK_ROOT` | `results/workbench` under the checkout |
| `--inputs-root` | `COMPOSER_INPUTS_ROOT` | `/inputs/reports` |
| `--data-root` | `COMPOSER_DATA_ROOT` | `/inputs` |
| `--recipes-root` | `COMPOSER_RECIPES_ROOT` | `scripts/health_pipeline/config/composer/compositions` |
| `--workflow-config` | `COMPOSER_WORKFLOW_CONFIG` | `workflow/config.yaml` |

Command-line options override their environment defaults.

Keep the work root in persistent storage outside the source checkout if you want
to replace or update the checkout without deleting your working state. Back it
up separately: cloning the source repository does not recover local user state.

## CSV workflow

1. Upload a supported CSV dataset and review its structural preview.
2. Review and explicitly confirm the interpretation before generation.
3. Configure the supported report sections and presentation settings.
4. Generate the report and review its data, methods and limitations.
5. Retain the complete generated package and its reproduction information.

Do not treat visual presentation settings as permission to change analytical
meaning. Where the application requires an explicit analysis update or
confirmation, complete that step rather than bypassing it.

Supported generic scope remains limited. Multi-measure, ungrouped/count modes,
new-profile workflows, dataset replacement and batch extensions are not
advertised as completed features.

## Health-report workflow

Health presets use saved inputs for their corresponding audiences. Prepared
health-input setup is required; selecting a preset must not be treated as an
automatic acquisition of fresh source data.

The server resolves each health bundle as:

```text
<inputs-root>/<audience>/data/
```

Here `<audience>` is `researcher`, `health_institution` or `public`.
Maintained recipes are resolved as `<recipes-root>/<audience>.json`.
Set `--inputs-root` to the parent containing those audience directories,
not to an individual `data/` directory. Startup does not create these bundles.
The complete bundle-preparation and validation procedure still needs
to be verified before this guide can serve as an end-to-end quick start.

The standard audience choices are researcher, health institution and public.
Custom composition is an editing mode, not a fourth stakeholder identity.

## Current limitations

- Structural CSV preview: first 100 records and 20 columns; no paging.
- Long preview cells: complete text is available through title tooltips.
- Saved-report history: newest 20 entries; no further pagination.
- Status presentation is not fully unified.
- Some health-source dates are unavailable where not recorded in the source bundle.
- Generic PDF/static parity is not established.
- Scoped visual review is not broad accessibility or cross-browser acceptance.

The composer is experimental. Publication of its source is not evidence of
clinical validity, production security acceptance or complete scientific review.

## Reproduction and verification

Preserve the complete report package, recorded data identities, parameters,
software versions and reproduction material.

Use the matching code and runtime when reproducing historical outputs.
Do not expect forced rerenders to be byte-identical when generation timestamps
change. Do not edit provenance to make an older output appear newly generated.

See [reproducibility](reproducibility.md),
[report generation](report-generation.md#methods-and-scientific-policy)
and [limitations](limitations.md).

## Stop the service

Press `Ctrl+C` in the terminal running the composer. Do not delete the work root
as part of stopping the service.
