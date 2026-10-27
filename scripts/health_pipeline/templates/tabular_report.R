# Presentation only. Python has verified the captured source and rows.
tabular_document_html <- function(document='report') {
  if(!document %in% c('report', 'methods')) stop('Unsupported tabular document')
  x <- jsonlite::fromJSON('tabular_context.json', simplifyVector=FALSE)
  p <- x$profile
  technical <- identical(p$layout, 'technical')
  editorial <- identical(p$layout, 'editorial')
  section <- function(id, title, body) paste0(
    '<section class="document-section" id="', esc(id), '"><h2>', esc(title), '</h2>', body, '</section>')
  pair <- function(key, value) paste0('<dt>', esc(key), '</dt><dd>', esc(value), '</dd>')
  show_value <- function(value) if(is.null(value)) 'Not applicable' else as.character(value)
  missing <- x$output$missing
  quality <- paste0('<dl class="provenance-list">',
    pair('Rows retained', x$output$rows),
    pair('Missing category fields', missing$category),
    pair('Missing numeric values', missing$value),
    pair('Missing observation dates', show_value(missing$period)), '</dl>',
    '<p>Empty or whitespace-only fields are missing. Invalid non-missing numeric or date values block preparation. ',
    'Missing values remain in the displayed rows. Acceptance of the file structure is not proof of scientific validity.</p>')
  parameters <- paste0('<dl class="provenance-list">',
    paste(vapply(names(x$parameters$mapping), function(role)
      pair(paste('Mapped', role), x$parameters$mapping[[role]]), character(1)), collapse=''),
    pair('Mode', x$parameters$mode), pair('Period', show_value(x$parameters$period)),
    pair('Row filters', 'None'), pair('Aggregation', 'None'), '</dl>')
  limits <- paste0('<p>This report shows the supplied observations, not disease notifications or infections ',
    'unless the source independently establishes that meaning. Units and geography are not inferred. ',
    'It does not calculate sums, averages, percentage changes, rates, alert thresholds or confidence intervals. ',
    'It does not establish causes or statistical significance.</p>',
    '<p>Period starts are labels for the selected granularity, not newly observed dates. ',
    'Rows sharing a period are not combined. A snapshot has no invented observation date. ',
    'Source authenticity, representativeness and fitness for a health decision have not been established.</p>')
  heading <- if(technical) 'Uploaded table: technical data report' else if(editorial)
    'Understanding the supplied data' else 'Supplied data: descriptive briefing'
  intro <- if(editorial) '<p>Each row below is one observation from the supplied file. Blank values remain visible; no totals or trends have been inferred.</p>' else if(technical)
    '<p>Row-preserving view of an independently verified preparation bundle. Consult the mapping and provenance before reusing these observations.</p>' else
    '<p>Review the observations and missing fields before using this briefing. No operational alert or public-health recommendation is inferred.</p>'
  navigation <- paste0('<nav aria-label="Reports"><a href="report.html">Observations</a> · ',
    '<a href="methods.html">Methods and provenance</a></nav>')
  parts <- c(paste0('<div class="dashboard audience-', esc(p$layout),
    '" data-tabular-audience="', esc(x$audience), '">'), navigation,
    paste0('<header class="document-header"><p class="eyebrow">', esc(p$display_name),
      ' · verified supplied-table report</p><h1>', esc(if(document == 'methods') 'Methods and provenance' else heading),
      '</h1><p>Source file: ', esc(x$source$source_filename), '</p></header>'))
  if(document == 'report') {
    parts <- c(parts, section('overview', 'What this report contains', intro),
      section('data-quality', if(editorial) 'What is missing?' else 'Data quality and missingness', quality))
    if(technical) parts <- c(parts, section('parameters', 'Effective parameters', parameters))
    parts <- c(parts, section('observations', 'Supplied observations', paste0(
      '<p>Initial order matches the source data records. Filtering and sorting change only the view. ',
      '“Missing” marks an absent field; a source category can also literally be named Missing.</p>', x$rows_html)))
  } else {
    parts <- c(parts, section('parameters', 'Mapping and processing', parameters),
      section('data-quality', 'Preserved rows and missingness', quality),
      section('source-identity', 'Captured source identity', paste0('<p>SHA-256: <code>',
        esc(x$source$sha256), '</code>. ', esc(x$source$bytes), ' bytes; ', esc(x$source$rows),
        ' data records. Original bytes are retained in the verified bundle.</p>')))
    if(technical) parts <- c(parts, section('reproduction', 'Reproduce and inspect', paste0(
      '<p>With the matching project code and environment, independently verify the bundle before using it:</p>',
      '<pre><code>from tabular_bundle import verify_prepared_bundle
verified = verify_prepared_bundle("../bundle")
print(verified.table)</code></pre>',
      '<p>Run from the audience directory with scripts/health_pipeline on PYTHONPATH. ',
      'The verifier requires matching preparation code and runtime versions.</p>')))
  }
  parts <- c(parts, section('limitations', 'Limitations', limits),
    section('provenance', 'Provenance', paste0(
      '<p><a href="provenance.json" download>Download render provenance</a> · ',
      '<a href="../bundle/manifest.json" download>Prepared bundle manifest</a> · ',
      '<a href="../bundle/provenance.json" download>Preparation provenance</a></p>',
      '<p>The same render provenance record is embedded in this page. Hashes establish internal ',
      'consistency, not authentication of the intended source.</p>')), '</div>')
  paste(parts, collapse='\n')
}
