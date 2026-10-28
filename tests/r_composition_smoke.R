# Composition dispatch smoke: order, omission, rejection and navigation targets.
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
          manifest = list(snapshot_id = strrep('a', 64)))
registry <- list(
  alpha = function(b, evidence_file = '') '<h2 class="composed-heading">A</h2>',
  beta = function(b, evidence_file = '') '<h2 class="composed-heading">B</h2>',
  'reference-comparison' = function(b, evidence_file = '') '<p class="finding-value">+60.0%</p>')

write_recipe <- function(blocks) {
  path <- tempfile(fileext = '.json')
  writeLines(toJSON(list(contract = 'health-report/composition-recipe/1', audience = 'test',
                         blocks = blocks), auto_unbox = TRUE), path)
  path
}

ordered <- write_recipe(list(list(block = 'alpha', instance_id = 'i-alpha'),
                             list(block = 'beta', instance_id = 'i-beta')))
reversed <- write_recipe(list(list(block = 'beta', instance_id = 'i-beta'),
                              list(block = 'alpha', instance_id = 'i-alpha')))
omitted <- write_recipe(list(list(block = 'beta', instance_id = 'i-beta')))

html_a <- compose_report_html(b, ordered, registry = registry)
html_b <- compose_report_html(b, reversed, registry = registry)
html_c <- compose_report_html(b, omitted, registry = registry)

pos <- function(h, id) regexpr(paste0('id="', id, '"'), h, fixed = TRUE)[[1]]
stopifnot(pos(html_a, 'alpha-block') < pos(html_a, 'beta-block'))
stopifnot(pos(html_b, 'beta-block') < pos(html_b, 'alpha-block'))
stopifnot(grepl('id="beta-block"', html_c, fixed = TRUE))
stopifnot(!grepl('id="alpha-block"', html_c, fixed = TRUE))

# Navigation targets must equal the rendered section ids.
nav <- regmatches(html_a, regexpr('<nav class="composed-nav"[^>]*>.*</nav>', html_a))
targets <- regmatches(nav, gregexpr('href="#[a-z0-9-]+"', nav))[[1]]
stopifnot(identical(sub('href="#(.*)"', '\\1', targets), c('alpha-block', 'beta-block')))

bad <- tryCatch({ compose_report_html(b, write_recipe(list(list(block = 'gamma', instance_id = 'i-g'))), registry = registry); NULL },
                error = function(e) conditionMessage(e))
stopifnot(grepl('Unknown block type', bad))

primary_recipe <- write_recipe(list(list(block = 'reference-comparison', instance_id = 'i-ref'),
                                     list(block = 'beta', instance_id = 'i-b')))
html_p <- compose_report_html(b, primary_recipe, registry = registry)
stopifnot(lengths(regmatches(html_p, gregexpr('class="composed-block composed-block--primary"', html_p, fixed = TRUE))) == 1L)
stopifnot(grepl('Primary finding', html_p, fixed = TRUE))
stopifnot(grepl('Supporting block', html_p, fixed = TRUE))
stopifnot(!any(grepl('-', composition_labels, fixed = TRUE)))
stopifnot(identical(unname(composition_labels),
                    c('Context', 'Reference comparison', 'Limitations', 'Reproduction')))
stopifnot(!grepl('dash-footer', html_a, fixed = TRUE))
stopifnot(!grepl('presentation_open', html_a, fixed = TRUE))
dup <- tryCatch({ compose_report_html(b, write_recipe(list(list(block = 'alpha', instance_id = 'i-same'),
                                                          list(block = 'beta', instance_id = 'i-same'))), registry = registry); NULL },
                error = function(e) conditionMessage(e))
stopifnot(grepl('Duplicate block instance id', dup))

stopifnot(identical(sort(names(composition_registry)),
                    sort(c('intro', 'reference-comparison', 'limitations', 'reproduction'))))
recipe <- jsonlite::fromJSON(file.path(project, 'scripts', 'health_pipeline', 'config', 'composer',
                                       'compositions', 'researcher.json'), simplifyVector = FALSE)
stopifnot(identical(vapply(recipe$blocks, function(x) x$block, character(1)),
                    c('intro', 'reference-comparison', 'limitations', 'reproduction')))

cat('r-composition smoke passed\n')
