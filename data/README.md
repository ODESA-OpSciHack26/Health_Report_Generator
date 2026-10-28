# Data directories

## Canonical live source

`data/reference/` is the only active source-data root. It is the default in `workflow/config.yaml`, and CI uses that default without an override. The directory contains the broader synchronized IDD reference collection and associated publisher metadata.

Treat each update as a new source release. Do not edit files in place without retaining their source metadata and recording the resulting content-addressed snapshot.

## Retired legacy source

The frozen `Data/` release was removed in Phase 4 after the canonical-root migration passed full push and pull-request CI. It is not an accepted runtime input and must not be recreated.

The machine-readable disposition of every former legacy dataset directory remains recorded in `docs/phase-3-data-migration.json`. `docs/phase-4-legacy-removal.json` records the removal gate and deletion commit. Git history and the Phase 0 snapshot ID preserve the previous state for audit and recovery.

## Generated data

The pipeline writes generated snapshots, harmonised data, checks, analysis bundles, and reports under `results/` by default. Generated results are ignored by Git and must not be manually promoted to source data.

## Migration safety

Canonicalization was a source-release change, not a byte-preserving rename. The two roots had different publisher dates and file hashes. Their selected reports had the same row counts and topic set, but some 2022–2025 values and 2025 population denominators differed. Those differences remain documented in `docs/phase-3-data-migration.json` and must not be described as simple deduplication.

The removal is reversible through Git history, but restoration is not part of the supported production workflow. Any proposed restoration must explain why the older source release is scientifically required and must use a distinct archival path rather than reintroducing an ambiguous active root.

## Source, terms and acquisition

- **Publisher:** Federal Office of Public Health (FOPH/BAG), Infectious Diseases Dashboard (IDD), <https://www.idd.bag.admin.ch/>.
- **Terms:** the FOPH states the data are publicly accessible and may be used with proper source attribution ([IDD data page](https://www.idd.bag.admin.ch/en/portal-data)). Attribute the FOPH when redistributing reports or data. No separate licence text is given on that page.
- **Acquisition:** `src/sync_idd_exports.py` downloads `https://api.idd.bag.admin.ch/api/v1/export/latest/<DATASET>/csv` and `/metadata`, and writes `retrieval.json` (source URLs, retrieval time, hashes, row count) beside each export. The publisher updates weekly on Wednesdays; the scheduled workflow commits changes to `data/reference/`.
- **Layout:** `data/reference/<DATASET>/{data.csv, metadata.json, retrieval.json}`; committed to Git.
- **Version in a report:** each report's `provenance.json` lists snapshot id, publisher release dates and retrieval dates.

## Project licence

The project software is licensed under the MIT License. The tracked [LICENSE](../LICENSE)
file holds the operative terms; [release-checklist.md](../docs/release-checklist.md)
records how releases treat it. The source-data terms above are separate from that
software licence: the MIT License does not license the source data, attribution to the
FOPH is still required when redistributing reports or data, and the publisher publishes
no separate licence text for the data.
