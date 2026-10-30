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

write_recipe <- function(blocks, contract = 'health-report/composition-recipe/1',
                         titles = NULL) {
  path <- tempfile(fileext = '.json')
  payload <- list(contract = contract, audience = 'test', blocks = blocks)
  if(!is.null(titles)) payload$titles <- titles
  writeLines(toJSON(payload, auto_unbox = TRUE), path)
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

# 2b. v2 recipes compose the same way; the topic is a binding field, not renderer input.
v2_recipe <- write_recipe(list(list(block = 'alpha', instance_id = 'i-alpha',
                                    topic = 'virus'),
                               list(block = 'beta', instance_id = 'i-beta')),
                          contract = 'health-report/composition-recipe/2')
html_v2 <- compose_report_html(b, v2_recipe, registry = registry)
stopifnot(identical(section_ids(html_v2), c('i-alpha', 'i-beta')))

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
stopifnot(setequal(names(composition_labels),
                   c('intro', 'series-trend', 'series-collection', 'reference-comparison',
                     'coverage-selection', 'monitoring-overview', 'sensitivity-comparison',
                     'limitations', 'reproduction')))
stopifnot(identical(unname(composition_labels[c('intro', 'series-collection',
                                                 'reference-comparison', 'monitoring-overview',
                                                 'limitations')]),
                    c('Report context', 'Annual trends by disease',
                      'Change from the reference year', 'Latest observations by disease',
                      'Limitations and cautions')))
stopifnot(!grepl('dash-footer', html_a, fixed = TRUE))
stopifnot(!grepl('presentation_open', html_a, fixed = TRUE))

# 8. Real registry shape and persistent researcher recipe blocks.
stopifnot(identical(sort(names(composition_registry)),
                    sort(c('intro', 'series-trend', 'series-collection', 'coverage-selection',
                           'monitoring-overview', 'sensitivity-comparison',
                           'reference-comparison', 'limitations', 'reproduction'))))
stopifnot(all(vapply(composition_registry, function(spec)
  is.list(spec) && is.function(spec$render) && is.character(spec$label), logical(1))))
recipe <- jsonlite::fromJSON(file.path(project, 'scripts', 'health_pipeline', 'config', 'composer',
                                       'compositions', 'researcher.json'), simplifyVector = FALSE)
stopifnot(identical(vapply(recipe$blocks, function(x) x$block, character(1)),
                    c('intro', 'series-collection', 'coverage-selection',
                      'sensitivity-comparison', 'reference-comparison',
                      'limitations', 'reproduction')))
instance_ids <- vapply(recipe$blocks, function(x) x$instance_id, character(1))
stopifnot(identical(instance_ids,
                    c('intro-0001', 'researcher-series-collection', 'block-coverage-selection',
                      'block-sensitivity-comparison', 'block-reference-comparison',
                      'limitations-0001', 'reproduction-0001')))

# 8b. The three audience recipes declare themselves and keep evidence/limitations.
expected_orders <- list(
  researcher = c('intro', 'series-collection', 'coverage-selection',
                 'sensitivity-comparison', 'reference-comparison',
                 'limitations', 'reproduction'),
  health_institution = c('intro', 'monitoring-overview', 'series-collection',
                         'reference-comparison', 'limitations', 'reproduction'),
  public = c('intro', 'reference-comparison', 'series-collection',
             'limitations', 'reproduction'))
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
  status = 'verified', instance_id = instance,
  component = list(type = 'reference-comparison', version = '1'), subject = 'virus',
  reference_year = 2019L, latest_year = 2025L, measure = 'cases',
  reference_count = list(metric_id = 'virus:2019:count', value = '10'),
  latest_count = list(metric_id = 'virus:2025:count', value = '16'),
  result = list(metric_id = 'virus:reference_change', value = 60.0, unit = 'percent',
                formula = 'percent_change', availability = 'available'),
  effective = list(presentation = list(unit = 'percent', digits = 1L)),
  trace = list(list(field = 'presentation.digits', source = 'component', value = 1L)),
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
stopifnot(grepl('no checked reference-comparison record for block instance ref-absent', missing, fixed = TRUE))
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
             period_type = 'year', outputs = c('headline', 'quality', 'sources'),
             presentation = list(display_name = layout, layout = layout,
                                 detail_level = detail, version = '1.0')),
  manifest = list(snapshot_id = strrep('d', 64),
                  files = c(stakeholder.json = strrep('a', 64), metrics.csv = strrep('b', 64),
                            lineage.csv = strrep('c', 64))),
  classes = data.frame(topic = 'virus', label = 'Virus', stringsAsFactors = FALSE),
  sources = data.frame(dataset_id = 'ds-virus', topic = 'virus',
                       source_system = 'mandatory_reporting_system', used = 'True',
                       stringsAsFactors = FALSE),
  selection = data.frame(dataset_id = 'ds-virus', topic = 'virus',
                         source_system = 'mandatory_reporting_system',
                         status = 'included', reason = '', group_eligible = 'True',
                         stringsAsFactors = FALSE),
  checks = data.frame(dataset_id = rep('ds-virus', 4),
                      check = c('no_duplicate_rows', 'value_present', 'cantons_sum_to_national', 'value_present'),
                      status = c('PASS', 'WARN', 'SKIP', 'PASS'),
                      detail = c('0', '12.5% missing', 'Requires 26 cantons', '0% missing'),
                      stringsAsFactors = FALSE))
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
stopifnot(grepl('Monitoring context:', dash, fixed = TRUE))
stopifnot(grepl('Monitoring context: latest saved annual notification counts', dash, fixed = TRUE))
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

# 12. Shared quality preparation, summary link, methods detail and escaping.
warning_b <- function(checks, selection_status = 'included') {
  b <- audience_b('technical', 'full')
  b$checks <- checks
  b$sources <- data.frame(dataset_id = c('ds-virus', 'ds-other'),
                          topic = c('virus', 'other_signal'),
                          source_system = c('mandatory_reporting_system', 'sentinella_reporting_system'),
                          used = c('True', 'False'), stringsAsFactors = FALSE)
  b$selection <- data.frame(dataset_id = c('ds-virus', 'ds-other'),
                            topic = c('virus', 'other_signal'),
                            source_system = c('mandatory_reporting_system', 'sentinella_reporting_system'),
                            status = c(selection_status, 'excluded'),
                            reason = c('', 'surveillance_signal: not a classified count series'),
                            group_eligible = c('True', 'False'), stringsAsFactors = FALSE)
  b
}
checks_mixed <- data.frame(
  dataset_id = c('ds-virus', 'ds-virus', 'ds-virus', 'ds-other', 'ds-other', 'ds-other'),
  check = c('no_duplicate_rows', 'value_present', 'mystery_rule', 'value_present',
            'cantons_sum_to_national', 'periods_parseable'),
  status = c('PASS', 'WARN', 'WARN', 'WARN', 'SKIP', 'PASS'),
  detail = c('0', '12.5% missing', '<script>alert(1)</script>', '52.7% missing',
             'Requires 26 cantons', '0'),
  stringsAsFactors = FALSE)
b_mixed <- warning_b(checks_mixed)
summary_html <- quality_summary_html(b_mixed)
methods_q <- quality_methods_html(b_mixed)
totals_line <- '6 recorded check-result rows covering 5 distinct rule identifiers and 2 datasets: 2 PASS, 1 SKIP, 3 WARN, 0 FAIL.'

# The same prepared records drive both pages.
stopifnot(identical(quality_totals(quality_results(b_mixed)),
                    quality_totals(quality_results(b_mixed))))
stopifnot(grepl(totals_line, summary_html, fixed = TRUE))
stopifnot(grepl(totals_line, methods_q, fixed = TRUE))
stopifnot(grepl('id="quality-summary"', summary_html, fixed = TRUE))
stopifnot(grepl('href="methods.html#quality-checks"', summary_html, fixed = TRUE))
stopifnot(grepl('Inspect all checks and detailed warning explanations', summary_html, fixed = TRUE))
stopifnot(grepl('Download exact check results — CSV', summary_html, fixed = TRUE))
stopifnot(grepl('<summary>What was flagged?</summary>', summary_html, fixed = TRUE))
stopifnot(grepl('Missing values', summary_html, fixed = TRUE))
stopifnot(grepl('Some warnings concern datasets recorded as included, or their selection mapping is unresolved.',
                summary_html, fixed = TRUE))

stopifnot(grepl('id="quality-checks"', methods_q, fixed = TRUE))
stopifnot(grepl('Report audience: <strong>technical</strong>', methods_q, fixed = TRUE))
stopifnot(grepl('Saved scope: Switzerland and Liechtenstein; reporting years 2021–2025; reference year 2019.', methods_q, fixed = TRUE))
stopifnot(grepl('href="report.html#quality-summary"', methods_q, fixed = TRUE))
stopifnot(grepl('<caption>All 6 recorded check results', methods_q, fixed = TRUE))
stopifnot(grepl('Showing all 6 recorded check results', methods_q, fixed = TRUE))
stopifnot(count_of(methods_q, '<tr data-status=') == 6L)
stopifnot(grepl('id="quality-status"', methods_q, fixed = TRUE))
stopifnot(grepl('id="quality-check"', methods_q, fixed = TRUE))
stopifnot(grepl('id="quality-search"', methods_q, fixed = TRUE))
stopifnot(grepl('Warnings and failures', methods_q, fixed = TRUE))
stopifnot(grepl('All results', methods_q, fixed = TRUE))
stopifnot(grepl('role="region"', methods_q, fixed = TRUE))
stopifnot(grepl('tabindex="0"', methods_q, fixed = TRUE))
stopifnot(grepl('scope="col"', methods_q, fixed = TRUE))
stopifnot(grepl('data/selection.csv', methods_q, fixed = TRUE))
stopifnot(grepl('data/sources.csv', methods_q, fixed = TRUE))
stopifnot(grepl('Share of rows with a missing value', methods_q, fixed = TRUE))
stopifnot(grepl('12.5% missing', methods_q, fixed = TRUE))
stopifnot(grepl('Unknown check', methods_q, fixed = TRUE))
stopifnot(grepl('No plain-language explanation is available for this check yet.', methods_q, fixed = TRUE))
stopifnot(grepl('&lt;script&gt;alert(1)&lt;/script&gt;', methods_q, fixed = TRUE))
stopifnot(!grepl('<script>alert(1)</script>', methods_q, fixed = TRUE))
stopifnot(grepl('surveillance_signal: not a classified count series', methods_q, fixed = TRUE))
stopifnot(grepl('finding-level warning relevance has not been evaluated', methods_q, fixed = TRUE))
filter_script <- quality_filter_script()
stopifnot(grepl("getElementById('quality-status')", filter_script, fixed = TRUE))
stopifnot(grepl("getElementById('quality-results-table')", filter_script, fixed = TRUE))
stopifnot(grepl("Showing '+shown+' of '+rows.length+' recorded check results", filter_script, fixed = TRUE))
stopifnot(!grepl('fetch(', filter_script, fixed = TRUE))
stopifnot(!grepl('data-searchable', methods_q, fixed = TRUE))
stopifnot(grepl('data-searchable="true"', html_table(data.frame(a = 1)), fixed = TRUE))
stopifnot(grepl('table.report-table[data-searchable]', interactive_tables_script(), fixed = TRUE))

excluded_only <- checks_mixed[checks_mixed$dataset_id == 'ds-other', ]
excl_html <- quality_summary_html(warning_b(excluded_only))
stopifnot(grepl("These warnings concern datasets recorded as excluded from this report's selected inputs. Finding-level warning relevance has not been evaluated.",
                excl_html, fixed = TRUE))

ambiguous <- warning_b(checks_mixed)
ambiguous$selection <- rbind(ambiguous$selection[1, ], ambiguous$selection[1, ])
amb_results <- quality_results(ambiguous)
stopifnot(any(grepl('Ambiguous selection mapping (2 rows)', amb_results$selection, fixed = TRUE)))
stopifnot(any(grepl('Relevance not established (ambiguous selection mapping)', amb_results$relevance, fixed = TRUE)))

missing_checks <- data.frame(dataset_id = 'ds-missing', check = 'value_present',
                             status = 'WARN', detail = '50.0% missing', stringsAsFactors = FALSE)
miss_results <- quality_results(warning_b(missing_checks))
stopifnot(identical(miss_results$selection, 'No selection record'))
stopifnot(identical(miss_results$dataset_label, 'Source metadata not recorded'))
stopifnot(identical(miss_results$relevance, 'Relevance not established (no selection record)'))

clean <- data.frame(dataset_id = 'ds-virus', check = c('no_duplicate_rows', 'periods_parseable'),
                    status = c('PASS', 'SKIP'), detail = c('0', 'No complete pair'),
                    stringsAsFactors = FALSE)
clean_b <- warning_b(clean)
clean_summary <- quality_summary_html(clean_b)
clean_methods <- quality_methods_html(clean_b)
stopifnot(grepl('No WARN or FAIL results are recorded in this bundle. That is not proof that source counts are complete or accurate.',
                clean_summary, fixed = TRUE))
stopifnot(!grepl('no relevant warnings', clean_summary, ignore.case = TRUE))
stopifnot(grepl('No WARN or FAIL results are recorded in this bundle.', clean_methods, fixed = TRUE))
stopifnot(!grepl('Detailed warning explanations', clean_methods, fixed = TRUE))

settings_dir <- tempfile('settings-')
dir.create(settings_dir)
old_settings <- setwd(settings_dir)
writeLines('{}', 'stakeholder.json')
writeLines('value', 'metrics.csv')
writeLines('id', 'lineage.csv')
writeLines('{}', 'bundle.json')
settings <- composed_settings_html(b_tech)
repro <- composition_registry$reproduction$render(b_tech,
          list(block = 'reproduction', instance_id = 'reproduction-test'))
setwd(old_settings)
stopifnot(grepl('Report settings and source files', settings, fixed = TRUE))
stopifnot(grepl('Reporting years', settings, fixed = TRUE))
stopifnot(grepl('2021–2025', settings, fixed = TRUE))
stopifnot(grepl('Reference year', settings, fixed = TRUE))
stopifnot(grepl('2019', settings, fixed = TRUE))
stopifnot(grepl('Switzerland and Liechtenstein', settings, fixed = TRUE))
stopifnot(grepl('technical · full', settings, fixed = TRUE))
stopifnot(grepl('aaaaaaaaaaaaaaaa', settings, fixed = TRUE))
stopifnot(grepl('not composed', settings, fixed = TRUE))
stopifnot(grepl('publishes 4 files', settings, fixed = TRUE))
stopifnot(grepl('not self-digested', settings, fixed = TRUE))
stopifnot(grepl('href="data/stakeholder.json" download', settings, fixed = TRUE))
stopifnot(grepl('href="data/metrics.csv" download', settings, fixed = TRUE))
stopifnot(grepl('href="data/bundle.json" download', settings, fixed = TRUE))
stopifnot(grepl('Download exact audience parameters — JSON', settings, fixed = TRUE))
stopifnot(grepl('Download bundle manifest — JSON', settings, fixed = TRUE))
stopifnot(grepl('Download Metrics — CSV', settings, fixed = TRUE))
stopifnot(grepl('Download Calculation lineage — CSV', settings, fixed = TRUE))
stopifnot(!grepl('data-searchable', settings, fixed = TRUE))
stopifnot(grepl('Show code: verify saved-file integrity and inspect results', repro, fixed = TRUE))
stopifnot(grepl('does not rerun the production analysis', repro, fixed = TRUE))
stopifnot(grepl('View report provenance — JSON', repro, fixed = TRUE))
stopifnot(grepl('href="#report-settings"', repro, fixed = TRUE))
stopifnot(grepl('Open methods and source traceability', repro, fixed = TRUE))
stopifnot(count_of(repro, 'href="data/metrics.csv"') == 1L)
provenance_links <- provenance_summary(b_tech)
stopifnot(grepl('Included topics', provenance_links, fixed = TRUE))
stopifnot(grepl('not restricted (all eligible topics)', provenance_links, fixed = TRUE))
stopifnot(grepl('Excluded topics', provenance_links, fixed = TRUE))
stopifnot(grepl('View report provenance — JSON', provenance_links, fixed = TRUE))
stopifnot(grepl('Download exact audience parameters — JSON', provenance_links, fixed = TRUE))
stopifnot(grepl('Download bundle manifest — JSON', provenance_links, fixed = TRUE))
stopifnot(grepl('Open methods and source traceability', provenance_links, fixed = TRUE))
stopifnot(grepl('href="data/stakeholder.json"', provenance_links, fixed = TRUE))
stopifnot(grepl('href="data/bundle.json"', provenance_links, fixed = TRUE))
without_raw <- provenance_summary(b_tech, raw_links = FALSE)
stopifnot(!grepl('href="data/stakeholder.json"', without_raw, fixed = TRUE))
stopifnot(!grepl('href="data/bundle.json"', without_raw, fixed = TRUE))
stopifnot(grepl('View report provenance — JSON', without_raw, fixed = TRUE))
b_scoped <- b_tech
b_scoped$cfg$include_topics <- c('virus', 'bacterium')
b_scoped$cfg$exclude_topics <- c('other_signal')
scoped_links <- provenance_summary(b_scoped)
stopifnot(grepl('virus, bacterium', scoped_links, fixed = TRUE))
stopifnot(grepl('other_signal', scoped_links, fixed = TRUE))

# 10. Section titles: heading, stable name nearby, escaping and navigation disambiguation.
titled <- write_recipe(list(list(block = 'alpha', instance_id = 'i-alpha'),
                            list(block = 'beta', instance_id = 'i-beta')),
                       titles = list('i-alpha' = 'Focus section'))
html_t <- compose_report_html(b, titled, registry = registry)
stopifnot(grepl('<h2 class="composed-heading">Focus section</h2>', html_t, fixed = TRUE))
stopifnot(grepl('<p class="composed-section-meta">Alpha</p>', html_t, fixed = TRUE))
stopifnot(grepl('<h2 class="composed-heading">Beta</h2>', html_t, fixed = TRUE))

escaped <- write_recipe(list(list(block = 'alpha', instance_id = 'i-alpha')),
                        titles = list('i-alpha' = '<script>alert(1)</script> & "quoted"'))
html_e <- compose_report_html(b, escaped, registry = registry)
stopifnot(!grepl('<script>alert(1)</script>', html_e, fixed = TRUE))
stopifnot(grepl('<h2 class="composed-heading">&lt;script&gt;alert(1)&lt;/script&gt; &amp; "quoted"</h2>',
                html_e, fixed = TRUE))
# The same text inside the navigation attribute is quote-escaped.
stopifnot(grepl('aria-label="Section 1 of 1: &lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;quoted&quot;"',
                html_e, fixed = TRUE))

# Two sections with the same title stay distinguishable in the navigation through their
# position, without exposing instance ids or inventing a difference.
same <- write_recipe(list(list(block = 'alpha', instance_id = 'i-1'),
                          list(block = 'alpha', instance_id = 'i-2')),
                     titles = list('i-1' = 'Repeated', 'i-2' = 'Repeated'))
html_s <- compose_report_html(b, same, registry = registry)
stopifnot(count_of(html_s, '<h2 class="composed-heading">Repeated</h2>') == 2L)
stopifnot(grepl('aria-label="Section 1 of 2: Repeated"', html_s, fixed = TRUE))
stopifnot(grepl('aria-label="Section 2 of 2: Repeated"', html_s, fixed = TRUE))
stopifnot(!grepl('i-1<', html_s, fixed = TRUE))

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
  stopifnot(grepl('What was flagged?', html, fixed = TRUE))
  stopifnot(grepl('Report settings and source files', html, fixed = TRUE))
  stopifnot(grepl('Download exact audience parameters — JSON', html, fixed = TRUE))
  stopifnot(grepl('Download bundle manifest — JSON', html, fixed = TRUE))
  stopifnot(grepl('Download Metrics — CSV', html, fixed = TRUE))
  stopifnot(grepl('Download Calculation lineage — CSV', html, fixed = TRUE))
  stopifnot(grepl('View report provenance — JSON', html, fixed = TRUE))
  stopifnot(!grepl('data-searchable="true"', html, fixed = TRUE))
  stopifnot(grepl('data/checks.csv', html, fixed = TRUE))
  stopifnot(grepl('href="methods.html#quality-checks"', html, fixed = TRUE))
  methods <- file.path(dirname(report), 'methods.html')
  stopifnot(file.exists(methods))
  mhtml <- paste(readLines(methods, warn = FALSE, encoding = 'UTF-8'), collapse = '\n')
  stopifnot(grepl('id="quality-checks"', mhtml, fixed = TRUE))
  stopifnot(grepl('href="report.html#quality-summary"', mhtml, fixed = TRUE))
  stopifnot(grepl('id="quality-results-table"', mhtml, fixed = TRUE))
  stopifnot(grepl('id="quality-status"', mhtml, fixed = TRUE))
  stopifnot(grepl('id="quality-check"', mhtml, fixed = TRUE))
  stopifnot(grepl('id="quality-search"', mhtml, fixed = TRUE))
  stopifnot(grepl('recorded check-result rows covering', mhtml, fixed = TRUE))
  stopifnot(grepl('Detailed warning explanations', mhtml, fixed = TRUE))
  stopifnot(grepl('data/checks.csv', mhtml, fixed = TRUE))
  cat('rendered composition checks passed:', audience, '\n')
}
