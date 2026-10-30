# Saved annual series smoke: plot data, gap segments, exact table, typed selection.
suppressPackageStartupMessages({library(jsonlite); library(knitr)})
knitr::opts_knit$set(rmarkdown.pandoc.to = 'html')
project <- Sys.getenv('HEALTH_REPORT_PROJECT')
if(!nzchar(project)) stop('HEALTH_REPORT_PROJECT is required')
templates <- file.path(project, 'scripts', 'health_pipeline', 'templates')
old <- setwd(templates); on.exit(setwd(old), add = TRUE)
source('report_helpers.R')

b <- list(
  cfg = list(id = 'researcher', title = 'Series test', years = c(2021, 2025),
             reference_year = 2019, geography = 'CHFL', period_type = 'year',
             outputs = c('headline', 'quality'),
             presentation = list(display_name = 'Researcher', layout = 'technical',
                                 detail_level = 'full', version = '1.0')),
  manifest = list(snapshot_id = strrep('a', 64)),
  classes = data.frame(topic = 'virus', label = 'Virus', stringsAsFactors = FALSE),
  selection = data.frame(dataset_id = 'ds1', topic = 'virus',
                         source_system = 'mandatory_reporting_system',
                         status = 'included', reason = '', group_eligible = 'True',
                         stringsAsFactors = FALSE),
  checks = data.frame(dataset_id = c('ds1', 'ds1', 'other'),
                      check = c('no_duplicate_rows', 'value_present', 'value_present'),
                      status = c('PASS', 'PASS', 'WARN'),
                      detail = c('0', '0% missing', '12.5% missing'),
                      stringsAsFactors = FALSE))

series_record <- function(instance, years, values, requested, missing,
                          status = 'verified', reference_outside = TRUE, style = NULL) {
  observations <- Map(function(year, value)
    list(year = as.integer(year), count_metric_id = paste0('virus:', year, ':count'),
         value = as.character(value), unit = 'cases'), years, values)
  entry <- list(
    status = status, instance_id = instance,
    component = list(type = 'series-trend', version = '1'),
    contract = list(series = 'health-report/series-component/1'),
    selection = list(topic = 'virus', measure = 'cases', geography = 'CHFL',
                     dataset_id = 'ds1', source_system = 'mandatory_reporting_system'),
    periods = list(requested = as.integer(requested),
                   effective = as.integer(years), reference_year = 2019L,
                   reference_outside_window = reference_outside),
    missing_years = as.integer(missing),
    presentation = if(is.null(style)) list(unit = 'cases') else list(unit = 'cases', style = style),
    artifact = list(file = 'series.csv', digest = strrep('c', 64)),
    snapshot = list(snapshot_id = strrep('a', 64), snapshot_path = 'snapshots/example'),
    implementation = list(
      analysis = list(file = 'scripts/health_pipeline/analyse.py', sha256 = strrep('d', 64)),
      presentation = list(file = 'scripts/health_pipeline/templates/report_helpers.R',
                          sha256 = strrep('e', 64))),
    identities = list(analytical = strrep('1', 64), rows = strrep('2', 64),
                      instance = paste0('id-', instance)),
    effective = list(presentation = list(unit = 'cases')),
    trace = list(list(field = 'presentation.unit', source = 'author', value = 'cases')),
    reproduction = list(entry_point = 'snakemake --cores 2', snapshot_id = strrep('a', 64)),
    observations = observations)
  if(identical(status, 'failed')) {
    entry <- list(status = 'failed', instance_id = instance,
                  component = list(type = 'series-trend', version = '1'),
                  contract = list(series = 'health-report/series-component/1'),
                  code = 'selection', detail = 'no saved observations for this range')
  }
  entry
}

reference_record <- function(instance) list(
  status = 'verified', instance_id = instance,
  component = list(type = 'reference-comparison', version = '1'),
  contract = list(instance = 'health-report/composer-component/1',
                  evidence = 'health-report/composer-evidence/1'),
  subject = 'virus', reference_year = 2019L, latest_year = 2025L, measure = 'cases',
  reference_count = list(metric_id = 'virus:2019:count', value = '10'),
  latest_count = list(metric_id = 'virus:2025:count', value = '16'),
  result = list(metric_id = 'virus:reference_change', value = 60.0, unit = 'percent',
                formula = 'percent_change', availability = 'available'),
  effective = list(presentation = list(unit = 'percent', digits = 1L)),
  trace = list(list(field = 'presentation.digits', source = 'component', value = 1L)),
  identities = list(analytical = strrep('3', 64), result = strrep('4', 64),
                    instance = paste0('id-', instance)),
  snapshot = list(snapshot_id = strrep('a', 64), snapshot_path = 'snapshots/example'),
  implementation = list(
    analysis = list(file = 'scripts/health_pipeline/analyse.py', sha256 = strrep('d', 64)),
    presentation = list(file = 'scripts/health_pipeline/templates/report_helpers.R',
                        sha256 = strrep('e', 64))),
  reproduction = list(entry_point = 'snakemake --cores 2', snapshot_id = strrep('a', 64)),
  lineage = list(source_file = 'data/virus/data.csv', source_row = '2.0'))

count_of <- function(h, text) lengths(regmatches(h, gregexpr(text, h, fixed = TRUE)))

gap <- series_record('series-a', c(2021L, 2023L, 2024L), c('10', '14', '16'),
                     c(2021L, 2024L), 2022L)
single <- series_record('series-single', 2024L, '12', c(2021L, 2025L),
                        c(2021L, 2022L, 2023L, 2025L))
missing_end <- series_record('series-end', c(2021L, 2022L, 2023L), c('9', '11', '13'),
                             c(2021L, 2024L), 2024L)
zero <- series_record('series-zero', c(2021L, 2022L), c('10', '0'), c(2021L, 2022L), integer(0))
failed <- series_record('series-failed', 2021L, '1', c(2021L, 2025L), c(), status = 'failed')

evidence <- list(blocks = list(reference_record('ref-a'), gap, single, missing_end, zero, failed))
path <- tempfile(fileext = '.json')
writeLines(toJSON(evidence, auto_unbox = TRUE, null = 'null'), path)

# 1. Plot preparation uses real year positions and breaks segments at gaps.
d <- series_plot_data(gap)
stopifnot(identical(d$year, c(2021L, 2023L, 2024L)))
stopifnot(identical(d$value, c(10, 14, 16)))
stopifnot(identical(d$segment, c(1L, 2L, 2L)))
stopifnot(nrow(series_plot_data(single)) == 1L)
stopifnot(identical(series_plot_data(single)$segment, 1L))

# 2. Exact-value table lists every requested year; missing years are not zero.
values <- series_value_rows(gap)
stopifnot(identical(values$Year, c(2021L, 2022L, 2023L, 2024L)))
stopifnot(identical(values$Value, c('10', 'Not available', '14', '16')))
stopifnot(identical(values$Availability, c('Reported', 'Not available', 'Reported', 'Reported')))
stopifnot(identical(series_value_rows(missing_end)$Value[[4]], 'Not available'))

# 2b. A recorded zero is a value, not a missing period.
zero_values <- series_value_rows(zero)
stopifnot(identical(zero_values$Value, c('10', '0')))
stopifnot(identical(zero_values$Availability, c('Reported', 'Reported')))
zero_html <- series_trend_block(b, path, instance_id = 'series-zero')
stopifnot(grepl('2021–2022', zero_html, fixed = TRUE))

# 3. Typed selection: the series record is second in the file, so positional fallback
#    would return the reference record. Only the typed, id-matching record is used.
html <- series_trend_block(b, path, instance_id = 'series-a')
stopifnot(grepl('2021–2024', html, fixed = TRUE))
stopifnot(grepl('No saved observation exists for 2022', html, fixed = TRUE))
stopifnot(grepl('belongs to the adjacent reference comparison', html, fixed = TRUE))
stopifnot(grepl('displayed years 2021, 2023, 2024', html, fixed = TRUE))
stopifnot(count_of(html, 'id="series-a-inspect"') == 1L)
stopifnot(count_of(html, 'id="series-a-values"') == 1L)
stopifnot(count_of(html, 'data/series.csv') == 1L)
stopifnot(grepl('22 recorded check results', html, fixed = FALSE) == FALSE)
stopifnot(grepl('2 recorded check results for this dataset', html, fixed = TRUE))
stopifnot(grepl('Dataset-level only; finding-level warning relevance has not been evaluated.',
                html, fixed = TRUE))
for(word in c('rise', 'decline', 'outbreak', 'forecast', 'steady')) {
  stopifnot(!grepl(word, html, ignore.case = TRUE))
}

# 4. A wrong instance id or a different block type is unavailable, not a fallback.
absent <- series_trend_block(b, path, instance_id = 'series-absent')
stopifnot(grepl('no checked series-trend record for block instance series-absent',
                absent, fixed = TRUE))
wrong_type <- series_trend_block(b, path, instance_id = 'ref-a')
stopifnot(grepl('no checked series-trend record for block instance ref-a',
                wrong_type, fixed = TRUE))
stopifnot(!grepl('+60.0%', wrong_type, fixed = TRUE))
reference <- reference_block(b, path, variant = 'composed', instance_id = 'ref-a')
stopifnot(grepl('+60.0%', reference, fixed = TRUE))
stopifnot(!grepl('2021–2024', reference, fixed = TRUE))
legacy_reference <- reference_block(b, path)
stopifnot(grepl('+60.0%', legacy_reference, fixed = TRUE))
stopifnot(grepl('id="block-reference-comparison"', legacy_reference, fixed = TRUE))

# 5. A failed check renders an honest unavailable state with no values.
failed_html <- series_trend_block(b, path, instance_id = 'series-failed')
stopifnot(grepl('Reported values over time unavailable', failed_html, fixed = TRUE))
stopifnot(grepl('selection: no saved observations for this range', failed_html, fixed = TRUE))
stopifnot(!grepl('data/series.csv', failed_html, fixed = TRUE))
stopifnot(!grepl('Inspect this block', failed_html, fixed = TRUE))

# 6. A single observation is a point, with explicit wording that no pattern is assessed.
single_html <- series_trend_block(b, path, instance_id = 'series-single')
stopifnot(grepl('no temporal pattern can be assessed', single_html, fixed = TRUE))
stopifnot(grepl('shown as a single point', single_html, fixed = TRUE))
stopifnot(grepl('No saved observation exists for 2021, 2022, 2023, 2025',
                single_html, fixed = TRUE))
stopifnot(nrow(series_plot_data(single)) == 1L)

# 7. The composer places the block by recipe and names the section from instance_id.
recipes <- list(list(block = 'intro', instance_id = 'intro-0001'),
                list(block = 'series-trend', instance_id = 'series-a',
                     topic = 'virus', measure = 'cases'),
                list(block = 'reference-comparison', instance_id = 'ref-a', topic = 'virus'))
recipe_path <- tempfile(fileext = '.json')
writeLines(toJSON(list(contract = 'health-report/composition-recipe/2', audience = 'researcher',
                       blocks = recipes), auto_unbox = TRUE), recipe_path)
composed <- compose_report_html(b, recipe_path, evidence_file = path)
stopifnot(grepl('id="series-a"', composed, fixed = TRUE))
stopifnot(count_of(composed, 'href="#series-a"') == 1L)
stopifnot(grepl('Annual trend for one disease', composed, fixed = TRUE))
stopifnot(grepl('2021–2024', composed, fixed = TRUE))
stopifnot(grepl('id="ref-a-inspect"', composed, fixed = TRUE))

# 7b. The series figure is narrowly scoped, width-limited and aspect-preserving. This is a
# markup/style assertion, not a browser geometry test.
stopifnot(count_of(composed, 'class="series-figure"') == 1L)
stopifnot(grepl('<figure class="series-figure"><img alt=', composed, fixed = TRUE))
stopifnot(grepl('.composed-report .series-figure{margin:14px 0 8px;width:100%;max-width:680px}',
                composed, fixed = TRUE))
stopifnot(grepl('.composed-report .series-figure img{display:block;width:100%;max-width:100%;height:auto}',
                composed, fixed = TRUE))
# Long provenance paths and identifiers keep their full text but may break anywhere.
stopifnot(grepl('.composed-report .provenance-list dd code,.composed-report .report-settings td code,.composed-report .audit-row strong,.composed-report .audit-row code{min-width:0;overflow-wrap:anywhere;white-space:normal}',
                composed, fixed = TRUE))
stopifnot(!grepl('<img width=', composed, fixed = TRUE))
stopifnot(!grepl('style="width', composed, fixed = TRUE))
stopifnot(grepl('Annual reported cases for Virus, 2021–2024', composed, fixed = TRUE))

# 8. Closed presentation style: compact selects a smaller figure and marks itself, while
#    values, gap segmentation, evidence and limitations stay identical. Omitted style keeps
#    the previous markup exactly (no style row, no compact class).
standard <- series_record('series-standard', c(2021L, 2023L, 2024L), c('10', '14', '16'),
                          c(2021L, 2024L), 2022L, style = 'standard')
compact <- series_record('series-compact', c(2021L, 2023L, 2024L), c('10', '14', '16'),
                         c(2021L, 2024L), 2022L, style = 'compact')
styled_path <- tempfile(fileext = '.json')
writeLines(toJSON(list(blocks = list(standard, compact)), auto_unbox = TRUE, null = 'null'),
           styled_path)
standard_html <- series_trend_block(b, styled_path, instance_id = 'series-standard')
compact_html <- series_trend_block(b, styled_path, instance_id = 'series-compact')
stopifnot(grepl('series-figure series-figure--compact', compact_html, fixed = TRUE))
stopifnot(!grepl('series-figure--compact', standard_html, fixed = TRUE))
stopifnot(grepl('Presentation style', standard_html, fixed = TRUE))
stopifnot(grepl('Presentation style', compact_html, fixed = TRUE))
stopifnot(identical(series_plot_data(standard), series_plot_data(compact)))
for(value in c('10', '14', '16', 'No saved observation exists for 2022',
               'Not available', 'Download the saved series rows')) {
  stopifnot(grepl(value, standard_html, fixed = TRUE))
  stopifnot(grepl(value, compact_html, fixed = TRUE))
}
stopifnot(!identical(standard_html, compact_html))
# Omitted style is byte-compatible with the pre-extension presentation.
stopifnot(!grepl('Presentation style', html, fixed = TRUE))
stopifnot(!grepl('series-figure--compact', html, fixed = TRUE))
# Responsive and wrapping rules survive the added style.
stopifnot(grepl('.composed-report .series-figure{margin:14px 0 8px;width:100%;max-width:680px}',
                composed, fixed = TRUE))
stopifnot(grepl('.composed-report .series-figure--compact{margin:10px 0 6px}',
                composed, fixed = TRUE))
stopifnot(grepl('.composed-report .series-figure img{display:block;width:100%;max-width:100%;height:auto}',
                composed, fixed = TRUE))

# 9. Composite renderers select by type+instance and stay display-only. Records below are
#    synthetic fixtures, not findings in the retained data.
implementation <- list(presentation = list(file = 'report_helpers.R', sha256 = strrep('3', 64)),
                       binding = list(file = 'publish.py', sha256 = strrep('4', 64)),
                       contracts = list(file = 'composer_contracts.py', sha256 = strrep('5', 64)))
cov <- list(status = 'verified', instance_id = 'cov-a',
  component = list(type = 'coverage-selection', version = '1'), binding = 'saved-records/1',
  counts = list(datasets_total = 56L, datasets_included = 12L, datasets_excluded = 44L,
                topics_included = 12L, topics_excluded = 6L, observations_saved = 72L,
                sources_recorded = 56L, sources_used = 12L),
  requested = list(years = c(2021L, 2025L), geography = 'CHFL'),
  topics_included = list('virus'),
  excluded = list(list(topic = 'measles', reasons = list('No explicit CHFL total'))),
  displayed_topics = list('virus'),
  unsupported = list('A topic-by-year completeness matrix is not available.'),
  identities = list(analytical = strrep('1', 64), instance = 'cov-inst'),
  bindings = list(list(file = 'selection.csv', digest = strrep('2', 64))),
  snapshot = list(snapshot_id = strrep('a', 64)), implementation = implementation,
  reproduction = list(entry_point = 'publish.py batch'))
mon <- list(status = 'verified', instance_id = 'mon-a',
  component = list(type = 'monitoring-overview', version = '1'), binding = 'saved-records/1',
  rows = list(list(topic = 'virus', availability = 'saved observation', measure = 'cases',
                   latest_year = 2025L, latest_value = '16', latest_metric_id = 'virus:2025:count',
                   comparisons = list(list(metric_id = 'virus:reference_change',
                                           type = 'reference_change', value = '60.0',
                                           unit = 'percent', from_year = '2019', to_year = '2025')),
                   recorded_checks = list()),
              list(topic = 'ghost', availability = 'no saved annual observation',
                   recorded_checks = list())),
  units = list('cases'), limits = list('No composite score is derived.'),
  identities = list(analytical = strrep('6', 64), instance = 'mon-inst'),
  bindings = list(list(file = 'series.csv', digest = strrep('7', 64))),
  snapshot = list(snapshot_id = strrep('a', 64)), implementation = implementation,
  reproduction = list(entry_point = 'publish.py batch'))
spec <- function(subject, role, members, latest, change) list(
  subject = subject, role = role, members = as.list(members),
  reference = list(year = 2019L, metric_id = paste0(subject, ':2019:total'),
                   value = '7253.0', unit = 'cases'),
  latest = list(year = 2025L, metric_id = paste0(subject, ':2025:total'),
                value = latest, unit = 'cases'),
  reference_change = list(metric_id = paste0(subject, ':reference_change'),
                          value = change, unit = 'percent'),
  member_metric_ids = lapply(members, function(m) paste0(m, ':2025:count')),
  artifact = list(file = 'metrics.csv', digest = strrep('b', 64)))
sens <- list(status = 'verified', instance_id = 'sens-a',
  component = list(type = 'sensitivity-comparison', version = '1'), binding = 'saved-records/1',
  pairs = list(list(class = 'viral',
    specifications = list(spec('viral:main', 'main', c('virus', 'bacterium'), '8716.0', '20.2'),
                          spec('viral:sensitivity', 'sensitivity', 'virus', '8600.0', '18.6')),
    excluded_members = list('bacterium'), added_members = list())),
  question = 'How do the saved specifications differ?',
  limits = list('This is not a robustness assessment.'),
  identities = list(analytical = strrep('8', 64), instance = 'sens-inst'),
  bindings = list(list(file = 'metrics.csv', digest = strrep('9', 64))),
  snapshot = list(snapshot_id = strrep('a', 64)), implementation = implementation,
  reproduction = list(entry_point = 'publish.py batch'))
comp_path <- tempfile(fileext = '.json')
writeLines(toJSON(list(blocks = list(cov, mon, sens)), auto_unbox = TRUE, null = 'null'),
           comp_path)

cov_html <- coverage_selection_block(b, comp_path, instance_id = 'cov-a')
stopifnot(grepl('Saved selection counts', cov_html, fixed = TRUE))
stopifnot(grepl('Datasets recorded', cov_html, fixed = TRUE))
stopifnot(grepl('Topics displayed individually by this report:', cov_html, fixed = TRUE))
stopifnot(grepl('No explicit CHFL total', cov_html, fixed = TRUE))
stopifnot(grepl('id="cov-a-excluded"', cov_html, fixed = TRUE))
stopifnot(count_of(cov_html, 'id="cov-a-inspect"') == 1L)
mon_html <- monitoring_overview_block(b, comp_path, instance_id = 'mon-a')
stopifnot(grepl('Latest saved observation by topic', mon_html, fixed = TRUE))
stopifnot(grepl('no saved annual observation', mon_html, fixed = TRUE))
stopifnot(grepl('Reference +60.0% (2019→2025)', mon_html, fixed = TRUE))
stopifnot(grepl('id="mon-a-bindings"', mon_html, fixed = TRUE))
# No series-collection record in this report: the monitoring table keeps its plain rows.
stopifnot(count_of(mon_html, 'data-panel-link') == 0L)
stopifnot(count_of(mon_html, 'panel-link-note') == 0L)
stopifnot(count_of(mon_html, '<script') == 0L)
sens_html <- sensitivity_comparison_block(b, comp_path, instance_id = 'sens-a')
stopifnot(grepl('viral group', sens_html, fixed = TRUE))
stopifnot(grepl('bacterium', sens_html, fixed = TRUE))
stopifnot(grepl('not a robustness assessment', sens_html, fixed = TRUE))
wrong_type <- coverage_selection_block(b, comp_path, instance_id = 'mon-a')
stopifnot(grepl('no checked coverage-selection record for block instance mon-a',
                wrong_type, fixed = TRUE))
stopifnot(all(c('coverage-selection', 'monitoring-overview', 'sensitivity-comparison') %in%
                names(composition_registry)))

# The narrow-screen filter layout and composite table rules are scoped CSS, not browser tests.
style_text <- composition_style()
stopifnot(grepl('.composed-report .table-scroll{overflow-x:auto;max-width:100%}',
                style_text, fixed = TRUE))
stopifnot(grepl('@media (max-width:480px)', style_text, fixed = TRUE))
quality_source <- paste(deparse(quality_methods_html), collapse = '\n')
stopifnot(grepl('.quality-controls>div{min-width:0;flex:1 1 14rem;max-width:100%}',
                quality_source, fixed = TRUE))
stopifnot(grepl('.quality-controls select,.quality-controls input{max-width:100%;width:100%;box-sizing:border-box}',
                quality_source, fixed = TRUE))

# The public/editorial reference variant leads with plain-language copy, same values.
b_public <- b
b_public$cfg$presentation <- list(display_name = 'General public', layout = 'editorial',
                                  detail_level = 'plain_language', version = '1.0')
public_html <- reference_block(b_public, path, variant = 'composed', instance_id = 'ref-a')
stopifnot(grepl('finding--editorial', public_html, fixed = TRUE))
stopifnot(grepl('In plain terms:', public_html, fixed = TRUE))
stopifnot(grepl('+60.0%', public_html, fixed = TRUE))

cat('r-series smoke passed\n')
