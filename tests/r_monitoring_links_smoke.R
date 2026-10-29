# Monitoring row -> collection panel links: exact topic/measure/source/window matching, a native
# anchor baseline and scoped progressive enhancement. Values are fixture strings; no calculation
# and no browser behaviour is exercised here (the script assertions are structural only).
suppressPackageStartupMessages({library(jsonlite); library(knitr)})
knitr::opts_knit$set(rmarkdown.pandoc.to = 'html')
project <- Sys.getenv('HEALTH_REPORT_PROJECT')
if(!nzchar(project)) stop('HEALTH_REPORT_PROJECT is required')
old <- setwd(file.path(project, 'scripts', 'health_pipeline', 'templates')); on.exit(setwd(old), add = TRUE)
source('report_helpers.R')

b <- list(
  cfg = list(id = 'health_institution', title = 'Links test', years = c(2021, 2025),
             reference_year = 2019, geography = 'CHFL', period_type = 'year',
             outputs = c('headline'), presentation = list(display_name = 'Health institution',
             layout = 'dashboard', detail_level = 'monitoring', version = '1.0')),
  manifest = list(snapshot_id = strrep('a', 64)),
  classes = data.frame(topic = c('alpha', 'beta', 'gamma', 'delta'),
                       label = c('Alpha', 'Beta', 'Gamma', 'Delta'), stringsAsFactors = FALSE),
  selection = data.frame(dataset_id = 'ds1', topic = c('alpha', 'beta', 'gamma', 'delta'),
                         source_system = 'mandatory_reporting_system', status = 'included',
                         reason = '', group_eligible = 'True', stringsAsFactors = FALSE),
  checks = data.frame(dataset_id = character(0), check = character(0),
                      status = character(0), detail = character(0), stringsAsFactors = FALSE))

member <- function(instance, topic, measure = 'cases', geography = 'CHFL', dataset = 'ds1',
                   years = 2021:2025, values = c(10, 12, 11, 14, 16)) {
  observations <- Map(function(year, value)
    list(year = as.integer(year), count_metric_id = paste0(topic, ':', year, ':count'),
         value = as.character(value), unit = 'cases'), years, values)
  list(status = 'verified', instance_id = instance,
       component = list(type = 'series-trend', version = '1'),
       contract = list(series = 'health-report/series-component/1'),
       selection = list(topic = topic, measure = measure, geography = geography,
                        dataset_id = dataset, source_system = 'mandatory_reporting_system'),
       periods = list(requested = c(2021L, 2025L), effective = as.integer(years),
                      reference_year = 2019L, reference_outside_window = TRUE),
       missing_years = as.integer(setdiff(2021:2025, years)),
       artifact = list(file = 'series.csv', digest = strrep('c', 64)),
       presentation = list(unit = 'cases', style = 'standard'),
       snapshot = list(snapshot_id = strrep('a', 64)),
       implementation = list(analysis = list(file = 'scripts/health_pipeline/analyse.py',
                                             sha256 = strrep('d', 64)),
                             presentation = list(file = 'scripts/health_pipeline/templates/report_helpers.R',
                                                 sha256 = strrep('e', 64))),
       identities = list(analytical = paste0('an-', topic), rows = paste0('row-', topic),
                         instance = paste0('inst-', topic)),
       effective = list(presentation = list(unit = 'cases')),
       trace = list(list(field = 'presentation.unit', source = 'author', value = 'cases')),
       reproduction = list(entry_point = 'snakemake --cores 2', snapshot_id = strrep('a', 64)),
       observations = observations)
}

collection <- function(members, default = NULL, status = 'verified', instance = 'sc-collection',
                       effective = c(2021L, 2022L, 2023L, 2024L, 2025L),
                       code = NULL, detail = NULL) {
  if(!identical(status, 'verified'))
    return(list(status = 'failed', instance_id = instance,
                component = list(type = 'series-collection', version = '1'),
                contract = list(collection = 'health-report/series-collection/1'),
                code = code, detail = detail))
  if(is.null(default)) default <- members[[1]]$selection$topic
  list(status = 'verified', instance_id = instance,
       component = list(type = 'series-collection', version = '1'),
       contract = list(series = 'health-report/series-component/1',
                       collection = 'health-report/series-collection/1'),
       topics = vapply(members, function(m) m$selection$topic, character(1)),
       ordering = 'eligible-ascending', measure = 'cases',
       presentation = list(style = 'compact', default_topic = default),
       periods = list(requested = c(2021L, 2025L), effective = as.integer(effective)),
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

row <- function(topic, measure = 'cases', dataset = 'ds1', year = 2025L, value = '16',
                availability = 'saved observation') list(
  topic = topic, availability = availability, measure = measure,
  latest_year = if(is.null(measure)) NULL else as.integer(year),
  latest_value = if(is.null(measure)) NULL else value,
  latest_metric_id = if(is.null(measure)) NULL else paste0(topic, ':2025:count'),
  dataset_id = if(is.null(measure)) NULL else dataset,
  comparisons = list(list(metric_id = paste0(topic, ':reference_change'),
                          type = 'reference_change', value = '60.0', unit = 'percent',
                          from_year = '2019', to_year = '2025')),
  recorded_checks = list())

monitor <- function(rows, instance = 'mon-a') list(
  status = 'verified', instance_id = instance,
  component = list(type = 'monitoring-overview', version = '1'), binding = 'saved-records/1',
  rows = rows, units = list('cases'), limits = list('No composite score is derived.'),
  identities = list(analytical = strrep('6', 64), instance = paste0(instance, '-inst')),
  bindings = list(list(file = 'series.csv', digest = strrep('7', 64))),
  snapshot = list(snapshot_id = strrep('a', 64)),
  implementation = list(presentation = list(file = 'scripts/health_pipeline/templates/report_helpers.R',
                                            sha256 = strrep('e', 64))),
  reproduction = list(entry_point = 'publish.py batch'))

write_evidence <- function(blocks) {
  dir <- tempfile(); dir.create(dir)
  path <- file.path(dir, 'provenance.json')
  writeLines(toJSON(list(blocks = blocks), auto_unbox = TRUE, null = 'null'), path)
  path
}
render_mon <- function(blocks) monitoring_overview_block(b, write_evidence(blocks), instance_id = 'mon-a')
render_collection <- function(blocks, instance = 'sc-collection')
  series_collection_block(b, write_evidence(blocks), instance_id = instance)

count_of <- function(h, text) lengths(regmatches(h, gregexpr(text, h, fixed = TRUE)))
hrefs <- function(h) {
  found <- regmatches(h, gregexpr('class="panel-link" href="#[A-Za-z0-9_-]+"', h))[[1]]
  if(!length(found)) return(character(0))
  sub('.*href="#([A-Za-z0-9_-]+)"', '\\1', found)
}
panel_ids <- function(h) {
  found <- regmatches(h, gregexpr('<details class="series-panel" id="[A-Za-z0-9_-]+"', h))[[1]]
  sub('.*id="([A-Za-z0-9_-]+)"', '\\1', found)
}

alpha <- member('sc-1-alpha', 'alpha')
beta <- member('sc-2-beta', 'beta')
gamma <- member('sc-3-gamma', 'gamma')
rows3 <- list(row('alpha', value = '16'), row('beta', value = '9'), row('gamma', value = '3'))

# 1. Monitoring plus a matching collection: one correct link per eligible row, and every target
#    is the panel id the collection block actually renders from the same checked record.
coll3 <- collection(list(alpha, beta, gamma))
html <- render_mon(list(monitor(rows3), coll3))
stopifnot(identical(hrefs(html), c('sc-1-alpha', 'sc-2-beta', 'sc-3-gamma')))
stopifnot(identical(hrefs(html), panel_ids(render_collection(list(coll3)))))
stopifnot(count_of(html, 'data-panel-link="1"') == 3L)
stopifnot(count_of(html, '>View annual series</a>') == 3L)
stopifnot(count_of(html, 'if(window.__composedPanelLinkOpen) return;') == 1L)
stopifnot(count_of(html, '<noscript>') == 1L)
stopifnot(grepl('needs to be opened with the panel summary', html, fixed = TRUE))
stopifnot(count_of(html, 'class="panel-link-note"') == 0L)

# 2. Topic identity is exact: similarly named or differently cased topics never borrow a panel.
prefix_only <- render_mon(list(monitor(list(row('alpha', value = '16'))),
                               collection(list(member('sc-7-alpha-b', 'alpha_b'), beta))))
stopifnot(!length(hrefs(prefix_only)))
stopifnot(grepl('No panel: this topic', prefix_only, fixed = TRUE))
cased <- render_mon(list(monitor(list(row('alpha'))),
                         collection(list(member('sc-8-alpha', 'ALPHA')))))
stopifnot(!length(hrefs(cased)))

# 3. Reordering the collection re-links each row to its own member, never to panel order.
reordered <- render_mon(list(monitor(rows3),
                             collection(list(gamma, alpha, beta), default = 'gamma')))
stopifnot(identical(hrefs(reordered), c('sc-1-alpha', 'sc-2-beta', 'sc-3-gamma')))

# 4. An explicit subset links only its members and explains the others.
subset <- render_mon(list(monitor(rows3), collection(list(alpha, gamma))))
stopifnot(identical(hrefs(subset), c('sc-1-alpha', 'sc-3-gamma')))
stopifnot(grepl('Beta<span class="panel-link-note">No panel: this topic</span>', subset, fixed = TRUE))

# 5. A report without a series collection keeps its table: no links, no note, no script, and the
#    same saved values as the linked render.
plain <- render_mon(list(monitor(rows3)))
stopifnot(!length(hrefs(plain)))
stopifnot(count_of(plain, 'data-panel-link') == 0L, count_of(plain, '<script') == 0L)
stopifnot(count_of(plain, 'panel-link-note') == 0L, count_of(plain, '<noscript>') == 0L)
stopifnot(grepl('<td>Alpha</td><td>cases</td><td>2025</td><td>16</td>', plain, fixed = TRUE))
stopifnot(grepl('<td>Alpha<a class="panel-link" href="#sc-1-alpha" data-panel-link="1">View annual series</a></td><td>cases</td><td>2025</td><td>16</td>',
                html, fixed = TRUE))
for(surface in c('<td>cases</td><td>2025</td><td>9</td>', 'Reference +60.0% (2019→2025)',
                 'id="mon-a-endpoints"', 'id="mon-a-bindings"', 'No composite score is derived.')) {
  stopifnot(count_of(plain, surface) == count_of(html, surface))
}

# 6. Incompatible measure, source and reporting window leave the row unlinked with a reason.
stopifnot(grepl('No panel: another measure', render_mon(list(
  monitor(list(row('alpha', measure = 'incidence'))),
  collection(list(alpha)))), fixed = TRUE))
stopifnot(grepl('No panel: another source', render_mon(list(
  monitor(list(row('alpha', dataset = 'ds2'))),
  collection(list(alpha)))), fixed = TRUE))
geography_gap <- render_mon(list(
  monitor(list(row('alpha'))), collection(list(member('sc-1-alpha', 'alpha', geography = 'CH02')))))
stopifnot(grepl('No panel: another source', geography_gap, fixed = TRUE))
window_gap <- render_mon(list(
  monitor(list(row('alpha'))),
  collection(list(alpha), effective = c(2021L, 2022L, 2023L, 2024L))))
stopifnot(grepl('No panel: another period', window_gap, fixed = TRUE))
stopifnot(!length(hrefs(window_gap)))
stopifnot(grepl('No panel: no saved observation', render_mon(list(
  monitor(list(row('alpha', measure = NULL, availability = 'no saved annual observation'))),
  collection(list(alpha)))), fixed = TRUE))

# 7. A failed collection is reported as unchecked, never silently treated as absent.
failed <- render_mon(list(monitor(rows3), collection(list(), status = 'failed', code = 'member',
                                                    detail = "member topic 'alpha' did not resolve")))
stopifnot(!length(hrefs(failed)))
stopifnot(count_of(failed, 'No panel: collection not checked') == 3L)

# 8. Ambiguous and invalid targets are detected rather than guessed.
ambiguous <- render_mon(list(monitor(list(row('alpha'))),
                             collection(list(alpha)),
                             collection(list(alpha), instance = 'sc-other')))
stopifnot(!length(hrefs(ambiguous)))
stopifnot(grepl('No panel: ambiguous target', ambiguous, fixed = TRUE))
invalid <- render_mon(list(monitor(list(row('alpha'))), collection(list(member('SC-BAD', 'alpha')))))
stopifnot(!length(hrefs(invalid)))
stopifnot(grepl('No panel: invalid target', invalid, fixed = TRUE))

# 9. The enhancement is scoped to these links and never closes or reorders panels.
script <- paste(deparse(panel_link_script), collapse = '\n')
stopifnot(grepl('a[data-panel-link]', script, fixed = TRUE))
stopifnot(!grepl("querySelectorAll('a')", script, fixed = TRUE))
stopifnot(grepl('hasAttribute(\'data-panel-link\')', script, fixed = TRUE))
stopifnot(grepl('metaKey', script, fixed = TRUE), grepl('ctrlKey', script, fixed = TRUE))
stopifnot(!grepl('preventDefault(', script, fixed = TRUE))
stopifnot(grepl("tagName!=='DETAILS'", script, fixed = TRUE))
stopifnot(grepl('series-panel', script, fixed = TRUE))
stopifnot(grepl('el.open=true', script, fixed = TRUE))
stopifnot(!grepl('open=false', script, fixed = TRUE))
stopifnot(!grepl('removeAttribute', script, fixed = TRUE))
stopifnot(grepl('summary.focus(', script, fixed = TRUE))
stopifnot(grepl('window.__composedPanelLinkOpen', script, fixed = TRUE))
stopifnot(grepl('hashchange', script, fixed = TRUE))
stopifnot(grepl('fromHash(false)', script, fixed = TRUE))
linked <- render_mon(list(monitor(rows3), collection(list(alpha, beta, gamma))))
stopifnot(count_of(linked, 'class="series-panel" id="sc-2-beta" open') == 0L)
stopifnot(grepl('.composed-report .panel-link{', composition_style(), fixed = TRUE))
stopifnot(grepl('.composed-report .series-panel>summary:focus{', composition_style(), fixed = TRUE))

cat('r-monitoring-links smoke passed\n')
