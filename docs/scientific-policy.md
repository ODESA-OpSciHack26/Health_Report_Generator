# Scientific policy and data contract

Rules that decide which data enter a report and how numbers are calculated.

## Quality rules (harmonise.py, checks.py)

- A subgroup is never inferred to be a total because it has one distinct value.
- Missing or malformed metadata and undescribed columns are quarantined; quarantine blocks the build until resolved.
- Deduplication requires identical data **and metadata** bytes. Same data with conflicting metadata is a blocking conflict.
- Counts must be numeric, finite, nonnegative and uniquely keyed. Year/month reconciliation uses a documented 2% tolerance only for complete compatible count series. Canton checks require exactly 26 Swiss cantons and a **CH** national total, never CHFL; tolerance is 5%. Nonapplicable checks are `SKIP`, not `PASS`.
- Geography is explicit (`CH` or `CHFL`); the workflow never silently substitutes one for the other.
- `checks.py` exits nonzero on critical failures and writes a success marker bound to the content it checked. Editing an input or output cannot silently reuse an old validation result, and no report is rendered from a table that has not passed.

## Report rules (reports/utils/helpers.py)

- **National series.** All ages, both sexes, no sub-type split. Switzerland plus Liechtenstein (CHFL) where published, otherwise Switzerland (CH). The COVID-19 case series counts laboratory-confirmed (positive-test) cases.
- **Period.** The finest published: weekly for respiratory series, monthly for most others, yearly for AIDS.
- **Comparison window.** Minimum, median and maximum of the same week or month in previous years: FOPH's published 5- or 10-year values where available, otherwise the previous 5 years of the series, requiring at least 3.
- **Level.** Record high: latest value at or above the window maximum. Above normal: at least 20% and at least 3 cases above the window median. Low: at or below the window minimum. Otherwise normal.
- **Recent change.** Weekly series: last 4 weeks against the previous 4. Monthly and yearly series: against the same period one year earlier.
- **Cantons.** Cases per 100,000 for the last full year, or the last 4 weeks for weekly series; cantons with fewer than 5 cases are not shaded.
- **Selections.** A reader can limit a report to some diseases and years. The years apply to the sections over time; the status and its comparison window always use the full data. Both choices are recorded in the report's Provenance.

Changing a rule means changing `helpers.py` with a matching update to the report's Methods section; do not describe descriptive changes as causal effects or statistical significance.

See [SCHEMA.md](../scripts/health_pipeline/SCHEMA.md) for the cleaned table's columns and types.
