# Composed preview smoke: the preview banner comes from provenance and never appears by
# default. Structural markup assertion only; it is not browser or visual evidence.
suppressPackageStartupMessages({library(jsonlite); library(knitr)})
knitr::opts_knit$set(rmarkdown.pandoc.to = 'html')
project <- Sys.getenv('HEALTH_REPORT_PROJECT')
if(!nzchar(project)) stop('HEALTH_REPORT_PROJECT is required')
templates <- file.path(project, 'scripts', 'health_pipeline', 'templates')
old <- setwd(templates); on.exit(setwd(old), add = TRUE)
source('report_helpers.R')

b <- list(cfg = list(title = 'Preview test', years = c(2021, 2025), reference_year = 2019),
          manifest = list(snapshot_id = strrep('a', 64)),
          classes = data.frame(topic = 'virus', label = 'Virus', stringsAsFactors = FALSE))
registry <- list(alpha = list(label = 'Alpha', primary = FALSE,
                              render = function(b, entry, evidence_file = '')
                                paste0('<p id="', entry$instance_id, '-detail">body</p>')))
recipe <- tempfile(fileext = '.json')
writeLines(toJSON(list(contract = 'health-report/composition-recipe/1', audience = 'test',
                       blocks = list(list(block = 'alpha', instance_id = 'i-alpha'))),
                  auto_unbox = TRUE), recipe)

count_of <- function(h, text) lengths(regmatches(h, gregexpr(text, h, fixed = TRUE)))

# A preview provenance record marks the render, and the page states it exactly once.
work <- tempfile(); dir.create(work); owd <- setwd(work)
writeLines(toJSON(list(composition = list(effective_title = 'Preview test'),
                       preview = list(status = 'preview',
                                      notice = 'Preview — not an accepted publication.',
                                      accepted_output = FALSE)),
                  auto_unbox = TRUE), 'provenance.json')
preview_html <- compose_report_html(b, recipe, registry = registry)
stopifnot(count_of(preview_html, 'class="composed-preview"') == 1L)
stopifnot(grepl('Preview — not an accepted publication.', preview_html, fixed = TRUE))
stopifnot(grepl('role="note"', preview_html, fixed = TRUE))
stopifnot(grepl('implies no review, acceptance or release', preview_html, fixed = TRUE))
stopifnot(grepl('.composed-report .composed-preview{', composition_style(), fixed = TRUE))
# The banner precedes the report intro and the block order is unchanged.
stopifnot(regexpr('class="composed-preview"', preview_html, fixed = TRUE)[[1]] <
            regexpr('class="composed-intro"', preview_html, fixed = TRUE)[[1]])
stopifnot(grepl('id="i-alpha"', preview_html, fixed = TRUE))

# Without the marker the markup is exactly the ordinary composed report: no banner at all.
writeLines(toJSON(list(composition = list(effective_title = 'Preview test')), auto_unbox = TRUE),
           'provenance.json')
plain_html <- compose_report_html(b, recipe, registry = registry)
stopifnot(count_of(plain_html, 'class="composed-preview"') == 0L)
stopifnot(!grepl('not an accepted publication', plain_html, fixed = TRUE))
setwd(owd)

# A record whose preview status is something else is not treated as a preview.
work2 <- tempfile(); dir.create(work2); owd <- setwd(work2)
writeLines(toJSON(list(preview = list(status = 'publication', notice = 'x')), auto_unbox = TRUE),
           'provenance.json')
other_html <- compose_report_html(b, recipe, registry = registry)
stopifnot(count_of(other_html, 'class="composed-preview"') == 0L)
setwd(owd)

cat('r-composer-preview smoke passed\n')
