# Opt-in tabular preparation contract

`prepare_table(source, *, mapping, mode, period)` is an internal, in-memory
API. It is not connected to the default workflow, renderer or UI.

## Explicit parameters

- `mapping`: category and measure source-column names; also time for time series.
- `mode`: snapshot or timeseries.
- `period`: None for snapshots; year, month, week or day for time series.
- Mapped roles must name distinct existing columns.
- No aggregation is performed, including after period normalization.

## Input and output identity

The source is read once. Structural validation, parsing and the input checksum
use that same captured byte sequence. The result contains the prepared table,
machine-readable provenance and original bytes. Source order and data rows
are retained; empty CSV records are excluded consistently with inspection.

Output columns are category, value and period. Source columns not selected by
the mapping are not copied into the prepared table; original bytes are retained.

## Missingness and interpretation

Only empty or whitespace-only fields become missing. Literal NA/null tokens
are not automatically missing. Invalid or non-finite measures and invalid,
non-missing dates raise errors. Negative values are permitted without claiming
they are scientifically appropriate. Dates are timezone-naive; weeks start
Monday. Snapshots do not acquire fabricated observation dates.

Numeric precision follows pandas, not an exact-decimal contract. No disease
classification, denominator, rate calculation or causal interpretation occurs.

## Provenance and limitations

Provenance records input identity, effective parameters, no filters or
aggregation, row counts, missingness, UTC preparation time, Python/pandas
versions and code-file hashes. Code hashes describe files on disk, not a Git
attestation. Returned objects are mutable and are not verified publications.

This API publishes no files, does not impose upload-size limits and has not
passed upload-security, browser or report-release acceptance. Future
publication must bind the prepared data to provenance and existing gates.
