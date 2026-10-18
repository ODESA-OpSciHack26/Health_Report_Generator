# Data contract: the cleaned table and its companions

The reports read only these files in `results/`. All CSVs are UTF-8, comma-delimited, with one header row. Empty numeric fields mean missing, never zero.

## harmonised.parquet / harmonised.csv

One row is one value for one dataset, measure, period, place and subgroup. `harmonise.py` writes the Parquet file; `export_csv.py` writes the same rows as CSV for the reports.

| Column | Type | Meaning |
|---|---|---|
| `dataset_id` | string | `<topic>__<source_system>__<data hash>_<metadata hash>` |
| `topic` | string | Disease or indicator, e.g. `influenza`, `ehec` |
| `source_system` | string | e.g. `mandatory_reporting_system`, `sentinella_reporting_system` |
| `measure` | string | `cases`, `consultations`, or a comparison statistic such as `median_value_5y` |
| `period` | string | `2025`, `2025-M08` (month), `2026-W40` (week) |
| `period_type` | string | `year`, `month`, `iso_week`, `week`, `date` |
| `period_start` | datetime | First day of the period |
| `year` | integer | Calendar year of the period |
| `place`, `place_type` | string | e.g. `CHFL`/`CHFL`, `CH`/`country`, `ZH`/`canton` |
| `age_group`, `sex` | string | `all` for totals |
| `breakdown` | string | Other split, e.g. `testResult=positive`; empty if none |
| `value` | float | The published value |
| `pop` | float | Population denominator |
| `incValue` | float | FOPH's published rate per 100,000 |
| `prct` | float | Published percentage, where the dataset has one |
| `is_total` | bool | Every grouping column is at its "all" value |
| `is_stat_row` | bool | The row is a comparison statistic (min/median/max), not a count |
| `data_complete` | string | The publisher's completeness flag |
| `invalid_value` | bool | The raw value could not be read as a number |
| `groups_json` | string | The original grouping values |
| `source_file`, `source_row` | string, integer | Raw file (relative to the snapshot) and its CSV record number (header = 1) |
| `sha256`, `metadata_sha256`, `snapshot_id` | string | Checksums of the raw data and metadata, and the snapshot they came from |

## Companion files

| File | Content |
|---|---|
| `datasets.csv` | One row per raw file: checksums, topic, source system, publishing date, rows, `status` (`ok`, `duplicate_skipped`, `quarantined`) and detail |
| `checks.csv` | One row per quality check: `dataset_id`, `check`, `status` (`PASS`, `WARN`, `SKIP`, `FAIL`), `detail` |
| `validated.json` | Success marker written only when no check failed; bound to the checked content |
| `harmonised_snapshot.json`, `snapshot.json` | Snapshot id and the checksum of every raw file |
| `role_log.csv` | How each raw column was classified (time, place, group, value) |

Quality rules: [docs/scientific-policy.md](../../docs/scientific-policy.md).
