# Data directories

## Canonical live source

`data/reference/` is the only active source-data root. It is the default in `workflow/config.yaml`, and CI uses that default without an override. The directory contains the broader synchronized IDD reference collection and associated publisher metadata.

Treat each update as a new source release. Do not edit files in place without retaining their source metadata and recording the resulting content-addressed snapshot.

## Retired legacy source

An older `Data/` folder was retired; `data/reference/` replaced it. It is not an accepted input and must not be recreated. Git history keeps the earlier state.

## Generated data

The pipeline writes generated snapshots, the cleaned table, quality checks and reports under `results/` by default. Generated results are ignored by Git and must not be manually promoted to source data.

## Source, terms and acquisition

- **Publisher:** Federal Office of Public Health (FOPH/BAG), Infectious Diseases Dashboard (IDD), <https://www.idd.bag.admin.ch/>.
- **Terms:** the FOPH states the data are publicly accessible and may be used with proper source attribution ([IDD data page](https://www.idd.bag.admin.ch/en/portal-data)). Attribute the FOPH when redistributing reports or data. No separate licence text is given on that page.
- **Acquisition:** `src/sync_idd_exports.py` downloads `https://api.idd.bag.admin.ch/api/v1/export/latest/<DATASET>/csv` and `/metadata`, and writes `retrieval.json` (source URLs, retrieval time, hashes, row count) beside each export. The publisher updates weekly on Wednesdays; the scheduled workflow commits changes to `data/reference/`.
- **Layout:** `data/reference/<DATASET>/{data.csv, metadata.json, retrieval.json}`; committed to Git.
- **Version in a report:** each report's `provenance.json` lists snapshot id, publisher release dates and retrieval dates.

## Project licence

The repository does not yet state a project-wide licence; choosing one is a decision for the repository owner (see `docs/release-checklist.md`). Until then, no reuse rights are granted for the project code. The data terms above are independent of that choice.
