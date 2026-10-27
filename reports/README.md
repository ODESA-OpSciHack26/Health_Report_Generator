# Report templates

Each `.qmd` file in this folder is one report. Edit it to change what the report says and shows. The `utils/` folder holds the code and styles the templates use; most changes do not need it.

| Template | Report | Who it is for |
|---|---|---|
| [researcher.qmd](researcher.qmd) | Data report on the FOPH data: methods, quality checks, every series, trends, seasonality, age, cantons | Researchers |
| [public_health.qmd](public_health.qmd) | Situation report on the FOPH data: what is above its usual level now, and where | Public health officials |
| [general.qmd](general.qmd) | Report on any table uploaded on the home page; one file writes both views | Both |

## What to edit, and where

| To change… | Edit |
|---|---|
| Text, headings, explanations, limitations | The template: it is ordinary Markdown between the code blocks |
| The order of the sections, or remove one | The template: move or delete the `## Heading`, its text and its code block together |
| Which table or chart a section shows | The template: the code block under that heading |
| Report title, subtitle, table of contents | The settings block at the very top of the template (between the `---` lines) |
| Colours, summary cards, badges, table style | [utils/style.css](utils/style.css) (FOPH reports), [utils/general_style.css](utils/general_style.css) (general report) |
| Chart and map colours | `BLUE`, `MAP_RAMP` and `MAP_RAMP_MULTI` in [utils/helpers.py](utils/helpers.py) |
| Disease names and groups | `ALL_DISEASES` in [utils/helpers.py](utils/helpers.py); the home page reads the same list |
| When a disease counts as "Above normal" or "Record high" | `level()` in [utils/helpers.py](utils/helpers.py). Update the *Methods* text in the templates and [docs/scientific-policy.md](../docs/scientific-policy.md) to match |

## Code blocks

A code block starts with a line ` ```{python} ` and ends with ` ``` `. Keep both lines when you edit one. In the FOPH reports:

- `d` is the cleaned table and `st` the current status of every disease (one row each); `above` holds the diseases above their usual level, `record` those at a record high.
- `h.` calls a function in `utils/helpers.py`, for example `h.trend_figure(...)` or `h.canton_map(d)`.
- `show(table)` prints a table, `num(x)` and `pct(x)` format numbers, and `status_badge(...)` makes a coloured status label.
- `display(Markdown(f"..."))` writes text that contains numbers from the data.

The researcher report shows its code to readers under *Show code*; the other reports hide it.

## See your change

Start the home page (`start.bat`, or `./start.sh` on macOS and Linux) and click **Generate report**, or build both full reports into `results/site/` with:

```
docker compose run --rm report
```

No image rebuild is needed: the container reads this folder directly.

## The utils folder

| File | What it does |
|---|---|
| `helpers.py` | FOPH reports: disease list, loading the cleaned table, status against the comparison window, all charts and the map, table formatting |
| `general_helpers.py` | General report: loading the uploaded table, the reader's choices, its charts |
| `provenance.py` | The *Provenance* section and its JSON record |
| `style.css`, `general_style.css` | Look of the reports |
| `swiss_cantons.geojson` | Canton boundaries for the map |
| `index.html` | Landing page that links the built reports |
| `requirements.txt` | Locked Python packages the reports need |

Every file here is copied next to the template when a report is built, so a new helper file can be imported by name. A new FOPH report is a new `.qmd` here, its name under `reports` in [workflow/config.yaml](../workflow/config.yaml) and, to offer it on the home page, an entry in `STAKEHOLDERS` in [src/app.py](../src/app.py).
