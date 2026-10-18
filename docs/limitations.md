# Limitations

The reports state the limits relevant to reading the numbers; this page adds the technical and project limits.

## Interpreting the data

- **Notifications are not infections.** Mandatory reports reflect testing and reporting behaviour, not true incidence. A rise can mean more disease, more testing, or both.
- **Sentinella figures are extrapolations** from a sample of GP practices.
- **Descriptive only.** No significance testing, modelling or forecasting is applied. Small counts can change level on a handful of cases.
- **Comparison windows include the current value** where FOPH publishes them (5- or 10-year minimum, median and maximum). They are comparison windows, not purely historical baselines.
- **COVID-19.** The computed 5-year comparison window spans pandemic years and is not a normal reference; "low" there is relative to an exceptional period.
- **Different periods.** Canton and age figures refer to the last full year (or the last 4 weeks for weekly series), not the same period as the national latest value.
- **Colours are visual cues** for the levels defined in the report's Methods; they are not a clinical risk classification.
- **Not analysed.** Lab positivity, wastewater and variant data are in the cleaned table but not in the reports.
- **Recent periods can be revised.** The publisher updates counts as late notifications arrive. The snapshot id pins exactly which release a report used.
- **Rates are FOPH's published rates** per 100,000, not recomputed.

## Year choice

- The years limit only the sections that show history. The current status always uses the newest data and its full comparison window; the report says so at the top.
- A year choice that ends before the newest data shows canton and age figures for the last chosen year where FOPH publishes them; some series only publish the most recent period or a long-term mean.

## Reproducibility

- **Reproduction means the same snapshot, code and toolchain.** Changed data give changed reports. Hashes cannot recover deleted inputs, so retain the snapshot folder.
- **Python packages are pinned** in `scripts/health_pipeline/requirements.lock.txt` and `reports/requirements.txt`. Other versions of pandas or Plotly can change figures or layout.
- **Linux is the reference platform.** CI and the Docker image run on Linux x86_64. Windows builds give the same figures; file checksums of the CSV differ because of line endings.

## Project

- **No hosted service.** Each report is a file. The web page (`src/app.py`) renders one report at a time and has no login, so run it only on a trusted machine or network.
- **Code layout is transitional.** The pipeline modules are not yet an installable package.
- **No PDF output.** Use the browser's *Print -> Save as PDF* if a PDF is needed.
