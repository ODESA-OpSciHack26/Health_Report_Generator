# Composition dispatch smoke: instance identity, order, rejection and navigation targets.
suppressPackageStartupMessages({library(jsonlite); library(knitr)})
knitr::opts_knit$set(rmarkdown.pandoc.to = 'html')
project <- Sys.getenv('HEALTH_REPORT_PROJECT')
templates <- file.path(project, 'scripts', 'health_pipeline', 'templates')
old <- setwd(templates); on.exit(setwd(old), add = TRUE)
source('report_helpers.R')

# Stub only the page furniture so the composer itself is exercised.
presentation_open <- function(b) '<div class="report">'
report_metadata <- function(b) ''
b <- list(cfg = list(title = 'Composed test', years = c(2021, 2025), reference_year = 2019),
          manifest = list(snapshot_id = strrep('a', 64)),
          classes = data.frame(topic = 'virus', label = 'Virus', stringsAsFactors = FALSE))

write_recipe <- function(blocks) {
  path <- tempfile(fileext = '.json')
  writeLines(toJSON(list(contract = 'health-report/composition-recipe/1', audience = 'test',
                         blocks = blocks), auto_unbox = TRUE), path)
  path
}

stub <- function(label, primary = FALSE) list(
  label = label, primary = primary,
  render = function(b, entry, evidence_file = '')
    paste0('<p id="', entry$instance_id, '-detail">body ', entry$block, '</p>'))
registry <- list(
  alpha = stub('Alpha'), beta = stub('Beta'),
  'reference-comparison' = list(
    label = 'Reference comparison', primary = TRUE,
    render = function(b, entry, evidence_file = '')
      paste0('<p class="finding-value">+60.0%</p>')))

section_ids <- function(h) {
  tags <- regmatches(h, gregexpr('<section class="composed-block[^"]*" id="[a-z0-9-]+"', h))[[1]]
  sub('.*id="([a-z0-9-]+)"$', '\\1', tags)
}
nav_targets <- function(h) {
  nav <- regmatches(h, regexpr('<nav class="composed-nav"[^>]*>.*</nav>', h))
  targets <- regmatches(nav, gregexpr('href="#[a-z0-9-]+"', nav))[[1]]
  sub('href="#(.*)"', '\\1', targets)
}
count_of <- function(h, text) lengths(regmatches(h, gregexpr(text, h, fixed = TRUE)))

# 1. Section identity and navigation come from the recipe instance ids.
ordered <- write_recipe(list(list(block = 'alpha', instance_id = 'i-alpha'),
                             list(block = 'beta', instance_id = 'i-beta')))
html_a <- compose_report_html(b, ordered, registry = registry)
stopifnot(identical(section_ids(html_a), c('i-alpha', 'i-beta')))
stopifnot(identical(nav_targets(html_a), c('i-alpha', 'i-beta')))
for (id in c('i-alpha', 'i-beta')) {
  stopifnot(count_of(html_a, paste0('href="#', id, '"')) == 1L)
  stopifnot(count_of(html_a, paste0('id="', id, '"')) == 1L)
}
stopifnot(!grepl('id="overview"', html_a, fixed = TRUE))
stopifnot(!grepl('id="alpha-block"', html_a, fixed = TRUE))

# 2. Reordering changes section order, never instance identity.
reversed <- write_recipe(list(list(block = 'beta', instance_id = 'i-beta'),
                              list(block = 'alpha', instance_id = 'i-alpha')))
html_b <- compose_report_html(b, reversed, registry = registry)
stopifnot(identical(section_ids(html_b), c('i-beta', 'i-alpha')))
stopifnot(identical(nav_targets(html_b), c('i-beta', 'i-alpha')))
stopifnot(identical(sort(section_ids(html_a)), sort(section_ids(html_b))))

# 3. Repeated stateless blocks are safe with distinct instance ids.
repeated <- write_recipe(list(list(block = 'alpha', instance_id = 'i-one'),
                              list(block = 'alpha', instance_id = 'i-two'),
                              list(block = 'beta', instance_id = 'i-three')))
html_r <- compose_report_html(b, repeated, registry = registry)
stopifnot(identical(section_ids(html_r), c('i-one', 'i-two', 'i-three')))
stopifnot(identical(nav_targets(html_r), c('i-one', 'i-two', 'i-three')))
stopifnot(count_of(html_r, 'id="i-one-detail"') == 1L)
stopifnot(count_of(html_r, 'id="i-two-detail"') == 1L)
stopifnot(count_of(html_r, 'id="i-three-detail"') == 1L)

# 4. Duplicate and malformed instance ids are rejected.
dup <- tryCatch({ compose_report_html(b, write_recipe(list(
  list(block = 'alpha', instance_id = 'i-same'),
  list(block = 'beta', instance_id = 'i-same'))), registry = registry); NULL },
  error = function(e) conditionMessage(e))
stopifnot(grepl('Duplicate block instance id', dup))
unsafe <- tryCatch({ compose_report_html(b, write_recipe(list(
  list(block = 'alpha', instance_id = 'Bad Id'))), registry = registry); NULL },
  error = function(e) conditionMessage(e))
stopifnot(grepl('Invalid block instance id', unsafe))

# 5. Repeated reference-comparison blocks are refused, not relabelled.
repeated_ref <- tryCatch({ compose_report_html(b, write_recipe(list(
  list(block = 'reference-comparison', instance_id = 'ref-one'),
  list(block = 'reference-comparison', instance_id = 'ref-two'))), registry = registry); NULL },
  error = function(e) conditionMessage(e))
stopifnot(grepl('Repeated reference-comparison blocks are not supported yet', repeated_ref))

# 6. Unknown blocks and duplicate ids are still rejected.
bad <- tryCatch({ compose_report_html(b, write_recipe(list(
  list(block = 'gamma', instance_id = 'i-g'))), registry = registry); NULL },
  error = function(e) conditionMessage(e))
stopifnot(grepl('Unknown block type', bad))

# 7. Primary/kicker text and labels come from renderer metadata, not the block name.
primary_recipe <- write_recipe(list(list(block = 'reference-comparison', instance_id = 'i-ref'),
                                     list(block = 'beta', instance_id = 'i-b')))
html_p <- compose_report_html(b, primary_recipe, registry = registry)
stopifnot(count_of(html_p, 'class="composed-block composed-block--primary"') == 1L)
stopifnot(grepl('Primary finding', html_p, fixed = TRUE))
stopifnot(grepl('Supporting block', html_p, fixed = TRUE))
stopifnot(identical(nav_targets(html_p), c('i-ref', 'i-b')))
stopifnot(!any(grepl('-', composition_labels, fixed = TRUE)))
stopifnot(identical(unname(composition_labels),
                    c('Context', 'Reference comparison', 'Limitations', 'Reproduction')))
stopifnot(!grepl('dash-footer', html_a, fixed = TRUE))
stopifnot(!grepl('presentation_open', html_a, fixed = TRUE))

# 8. Real registry shape and researcher recipe still name the same four blocks.
stopifnot(identical(sort(names(composition_registry)),
                    sort(c('intro', 'reference-comparison', 'limitations', 'reproduction'))))
stopifnot(all(vapply(composition_registry, function(spec)
  is.list(spec) && is.function(spec$render) && is.character(spec$label), logical(1))))
recipe <- jsonlite::fromJSON(file.path(project, 'scripts', 'health_pipeline', 'config', 'composer',
                                       'compositions', 'researcher.json'), simplifyVector = FALSE)
stopifnot(identical(vapply(recipe$blocks, function(x) x$block, character(1)),
                    c('intro', 'reference-comparison', 'limitations', 'reproduction')))
instance_ids <- vapply(recipe$blocks, function(x) x$instance_id, character(1))
stopifnot(identical(instance_ids,
                    c('intro-0001', 'block-reference-comparison',
                      'limitations-0001', 'reproduction-0001')))

# 9. reference_block selects the checked record by instance id and namespaces its inspector.
make_block <- function(instance, identity) list(
  status = 'verified', instance_id = instance, subject = 'virus',
  reference_year = 2019L, latest_year = 2025L, measure = 'cases',
  reference_count = list(metric_id = 'virus:2019:count', value = '10'),
  latest_count = list(metric_id = 'virus:2025:count', value = '16'),
  result = list(metric_id = 'virus:reference_change', value = 60.0, unit = 'percent',
                formula = 'percent_change', availability = 'available'),
  effective = list(presentation = list(unit = 'percent', digits = 0L)),
  trace = list(list(field = 'presentation.digits', source = 'component', value = 0L)),
  identities = list(analytical = strrep('a', 64), result = strrep('b', 64), instance = identity),
  snapshot = list(snapshot_id = strrep('d', 64), snapshot_path = 'snapshots/example'),
  implementation = list(
    analysis = list(file = 'scripts/health_pipeline/analyse.py', sha256 = strrep('e', 64)),
    presentation = list(file = 'scripts/health_pipeline/templates/report_helpers.R',
                        sha256 = strrep('f', 64))),
  reproduction = list(entry_point = 'snakemake --cores 2', snapshot_id = strrep('d', 64)),
  lineage = list(source_file = 'data/virus/data.csv', source_row = '2.0', sha256 = strrep('b', 64)))
evidence <- list(blocks = list(make_block('ref-a', strrep('1', 64)),
                               make_block('ref-b', strrep('2', 64))))
path <- tempfile(fileext = '.json')
writeLines(toJSON(evidence, auto_unbox = TRUE, null = 'null'), path)

html_ra <- reference_block(b, path, variant = 'composed', instance_id = 'ref-a')
html_rb <- reference_block(b, path, variant = 'composed', instance_id = 'ref-b')
stopifnot(count_of(html_ra, 'id="ref-a-inspect"') == 1L)
stopifnot(count_of(html_rb, 'id="ref-b-inspect"') == 1L)
stopifnot(!grepl('ref-a-inspect', html_rb, fixed = TRUE))
stopifnot(grepl(strrep('1', 64), html_ra, fixed = TRUE))
stopifnot(grepl(strrep('2', 64), html_rb, fixed = TRUE))
stopifnot(!grepl('id="ref-a"', html_ra, fixed = TRUE))
missing <- reference_block(b, path, variant = 'composed', instance_id = 'ref-absent')
stopifnot(grepl('no checked record for block instance ref-absent', missing, fixed = TRUE))
stopifnot(!grepl('+60.0%', missing, fixed = TRUE))

# 10. Legacy defaults are unchanged: same panel id, first record, inspect panel ids.
legacy <- reference_block(b, path)
stopifnot(count_of(legacy, 'id="block-reference-comparison"') == 1L)
stopifnot(count_of(legacy, 'id="block-reference-comparison-inspector"') == 1L)
stopifnot(grepl('id="block-data"', legacy, fixed = TRUE))
stopifnot(grepl('id="block-method"', legacy, fixed = TRUE))
stopifnot(grepl('id="block-implementation"', legacy, fixed = TRUE))
stopifnot(grepl('id="block-reproduction"', legacy, fixed = TRUE))
stopifnot(grepl(strrep('1', 64), legacy, fixed = TRUE))
stopifnot(identical(reference_block(b, ''), ''))
stopifnot(!grepl('composed-block', legacy, fixed = TRUE))

cat('r-composition smoke passed\n')

# Optional rendered-output assertions: pass a produced composed report.html path.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) >= 1L) {
  report <- args[[1]]
  stopifnot(file.exists(report))
  html <- paste(readLines(report, warn = FALSE, encoding = 'UTF-8'), collapse = '\n')
  ids <- section_ids(html)
  stopifnot(identical(ids, instance_ids))
  stopifnot(identical(nav_targets(html), instance_ids))
  for (id in instance_ids) {
    stopifnot(count_of(html, paste0('href="#', id, '"')) == 1L)
    stopifnot(count_of(html, paste0('id="', id, '"')) == 1L)
  }
  stopifnot(count_of(html, 'id="block-reference-comparison-inspect"') == 1L)
  for (label in c('Context', 'Reference comparison', 'Limitations', 'Reproduction'))
    stopifnot(grepl(paste0('>', label, '</a>'), html, fixed = TRUE))
  stopifnot(!grepl('href="report.pdf"', html, fixed = TRUE))
  cat('rendered composition checks passed\n')
}
