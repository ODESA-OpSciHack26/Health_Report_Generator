# Series collection smoke: native panels, default-open topic, per-panel coherence, no JS.
suppressPackageStartupMessages({library(jsonlite); library(knitr)})
knitr::opts_knit$set(rmarkdown.pandoc.to = 'html')
project <- Sys.getenv('HEALTH_REPORT_PROJECT')
if(!nzchar(project)) stop('HEALTH_REPORT_PROJECT is required')
old <- setwd(file.path(project, 'scripts', 'health_pipeline', 'templates')); on.exit(setwd(old), add = TRUE)
source('report_helpers.R')

b <- list(
  cfg = list(id = 'researcher', title = 'Collection test', years = c(2021, 2025),
             reference_year = 2019, geography = 'CHFL', period_type = 'year',
             outputs = c('headline'), presentation = list(display_name = 'Researcher',
             layout = 'technical', detail_level = 'full', version = '1.0')),
  manifest = list(snapshot_id = strrep('a', 64)),
  classes = data.frame(topic = c('alpha', 'beta', 'gamma'),
                       label = c('Alpha', 'Beta', 'Gamma'), stringsAsFactors = FALSE),
  selection = data.frame(dataset_id = 'ds1', topic = c('alpha', 'beta', 'gamma'),
                         source_system = 'mandatory_reporting_system', status = 'included',
                         reason = '', group_eligible = 'True', stringsAsFactors = FALSE),
  checks = data.frame(dataset_id = character(0), check = character(0),
                      status = character(0), detail = character(0), stringsAsFactors = FALSE))

member <- function(instance, topic, years, values, requested = c(2021L, 2025L), missing = integer(0),
                   status = 'verified') {
  observations <- Map(function(year, value)
    list(year = as.integer(year), count_metric_id = paste0(topic, ':', year, ':count'),
         value = as.character(value), unit = 'cases'), years, values)
  if(identical(status, 'failed'))
    return(list(status = 'failed', instance_id = instance,
                component = list(type = 'series-trend', version = '1'),
                contract = list(series = 'health-report/series-component/1'),
                code = 'selection', detail = 'no saved observations for this range'))
  list(status = 'verified', instance_id = instance,
       component = list(type = 'series-trend', version = '1'),
       contract = list(series = 'health-report/series-component/1'),
       selection = list(topic = topic, measure = 'cases', geography = 'CHFL',
                        dataset_id = 'ds1', source_system = 'mandatory_reporting_system'),
       periods = list(requested = as.integer(requested), effective = as.integer(years),
                      reference_year = 2019L, reference_outside_window = TRUE),
       missing_years = as.integer(missing), artifact = list(file = 'series.csv', digest = strrep('c', 64)),
       presentation = list(unit = 'cases', style = 'standard'),
       snapshot = list(snapshot_id = strrep('a', 64)),
       implementation = list(analysis = list(file = 'scripts/health_pipeline/analyse.py', sha256 = strrep('d', 64)),
                             presentation = list(file = 'scripts/health_pipeline/templates/report_helpers.R', sha256 = strrep('e', 64))),
       identities = list(analytical = paste0('an-', topic), rows = paste0('row-', topic),
                         instance = paste0('inst-', topic)),
       effective = list(presentation = list(unit = 'cases')),
       trace = list(list(field = 'presentation.unit', source = 'author', value = 'cases')),
       reproduction = list(entry_point = 'snakemake --cores 2', snapshot_id = strrep('a', 64)),
       observations = observations)
}

collection <- function(members, default = 'alpha', ordering = 'eligible-ascending',
                       status = 'verified', code = NULL, detail = NULL) {
  if(!identical(status, 'verified'))
    return(list(status = 'failed', instance_id = 'research-collection',
                component = list(type = 'series-collection', version = '1'),
                contract = list(collection = 'health-report/series-collection/1'),
                code = code, detail = detail))
  list(status = 'verified', instance_id = 'research-collection',
       component = list(type = 'series-collection', version = '1'),
       contract = list(series = 'health-report/series-component/1',
                       collection = 'health-report/series-collection/1'),
       topics = vapply(members, function(m) m$selection$topic, character(1)),
       ordering = ordering, measure = 'cases',
       presentation = list(style = 'standard', default_topic = default),
       periods = list(requested = c(2021L, 2025L), effective = c(2021L, 2022L, 2023L, 2024L, 2025L)),
       members = members,
       identities = list(collection = strrep('f', 64),
                         contract = 'series-collection-identity/1',
                         members = lapply(members, function(m) list(
                           instance_id = m$instance_id, topic = m$selection$topic,
                           status = m$status, instance_identity = m$identities$instance))),
       snapshot = list(snapshot_id = strrep('a', 64)),
       implementation = members[[1]]$implementation,
       reproduction = list(entry_point = 'snakemake --cores 2', snapshot_id = strrep('a', 64)))
}

render <- function(blocks) {
  dir <- tempfile(); dir.create(dir)
  writeLines(toJSON(list(blocks = blocks), auto_unbox = TRUE, null = 'null'),
             file.path(dir, 'provenance.json'))
  owd <- setwd(dir); on.exit(setwd(owd), add = TRUE)
  series_collection_block(b, 'provenance.json', instance_id = 'research-collection')
}

alpha <- member('sc-1-alpha', 'alpha', 2021:2025, c(10, 12, 11, 14, 16))
beta  <- member('sc-2-beta', 'beta', c(2021L, 2022L, 2024L, 2025L), c(5, 6, 7, 8),
                missing = 2023L)
gamma <- member('sc-3-gamma', 'gamma', 2025L, 3, missing = 2021:2024)

html <- render(list(collection(list(alpha, beta, gamma), default = 'beta')))

# Structure: three native disclosures, exactly one open, no script added by the block.
stopifnot(lengths(regmatches(html, gregexpr('<details class="series-panel"', html, fixed = TRUE))) == 3)
stopifnot(lengths(regmatches(html, gregexpr('class="series-panel" id="sc-1-alpha" open', html, fixed = TRUE))) == 0)
stopifnot(lengths(regmatches(html, gregexpr('class="series-panel" id="sc-2-beta" open', html, fixed = TRUE))) == 1)
stopifnot(lengths(regmatches(html, gregexpr('class="series-panel" id="sc-3-gamma"', html, fixed = TRUE))) == 1)
stopifnot(!grepl('<script', html, fixed = TRUE))
stopifnot(grepl('3 topics', html, fixed = TRUE))

# Each panel carries its own heading, chart, exact-value table and inspector.
panel <- function(id) {
  start <- regexpr(paste0('id="', id, '"'), html, fixed = TRUE)[[1]]
  stopifnot(start > 0)
  tail <- substr(html, start, nchar(html))
  end <- regexpr('</details>\\s*<details class="series-panel"', tail)
  if(end[[1]] > 0) substr(tail, 1, end[[1]]) else tail
}
for(case in list(list('sc-1-alpha', 'Alpha', 'alpha:2021:count'),
                 list('sc-2-beta', 'Beta', 'beta:2022:count'),
                 list('sc-3-gamma', 'Gamma', 'gamma:2025:count'))) {
  p <- panel(case[[1]])
  stopifnot(grepl(paste0('<h3>', case[[2]]), p, fixed = TRUE))
  stopifnot(grepl('<img', p, fixed = TRUE))
  stopifnot(grepl('View exact values', p, fixed = TRUE))
  stopifnot(grepl(paste0('-inspect"'), p, fixed = TRUE))
  stopifnot(grepl(case[[3]], p, fixed = TRUE))
}
# Gaps: the beta panel reports 2023 as unavailable, the gamma panel reports 2021-2024.
stopifnot(grepl('Not available', panel('sc-2-beta'), fixed = TRUE))
stopifnot(grepl('2021, 2022, 2023, 2024', panel('sc-3-gamma'), fixed = TRUE))
stopifnot(grepl('single point', panel('sc-3-gamma'), fixed = TRUE))

# Unique ids across the whole block, including inspectors.
ids <- regmatches(html, gregexpr('id="[A-Za-z0-9_-]+"', html))[[1]]
stopifnot(length(ids) == length(unique(ids)))

# A failed member collection renders unavailable, never a partial chart set.
failed <- render(list(collection(list(), status = 'failed', code = 'member',
                                 detail = "member topic 'alpha' did not resolve")))
stopifnot(grepl('Reported values over time unavailable', failed, fixed = TRUE))
stopifnot(grepl('did not resolve', failed, fixed = TRUE))
stopifnot(!grepl('<details class="series-panel"', failed, fixed = TRUE))

# A missing default topic falls back to the first member rather than failing the panel set.
fallback <- render(list(collection(list(alpha, beta), default = 'not-present')))
stopifnot(grepl('2 topics', fallback, fixed = TRUE))
stopifnot(lengths(regmatches(fallback, gregexpr('class="series-panel"', fallback, fixed = TRUE))) == 2)
stopifnot(lengths(regmatches(fallback, gregexpr('series-panel" id="sc-2-beta" open', fallback, fixed = TRUE))) == 0)

# Focus and panel rules are present in the composed style; this is a string assertion, not a
# browser or keyboard test.
style <- composition_style()
stopifnot(grepl('.composed-report summary:focus-visible', style, fixed = TRUE))
stopifnot(grepl('.composed-report .series-panel>summary', style, fixed = TRUE))
stopifnot(grepl('overflow-wrap:anywhere', style, fixed = TRUE))

# --- Combined layout: one shared chart, per-disease details without their own charts ---
combined_record <- function(members, default = 'beta') {
  record <- collection(members, default = default)
  record$presentation$layout <- 'combined'
  record$identities$contract <- 'series-collection-identity/2'
  record
}
combined <- render(list(combined_record(list(alpha, beta, gamma))))
stopifnot(lengths(regmatches(combined, gregexpr(
  '<figure class="series-figure series-figure--combined"', combined, fixed = TRUE))) == 1)
stopifnot(lengths(regmatches(combined, gregexpr('<img', combined, fixed = TRUE))) == 1)
stopifnot(grepl('Alpha, Beta, Gamma', combined, fixed = TRUE))          # legend/alt labels
stopifnot(grepl('do not establish comparable individual disease risks', combined, fixed = TRUE))
stopifnot(grepl('shared linear axis', combined, fixed = TRUE))
stopifnot(grepl('Switzerland and Liechtenstein', combined, fixed = TRUE))
stopifnot(lengths(regmatches(combined, gregexpr(
  '<details class="series-panel"', combined, fixed = TRUE))) == 3)
stopifnot(lengths(regmatches(combined, gregexpr(
  'class="series-panel" id="sc-2-beta" open', combined, fixed = TRUE))) == 1)
for(id in c('sc-1-alpha', 'sc-2-beta', 'sc-3-gamma')) {
  start <- regexpr(paste0('id="', id, '"'), combined, fixed = TRUE)[[1]]
  stopifnot(start > 0)
  tail <- substr(combined, start, nchar(combined))
  end <- regexpr('</details>\\s*<details class="series-panel"', tail)
  p <- if(end[[1]] > 0) substr(tail, 1, end[[1]]) else tail
  stopifnot(grepl('View exact values', p, fixed = TRUE))
  stopifnot(grepl('-inspect"', p, fixed = TRUE))
  stopifnot(!grepl('<img', p, fixed = TRUE))          # no duplicate per-disease charts
}
# Gaps and single points stay honest in the combined details.
stopifnot(grepl('Not available', combined, fixed = TRUE))
stopifnot(grepl('single point', combined, fixed = TRUE))

# The panels layout is unchanged when it is requested explicitly.
panels <- render(list(do.call(function(...) { r <- collection(...); r$presentation$layout <- 'panels'; r },
                              list(list(alpha, beta), default = 'alpha'))))
stopifnot(lengths(regmatches(panels, gregexpr('<img', panels, fixed = TRUE))) == 2)
stopifnot(!grepl('series-figure--combined', panels, fixed = TRUE))

cat('r-collection smoke passed\n')
