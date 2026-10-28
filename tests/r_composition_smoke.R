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

# 8b. The three audience recipes declare themselves and keep evidence/limitations.
expected_orders <- list(
  researcher = c('intro', 'reference-comparison', 'limitations', 'reproduction'),
  health_institution = c('reference-comparison', 'intro', 'limitations', 'reproduction'),
  public = c('intro', 'limitations', 'reference-comparison', 'reproduction'))
for (audience in names(expected_orders)) {
  one <- jsonlite::fromJSON(file.path(project, 'scripts', 'health_pipeline', 'config', 'composer',
                                      'compositions', paste0(audience, '.json')),
                            simplifyVector = FALSE)
  stopifnot(identical(one$audience, audience))
  stopifnot(identical(vapply(one$blocks, function(x) x$block, character(1)),
                      expected_orders[[audience]]))
  ids <- vapply(one$blocks, function(x) x$instance_id, character(1))
  stopifnot(length(ids) == length(unique(ids)))
  stopifnot(all(c('limitations', 'reproduction') %in% vapply(one$blocks, function(x) x$block, character(1))))
}

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

# 11. Audience-specific explanations use the existing presentation layout.
audience_b <- function(layout, detail) list(
  cfg = list(id = layout, title = paste('Title', layout),
             question = 'Which notifiable diseases changed most in 2025?',
             years = c(2021, 2025), reference_year = 2019, geography = 'CHFL',
             period_type = 'year',
             presentation = list(display_name = layout, layout = layout,
                                 detail_level = detail, version = '1.0')),
  manifest = list(snapshot_id = strrep('d', 64)),
  classes = data.frame(topic = 'virus', label = 'Virus', stringsAsFactors = FALSE),
  checks = data.frame(status = c('PASS', 'PASS', 'WARN', 'SKIP'), stringsAsFactors = FALSE))
explanation <- function(html) {
  found <- regmatches(html, regexpr('<div class="audience-explanation">.*?</div>', html))
  stopifnot(length(found) == 1L)
  found
}
b_tech <- audience_b('technical', 'full')
b_dash <- audience_b('dashboard', 'monitoring')
b_pub <- audience_b('editorial', 'plain_language')
ref_tech <- reference_block(b_tech, path, variant = 'composed', instance_id = 'ref-a')
ref_dash <- reference_block(b_dash, path, variant = 'composed', instance_id = 'ref-a')
ref_pub <- reference_block(b_pub, path, variant = 'composed', instance_id = 'ref-a')
tech <- explanation(ref_tech); dash <- explanation(ref_dash); pub <- explanation(ref_pub)

# Same saved values reach every audience; only the explanation differs.
for (html in list(ref_tech, ref_dash, ref_pub)) {
  stopifnot(grepl('+60.0%', html, fixed = TRUE))
  stopifnot(grepl('<strong>10</strong>', html, fixed = TRUE))
  stopifnot(grepl('<strong>16</strong>', html, fixed = TRUE))
}
stopifnot(grepl('virus:reference_change', tech, fixed = TRUE))
stopifnot(grepl('virus:2019:count', tech, fixed = TRUE))
stopifnot(grepl('formula percent_change', tech, fixed = TRUE))
stopifnot(grepl('Unit percent', tech, fixed = TRUE))
stopifnot(grepl('no inferential uncertainty estimate', tech, fixed = TRUE))
stopifnot(grepl('no causal conclusion', tech, fixed = TRUE))
stopifnot(grepl('Monitoring question:', dash, fixed = TRUE))
stopifnot(grepl('Which notifiable diseases changed most in 2025?', dash, fixed = TRUE))
stopifnot(grepl('Observed change: +60.0%', dash, fixed = TRUE))
stopifnot(grepl('Switzerland and Liechtenstein', dash, fixed = TRUE))
stopifnot(grepl('no canton- or institution-specific evidence', dash, fixed = TRUE))
stopifnot(grepl('applies no operational threshold', dash, fixed = TRUE))
stopifnot(grepl('does not measure infection incidence', dash, fixed = TRUE))
stopifnot(grepl('In plain terms: 16 cases of virus were reported in 2025, compared with 10 in 2019', pub, fixed = TRUE))
stopifnot(grepl('do not necessarily mean a matching rise in infections', pub, fixed = TRUE))
stopifnot(grepl('not a statistical test', pub, fixed = TRUE))
stopifnot(!grepl('virus:reference_change', pub, fixed = TRUE))
stopifnot(!grepl('In plain terms', tech, fixed = TRUE))
stopifnot(!grepl('Monitoring question', pub, fixed = TRUE))

lim_tech <- composed_limitations(b_tech)
lim_dash <- composed_limitations(b_dash)
lim_pub <- composed_limitations(b_pub)
stopifnot(grepl('do not establish the completeness or accuracy', lim_tech, fixed = TRUE))
stopifnot(grepl('No operational threshold or recommendation is derived from them.', lim_dash, fixed = TRUE))
stopifnot(grepl('cannot prove that the reported counts are complete or accurate', lim_pub, fixed = TRUE))
stopifnot(grepl('Before this summary was made', lim_pub, fixed = TRUE))

cat('r-composition smoke passed\n')

# Optional rendered-output assertions: pass a produced composed report.html path,
# optionally followed by its audience id (default: researcher).
args <- commandArgs(trailingOnly = TRUE)
if (length(args) >= 1L) {
  report <- args[[1]]
  audience <- if (length(args) >= 2L) args[[2]] else 'researcher'
  stopifnot(file.exists(report))
  html <- paste(readLines(report, warn = FALSE, encoding = 'UTF-8'), collapse = '\n')
  audience_recipe <- jsonlite::fromJSON(file.path(project, 'scripts', 'health_pipeline', 'config',
                                                  'composer', 'compositions',
                                                  paste0(audience, '.json')), simplifyVector = FALSE)
  stopifnot(identical(audience_recipe$audience, audience))
  expected <- vapply(audience_recipe$blocks, function(x) x$instance_id, character(1))
  ids <- section_ids(html)
  stopifnot(identical(ids, expected))
  stopifnot(identical(nav_targets(html), expected))
  for (id in expected) {
    stopifnot(count_of(html, paste0('href="#', id, '"')) == 1L)
    stopifnot(count_of(html, paste0('id="', id, '"')) == 1L)
  }
  ref_id <- expected[[which(vapply(audience_recipe$blocks, function(x) x$block, character(1)) ==
                              'reference-comparison')]]
  stopifnot(count_of(html, paste0('id="', ref_id, '-inspect"')) == 1L)
  for (label in c('Context', 'Reference comparison', 'Limitations', 'Reproduction'))
    stopifnot(grepl(paste0('>', label, '</a>'), html, fixed = TRUE))
  stopifnot(!grepl('href="report.pdf"', html, fixed = TRUE))
  phrases <- c(researcher = 'no inferential uncertainty estimate',
               health_institution = 'no canton- or institution-specific evidence',
               public = 'do not necessarily mean a matching rise in infections')
  stopifnot(count_of(html, 'class="audience-explanation"') == 2L)
  stopifnot(grepl(phrases[[audience]], html, fixed = TRUE))
  cat('rendered composition checks passed:', audience, '\n')
}
