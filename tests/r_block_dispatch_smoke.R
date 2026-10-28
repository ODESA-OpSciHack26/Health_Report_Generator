# R dispatch smoke check: source order must match the shared template.
# report_helpers.R sources audience_reports.R, whose findings_html overrides the first
# definition. This check fails with "unused argument" if the override does not accept
# evidence_file, and asserts the researcher path renders exactly one block.
suppressPackageStartupMessages({library(jsonlite); library(knitr)})
knitr::opts_knit$set(rmarkdown.pandoc.to = 'html')
templates <- file.path(Sys.getenv('HEALTH_REPORT_PROJECT'), 'scripts', 'health_pipeline', 'templates')
old <- setwd(templates)
on.exit(setwd(old), add = TRUE)
source('report_helpers.R')

stopifnot('evidence_file' %in% names(formals(findings_html)))
stopifnot('evidence_file' %in% names(formals(audience_document_html)))
body_text <- paste(deparse(body(findings_html)), collapse = ' ')
stopifnot(grepl('audience_document_html\\(b, navigation, evidence_file\\)', body_text, fixed = FALSE))
stopifnot(grepl('findings_html_previous\\(b, navigation, evidence_file\\)', body_text, fixed = FALSE))

# Researcher path must contain exactly one call to the shared helper.
researcher_body <- paste(deparse(body(audience_document_html)), collapse = ' ')
calls <- length(gregexpr('reference_block\\(b, evidence_file\\)', researcher_body, fixed = FALSE)[[1]])
stopifnot(calls == 1L)

evidence <- list(blocks = list(list(
  status = 'verified', subject = 'virus', reference_year = 2019L, latest_year = 2025L,
  measure = 'cases',
  reference_count = list(metric_id = 'virus:2019:count', value = '10'),
  latest_count = list(metric_id = 'virus:2025:count', value = '16'),
  result = list(metric_id = 'virus:reference_change', value = 60.0, unit = 'percent',
                formula = 'percent_change', availability = 'available'),
  effective = list(presentation = list(unit = 'percent', digits = 0L)),
  trace = list(list(field = 'presentation.digits', source = 'component', value = 0L)),
  identities = list(analytical = strrep('a', 64), result = strrep('b', 64), instance = strrep('c', 64)),
  snapshot = list(snapshot_id = strrep('d', 64), snapshot_path = 'snapshots/example'),
  implementation = list(
    analysis = list(file = 'scripts/health_pipeline/analyse.py', sha256 = strrep('e', 64)),
    presentation = list(file = 'scripts/health_pipeline/templates/report_helpers.R', sha256 = strrep('f', 64))),
  reproduction = list(entry_point = 'snakemake --cores 2', snapshot_id = strrep('d', 64)),
  lineage = list(source_file = 'data/virus/data.csv', source_row = '2.0', sha256 = strrep('b', 64))
)))
path <- tempfile(fileext = '.json')
writeLines(toJSON(evidence, auto_unbox = TRUE, null = 'null'), path)
b <- list(classes = data.frame(topic = 'virus', label = 'Virus', stringsAsFactors = FALSE))
html <- reference_block(b, path)
stopifnot(lengths(regmatches(html, gregexpr('id="block-reference-comparison"', html))) == 1L)
stopifnot(grepl('Virus', html, fixed = TRUE))
stopifnot(grepl('10', html, fixed = TRUE) && grepl('16', html, fixed = TRUE))
stopifnot(grepl('+60.0%', html, fixed = TRUE))
stopifnot(grepl('<details', html, fixed = TRUE))

# Empty path means "no block requested"; a supplied but unusable path must be visible.
stopifnot(identical(reference_block(b, ''), ''))
missing <- reference_block(b, file.path(tempdir(), 'absent.json'))
stopifnot(grepl('id="block-reference-comparison"', missing, fixed = TRUE))
stopifnot(grepl('unavailable', missing, fixed = TRUE))

cat('r-block-dispatch smoke passed\n')

# Optional rendered-output assertions: pass a produced report.html path.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) >= 1L) {
  report <- args[[1]]
  stopifnot(file.exists(report))
  html <- paste(readLines(report, warn = FALSE, encoding = 'UTF-8'), collapse = '\n')
  stopifnot(grepl('href="#block-reference-comparison"', html, fixed = TRUE))
  stopifnot(lengths(regmatches(html, gregexpr('id="block-reference-comparison"', html))) == 1L)
  stopifnot(!grepl('href="#reference-block"', html, fixed = TRUE))
  stopifnot(lengths(regmatches(html, gregexpr('id="block-reference-comparison-inspector"', html))) == 1L)
  cat('rendered anchor checks passed\n')
}
