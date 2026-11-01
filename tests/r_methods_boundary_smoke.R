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

run <- function(composition, blocks, route = NULL) {
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
  methods_html(b, navigation = FALSE, composed = route)
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

# Source-state wording comes from the recorded provenance only: never re-derived from a SHA, and
# never guessed as clean when the Git state is absent or unreadable.
run_state <- function(code, blocks = list(ref_record('ref-a'))) {
  dir <- tempfile(); dir.create(dir)
  prov <- list(blocks = blocks, code = code)
  writeLines(toJSON(prov, auto_unbox = TRUE, null = 'null', na = 'null'),
             file.path(dir, 'provenance.json'))
  owd <- setwd(dir); on.exit(setwd(owd), add = TRUE)
  methods_html(b, navigation = FALSE)
}
state <- function(label, detail, availability)
  list(git_commit = 'abc123def456', git_worktree_clean = TRUE,
       source_state = list(state = 'clean', commit = 'abc123def456', label = label,
                           detail = detail, availability = availability))

clean_text <- run_state(state('clean worktree at the recorded commit',
                              'FIXTURE clean detail for commit abc123def456.',
                              'FIXTURE availability: supply the checkout separately.'))
stopifnot(grepl('FIXTURE clean detail for commit abc123def456.', clean_text, fixed = TRUE))
stopifnot(grepl('FIXTURE availability: supply the checkout separately.', clean_text, fixed = TRUE))
stopifnot(!grepl('candidate source is uncommitted', clean_text, fixed = TRUE))
stopifnot(!grepl('not determined', clean_text, fixed = TRUE))

dirty <- state('uncommitted changes present',
               'FIXTURE dirty detail: uncommitted changes present.',
               'FIXTURE availability: supply the checkout separately.')
dirty_text <- run_state(dirty)
stopifnot(grepl('FIXTURE dirty detail: uncommitted changes present.', dirty_text, fixed = TRUE))
stopifnot(!grepl('clean worktree', dirty_text, fixed = TRUE))

unknown <- state('source state not determined',
                 'FIXTURE unknown detail: not determined and not evidence of a clean tree.',
                 'FIXTURE availability: supply the checkout separately.')
unknown_text <- run_state(unknown)
stopifnot(grepl('not determined and not evidence of a clean tree', unknown_text, fixed = TRUE))

# A provenance that predates the recorded field must not imply clean.
legacy_text <- run_state(list(git_commit = 'abc123def456', git_worktree_clean = NULL))
stopifnot(grepl('Source state was not recorded in this provenance record', legacy_text, fixed = TRUE))
stopifnot(grepl('Neither the source checkout nor the container image is part of this package',
                legacy_text, fixed = TRUE))
stopifnot(!grepl('clean worktree', legacy_text, fixed = TRUE))

# The composed settings panel reads the same recorded label and availability.
summary_dir <- tempfile(); dir.create(summary_dir)
summary_prov <- list(
  code = list(git_commit = 'abc123def456',
              source_state = list(state = 'clean', commit = 'abc123def456',
                                  label = 'clean worktree at the recorded commit',
                                  detail = 'FIXTURE detail.',
                                  availability = 'FIXTURE availability: supply the checkout separately.')),
  data = list(publisher = 'FOPH/BAG IDD', canonical_root = '/baseline/snapshots/x',
              snapshot_manifest = NULL, publishing_date_range = list('2026-01-01'),
              retrieved_at_utc_range = list('2026-01-02T00:00:00Z')),
  rendered_at_utc = '2026-01-02T00:00:00Z')
writeLines(toJSON(summary_prov, auto_unbox = TRUE, null = 'null'), file.path(summary_dir, 'provenance.json'))
old_summary <- setwd(summary_dir)
b_summary <- b
b_summary$cfg$id <- 'researcher'
b_summary$cfg$title <- 'Researcher'
b_summary$cfg$presentation <- list(layout = 'technical', detail_level = 'full', display_name = 'Researcher')
summary_html <- provenance_summary(b_summary, raw_links = FALSE)
setwd(old_summary)
stopifnot(grepl('clean worktree at the recorded commit', summary_html, fixed = TRUE))
stopifnot(grepl('FIXTURE availability: supply the checkout separately.', summary_html, fixed = TRUE))
stopifnot(!grepl('uncommitted changes present', summary_html, fixed = TRUE))

# A host-supplied identity shows the recorded commit and says what was verified.
supplied <- list(
  git_commit = NULL, git_worktree_clean = NULL,
  source_identity = list(origin = 'host-supplied', verification = 'supplied-digest-match',
                         commit = 'abc123def456', tracked_dirty = FALSE,
                         untracked_inputs = 0, untracked_outside_inputs = 0),
  source_state = list(state = 'clean', commit = 'abc123def456',
                      label = 'clean worktree at the recorded commit',
                      detail = 'FIXTURE host-supplied detail.',
                      availability = 'FIXTURE availability: supply the checkout separately.'))
supplied_dir <- tempfile(); dir.create(supplied_dir)
supplied_prov <- summary_prov
supplied_prov$code <- supplied
writeLines(toJSON(supplied_prov, auto_unbox = TRUE, null = 'null'),
           file.path(supplied_dir, 'provenance.json'))
old_supplied <- setwd(supplied_dir)
supplied_text <- provenance_summary(b_summary, raw_links = FALSE)
setwd(old_supplied)
stopifnot(grepl('abc123def456', supplied_text, fixed = TRUE))
stopifnot(grepl('commit and tree host-reported', supplied_text, fixed = TRUE))
stopifnot(grepl('content verified in the runtime', supplied_text, fixed = TRUE))

cat('r-methods-boundary smoke passed\n')

# Route-aware reproduction/navigation; preserve all existing tests.
canonical_explicit <- run(NULL, list(ref_record('ref-a')), route = FALSE)
composed_explicit <- run(
  composed(list(list(block = 'reference-comparison', instance_id = 'ref-x'))),
  list(ref_record('ref-x')), route = TRUE)
for (text in list(legacy, canonical_explicit)) {
  stopifnot(!grepl('href="reproduction/composition.json"', text, fixed = TRUE))
  stopifnot(!grepl('href="reproduction/reproduction.json"', text, fixed = TRUE))
  stopifnot(grepl('This canonical package does not publish a composition recipe', text, fixed = TRUE))
  stopifnot(!grepl('effective recipe digest appears', text, fixed = TRUE))
  stopifnot(!grepl('report.html#quality-summary', text, fixed = TRUE))
}
for (text in list(valid, composed_explicit)) {
  stopifnot(grepl('href="reproduction/composition.json"', text, fixed = TRUE))
  stopifnot(grepl('href="reproduction/reproduction.json"', text, fixed = TRUE))
}
canonical_quality <- quality_methods_html(b_summary, composed = FALSE)
composed_quality <- quality_methods_html(b_summary, composed = TRUE)
stopifnot(grepl('href="report.html">', canonical_quality, fixed = TRUE))
stopifnot(!grepl('report.html#quality-summary', canonical_quality, fixed = TRUE))
stopifnot(grepl('report.html#quality-summary', composed_quality, fixed = TRUE))
stopifnot(identical(quality_methods_html(b_summary), composed_quality))
cat('route-aware methods regression passed\n')
