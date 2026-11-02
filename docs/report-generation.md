# Report generation

Every report is rendered by R and Quarto from one shared source. Audiences are parameter files,
not copies of the template. This page covers the supported routes, their outputs, configuration
examples and the methods policy behind the numbers.

## Routes and outputs

| Route | Entry point | HTML | PDF | Shiny app | `release.json` |
|---|---|---|---|---|---|
| Canonical pipeline | `snakemake --cores 2` | yes | yes | yes | yes |
| Supplied table | `tabular_run.py build` | yes | no | no | no |
| Composed batch | `publish.py batch` | yes | no | no | no |
| Custom request | `custom_report.py` | yes | no | no | no |
| Local composer | `src/composer_site.py` | yes (package) | no | no | no |

Do not infer capability across routes. A route that produces HTML does not thereby support PDF,
and composed or custom outputs are outside `results/release.json`.

## Canonical three-audience generation

One command builds every audience listed in `workflow/config.yaml`:

```sh
snakemake --cores 2                 # Docker: docker compose run --rm report snakemake --cores 2
bash scripts/health_pipeline/run_all.sh   # native wrapper, same command
```

Outputs per audience under `results/reports/<audience>/`:

```text
report.html  methods.html  report.pdf  methods.pdf
provenance.json  provenance.pdf.json
data/            (series, metrics, lineage, selection, sources, checks, snapshot, stakeholder…)
app/             (packaged Shiny application: app.R, report.qmd, helpers, CSS, data)
results/release.json
```

Partial targets: `snakemake tables|html|pdf|shiny --cores 2`. A partial target does not establish a
complete release.

### Configuration

`workflow/config.yaml`:

```yaml
data_root: data/reference   # committed inputs; override with --config data_root=<dir>
out: results                # output root
quarto: quarto              # renderer executable
source_identity: null       # optional host-collected identity record (JSON)
stakeholders:               # one shared template, one file per audience
  - researcher
  - health_institution
  - public
snapshot_manifest: null     # set to snapshots/<id>/manifest.json for archived reproduction
```

An audience is added by copying a file in `scripts/health_pipeline/config/stakeholders/`, setting a
unique `id` that matches the filename stem, changing validated communication settings, and listing
the id in `workflow/config.yaml`. No audience-specific QMD is needed. Standard release audiences
keep matching analytical scope; this is not a generic registry for arbitrary new methods.

### Scope controls in stakeholder files

`include_topics` (if present, only those validated topic identifiers are candidates) and
`exclude_topics` (removes topics from the analytical selection). Omitted fields preserve the
existing eligibility policy and the two lists may not overlap. Topic identifiers are validated
against `scripts/health_pipeline/config/pathogen_class.csv`, and every dataset keeps an explicit
selection reason. `exclude_from_group_totals`, `sensitivity_exclude` and
`classes_in_main_comparison` keep separate meanings.

Changing scope is an analysis change: regenerate the bundle through the canonical workflow. Rendering
a retained bundle only changes presentation.

## Composed audience reports (HTML-only)

Compose all three audience reports from their retained analysis bundles and recipes:

```sh
docker compose run --rm report python scripts/health_pipeline/publish.py batch \
  --bundle-root results/reports --output-root results/composed \
  --data-root /app/results/snapshots/<snapshot-id> \
  --workflow-config workflow/config.yaml
```

Recipes live in `scripts/health_pipeline/config/composer/compositions/<audience>.json` and must
declare that audience; a mismatch is refused rather than substituted. Outputs are
`results/composed/<audience>/report.html` plus `methods.html`, `provenance.json` (also embedded) and
a `data/` folder used by download links. Keep each folder together. The command exits nonzero if any
requested report fails; a partial run may leave other reports in place.

This is presentation-only: it re-renders saved bundles and never re-runs acquisition, harmonisation
or analysis. Passing `--composition` with PDF is rejected. Full analysis reproduction remains
`snakemake --cores 2`.

### Composition block contract

Recipes use `health-report/composition-recipe/2`. `reference-comparison` requires an explicit
`topic` bound to a saved included topic; contract v1 stays readable with its historical
deterministic binding. A recipe may include one `series-trend` block (`topic`, `measure`, optional
inclusive `years`, optional closed `presentation` with `style` `standard` or `compact`); a missing
year is a gap, not zero, and a second instance is refused. A `series-collection` block may replace
the single trend: `topics` is `"eligible"` or an explicit non-empty list, with one `measure`,
optional `years` and optional `{style, default_topic}`; each topic becomes a separately checked
series record with its own disclosure panel that works without JavaScript. A collection cannot be
combined with a single `series-trend`, and only one collection is allowed. Additionally one
`coverage-selection`, one `monitoring-overview` and one `sensitivity-comparison` may read saved
records. Every block selects among saved results and cannot broaden analytical scope; unknown or
excluded topics fail rather than being dropped.

## Supplied-table reports

Prepare one explicitly mapped UTF-8 CSV/TSV and render three audience HTML reports from the shared
source:

```sh
docker compose run --rm --no-deps report python scripts/health_pipeline/tabular_run.py build \
  --input examples/tabular/observations.csv \
  --request examples/tabular/request.json \
  --output reproduced/tabular-example
```

The request pins the source bytes (`source_sha256`), the column mapping, mode and period; the
checked-in example request matches the checked-in example CSV exactly. R/Quarto is the only
renderer: `--renderer r` is accepted (and is the default), and `--renderer python` fails with an
explicit "invalid choice" error. There is no fallback path.

Manual render from a prepared bundle:

```sh
python scripts/health_pipeline/tabular_render.py --bundle <bundle> --output <dir>
```

Verify an existing report set without rendering (checks artifacts, bundle, analysis and embedded
provenance):

```sh
python scripts/health_pipeline/tabular_run.py verify --output <dir>
```

Reports produced by the retired Python pilot renderer (`health-report/tabular-render/2`) can be
integrity-verified this way. Their recorded source cannot be verified from this checkout:
`--verify-source` fails explicitly for those artifacts instead of pretending to check them. This
release cannot regenerate Python-rendered artifacts.

## Custom reports

```sh
docker compose run --rm report python scripts/health_pipeline/custom_report.py \
  examples/request-2022-2025.json --out results/custom
```

The last line reports cache miss or hit, a SHA-256 key and the folder. Cache entries live in
`results/cache/custom_reports/`; the key covers request, snapshot, report code, toolchain and schema
version. This machine-local cache has no eviction. `--out` is replaced on each run — preserve an
earlier output or choose a fresh destination.

A request copied from `public.json` retains `reference_year`/`index_base_year` 2019 even when the
displayed years are 2022–2025; change both fields explicitly for another baseline.

## Methods and scientific policy

Rules that decide which data enter a report do not change with audience wording:

- **Quality gate.** Datasets pass blocking checks (schema, period completeness, denominators,
  overlap and metadata conflicts) before analysis; failures stop the build with a recorded reason.
  The methods page lists every check with status, rule and dataset filters.
- **Descriptive only.** Changes are percentage differences against a reference year. No
  significance tests, confidence intervals or causal claims are made.
- **Comparable audiences.** All three audiences use the same analytic parameters; only presentation,
  sections and wording differ, so findings agree across reports.
- **Uncertainty stays visible.** Every audience keeps headline, quality and sources sections; the
  public report keeps a "How sure can we be?" section.
- **Provenance is part of the output.** Snapshot id, filters, effective parameters, software
  versions and generation timestamp are embedded in the HTML and written as a sidecar.

Stakeholder files must pass `workflow/config.schema.json`. Unsupported geographies, periods,
classes, sections and unknown keys fail clearly; arbitrary new analyses need code and tests, not an
ignored configuration field. `config/stakeholders/public_health_expert.json` is retained as the
historical analytic base profile used by audience tests; it is not a fourth release audience.

## Verified example numbers

The committed reference data yield a +124% viral change for 2025 vs 2019 and +21% for the bacterial
group; excluding influenza the viral change is -3%. All three audience reports show those figures
with the same parameters, and the R smoke test asserts them against the stored analysis.
