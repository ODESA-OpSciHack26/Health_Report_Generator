# UI contract test: mock figures, not analytical calculation or real Quarto rendering.
main <- function() {
  args <- commandArgs(trailingOnly=TRUE)
  root <- normalizePath(args[1])
  temp <- tempfile('tabular-presentation-'); dir.create(temp)
  previous <- getwd()
  on.exit({setwd(previous);unlink(temp,recursive=TRUE)},add=TRUE)
  for(name in c('report_helpers.R','audience_reports.R','tabular_charts.R'))
    file.copy(file.path(root,'scripts/health_pipeline/templates',name),file.path(temp,name))
  setwd(temp); source('report_helpers.R'); source('tabular_charts.R')
  chart_image <- function(plot,alt,width=9,height=4) paste0('<img alt="',esc(alt),'" src="data:image/png;base64,TEST">')
  tabular_graphs <- function(analysis,technical=FALSE) {
    titles <- c('Development over the supplied periods','Latest selected period','Within-category change')
    if(technical) titles <- c(titles,'Distribution diagnostic')
    lapply(titles,function(title)list(title=title,note='Saved result',plot=NULL,height=4))
  }
  options <- list(title='Synthetic presentation test',measure_label='Recorded value',unit='cases',
    geography_label='Example region',source_label='Synthetic fixture',reference_period='2019-01-01T00:00:00',
    latest_period='2025-01-01T00:00:00',context_notes=list('Example source note.'))
  stats <- list(category='Example series',n=6,rows=6,missing_values=0,missing_dates=0,periods=6,
    first_period='2019-01-01T00:00:00',last_period='2025-01-01T00:00:00',
    mean=991.166666666667,sd=63.2531949127209,min=900,q1=945,median=1017.5,q3=1036.75,max=1048)
  a <- list(parameters=options,overview=list(rows=6,categories=1,periods=6,missing_values=0),
    periods=list('2019-01-01T00:00:00','2021-01-01T00:00:00','2022-01-01T00:00:00',
      '2023-01-01T00:00:00','2024-01-01T00:00:00','2025-01-01T00:00:00'),
    unrepresented_calendar_periods=list('2020-01-01T00:00:00'),category_statistics=list(stats),
    comparisons=list(list(category='Example series',baseline=900,latest=1048,difference=148,
      percent=16.44444444,note='Comparable single observations')),chart_categories=list('Example series'))
  rows <- '<div class="table-scroll"><table class="report-table"><thead><tr><th>Value</th></tr></thead><tbody><tr><td>900</td></tr></tbody></table></div>'
  views <- list()
  for(id in c('researcher','health_institution','public')) {
    layout <- switch(id,researcher='technical',health_institution='dashboard',public='editorial')
    x <- list(analysis=a,profile=list(layout=layout,display_name=id),audience=id,
      parameters=list(period='year'),rows_html=rows)
    jsonlite::write_json(x,'tabular_context.json',auto_unbox=TRUE,null='null')
    before <- readBin('tabular_context.json','raw',n=file.info('tabular_context.json')$size)
    for(document in c('report','methods')) views[[paste(id,document,sep='_')]] <- tabular_enriched_html(document)
    after <- readBin('tabular_context.json','raw',n=file.info('tabular_context.json')$size)
    stopifnot(identical(before,after))
  }
  output <- list(views=views,formatted=list(mean=tabular_display_number(991.166666666667),
    sd=tabular_display_number(63.2531949127209),large=tabular_display_number(18496.3333333333),
    integer=tabular_display_number(6,0),missing=tabular_display_number(NULL),
    small=tabular_display_number(0.0000123)))
  cat(jsonlite::toJSON(output,auto_unbox=TRUE,null='null'))
}
main()
