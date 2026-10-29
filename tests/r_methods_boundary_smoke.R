# Methods reference-boundary smoke: composed vs legacy resolution by instance id.
suppressPackageStartupMessages({library(jsonlite); library(knitr)})
knitr::opts_knit$set(rmarkdown.pandoc.to = 'html')
project <- Sys.getenv('HEALTH_REPORT_PROJECT')
old <- setwd(file.path(project, 'scripts', 'health_pipeline', 'templates')); on.exit(setwd(old), add = TRUE)
source('report_helpers.R')

b <- list(cfg = list(years = c(2021, 2025), reference_year = 2019, geography = 'CHFL',
                     exclude_from_group_totals = character(0), outputs = character(0)),
          sources = data.frame(status = 'ok', topic = 'virus',
                               publishing_date = '2026-01-01', used = 'True',
                               stringsAsFactors = FALSE),
          series = data.frame(topic = 'virus', pathogen_class = 'viral', measure = 'cases',
                              year = 2025, value = 16, stringsAsFactors = FALSE),
          manifest = list(snapshot_id = strrep('a', 64), files = list()),
          classes = data.frame(topic = 'virus', label = 'Virus', stringsAsFactors = FALSE),
          selection = data.frame(dataset_id = 'ds1', topic = 'virus',
                                 source_system = 'mandatory_reporting_system', status = 'included',
                                 reason = '', group_eligible = 'True', stringsAsFactors = FALSE),
          checks = data.frame(dataset_id = character(0), check = character(0),
                              status = character(0), detail = character(0)),
          metrics = data.frame(
            metric_id = c('viral:main:2019:total', 'viral:main:2025:total', 'viral:main:reference_change'),
            metric_type = c('group_total', 'group_total', 'reference_change'),
            subject = 'viral:main', year = c(2019, 2025, 2025),
            unit = c('cases', 'cases', 'percent'), value = c('10', '16', '60.0'),
            formula = c('sum', 'sum', 'percent_change'), inputs_json = c('[]', '[]', '[]'),
            stringsAsFactors = FALSE))

ref_record <- function(instance, status = 'verified', subject = 'virus')
  list(status = status, instance_id = instance,
       component = list(type = 'reference-comparison', version = '1'), subject = subject,
       reference_year = 2019L, latest_year = 2025L, measure = 'cases',
       reference_count = list(metric_id = 'virus:2019:count', value = '10'),
       latest_count = list(metric_id = 'virus:2025:count', value = '16'),
       result = list(metric_id = 'virus:reference_change', value = 60, unit = 'percent',
                     formula = 'percent_change', availability = 'available'),
       effective = list(presentation = list(unit = 'percent', digits = 1L)),
       identities = list(analytical = strrep('1', 64), result = strrep('2', 64), instance = instance),
       snapshot = list(snapshot_id = strrep('a', 64)), implementation = list())

series_record <- function(instance) list(status = 'verified', instance_id = instance,
  component = list(type = 'series-trend', version = '1'),
  selection = list(topic = 'virus', measure = 'cases', geography = 'CHFL'),
  periods = list(requested = c(2021L, 2025L), effective = c(2021L, 2025L), reference_year = 2019L),
  missing_years = list(), artifact = list(file = 'series.csv', digest = strrep('b', 64)),
  presentation = list(unit = 'cases'), identities = list(), snapshot = list(snapshot_id = strrep('a', 64)),
  implementation = list())

run <- function(composition, blocks) {
  dir <- tempfile(); dir.create(dir)
  writeLines(toJSON(list(blocks = blocks), auto_unbox = TRUE, null = 'null'), file.path(dir, 'provenance.json'))
  if(!is.null(composition))
    writeLines(toJSON(list(composition = composition), auto_unbox = TRUE, null = 'null'),
               file.path(dir, 'provenance.json'))
  if(!is.null(composition)) {
    full <- list(blocks = blocks, composition = composition)
    writeLines(toJSON(full, auto_unbox = TRUE, null = 'null'), file.path(dir, 'provenance.json'))
  }
  owd <- setwd(dir); on.exit(setwd(owd), add = TRUE)
  methods_html(b, navigation = FALSE)
}
composed <- function(recipe_blocks, display_topics = 'virus')
  list(audience = 'test', effective_recipe = recipe_blocks,
       display_scope = list(standalone_topics = as.list(display_topics), monitoring_topics = list(),
                            displayed_topics = as.list(display_topics), group_summaries = list()))

legacy <- run(NULL, list(ref_record('ref-a')))
stopifnot(grepl('This legacy methods path traces the saved group result', legacy, fixed = TRUE))
stopifnot(grepl('Calculation', legacy, fixed = TRUE))

no_ref <- run(composed(list(list(block = 'series-trend', instance_id = 'series-a'))),
              list(series_record('series-a')))
stopifnot(grepl('This composition selects no standalone reference-comparison block', no_ref, fixed = TRUE))
stopifnot(!grepl('legacy, non-composed', no_ref, fixed = TRUE))
stopifnot(grepl('saved annual series', no_ref, fixed = TRUE))

missing <- run(composed(list(list(block = 'reference-comparison', instance_id = 'ref-x'))), list())
stopifnot(grepl('Requested reference comparison unavailable', missing, fixed = TRUE))
stopifnot(grepl('ref-x', missing, fixed = TRUE))
stopifnot(!grepl('legacy, non-composed', missing, fixed = TRUE))

failed <- run(composed(list(list(block = 'reference-comparison', instance_id = 'ref-x'))),
              list(ref_record('ref-x', status = 'failed')))
stopifnot(grepl('Requested reference comparison unavailable', failed, fixed = TRUE))

wrong_id <- run(composed(list(list(block = 'reference-comparison', instance_id = 'ref-x'))),
                list(ref_record('ref-y')))
stopifnot(grepl('Requested reference comparison unavailable', wrong_id, fixed = TRUE))
stopifnot(!grepl('60.0%', wrong_id, fixed = TRUE))

valid <- run(composed(list(list(block = 'reference-comparison', instance_id = 'ref-x'))),
             list(ref_record('ref-x')))
stopifnot(grepl('+60.0%', valid, fixed = TRUE))
stopifnot(grepl('virus:reference_change', valid, fixed = TRUE))

cat('r-methods-boundary smoke passed\n')
