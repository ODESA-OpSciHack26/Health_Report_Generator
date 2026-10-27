# Render saved Python results only; do not calculate analytical statistics here.
tabular_records <- function(rows) {
  if(!length(rows)) return(data.frame())
  keys <- unique(unlist(lapply(rows, names)))
  out <- lapply(keys, function(key) vapply(rows, function(row) {
    value <- row[[key]]
    if(is.null(value)) NA_character_ else paste(as.character(unlist(value)),collapse=', ')
  }, character(1)))
  names(out) <- keys
  as.data.frame(out, stringsAsFactors=FALSE, check.names=FALSE)
}
tabular_number <- function(value, digits=1) {
  if(is.null(value) || is.na(value)) return('Not available')
  format(round(as.numeric(value), digits), big.mark=',', scientific=FALSE, trim=TRUE)
}
tabular_plot_theme <- function() report_theme() + ggplot2::theme(
  plot.title=ggplot2::element_text(face='bold', size=16, margin=ggplot2::margin(b=10)),
  strip.text=ggplot2::element_text(face='bold', size=10),
  strip.background=ggplot2::element_rect(fill='#edf4f5', colour=NA),
  axis.text=ggplot2::element_text(size=10),
  plot.caption=ggplot2::element_text(colour='#52656b', hjust=0, size=9))

tabular_graphs <- function(analysis, technical=FALSE) {
  p <- analysis$parameters
  plots <- list()
  d <- tabular_records(analysis$plot_rows)
  if(nrow(d)) {
    d$value <- as.numeric(d$value)
    d$source_row <- as.integer(d$source_row)
    d$date <- as.Date(d$period)
    good <- d[!is.na(d$value) & !is.na(d$date), , drop=FALSE]
    if(nrow(good)) {
      line <- good[tolower(good$line_allowed)=='true', , drop=FALSE]
      # Isolated points are retained; line segments never cross absent periods.
      plot <- ggplot2::ggplot(good, ggplot2::aes(date, value)) +
        ggplot2::geom_line(data=line, ggplot2::aes(group=segment), colour='#247c85', linewidth=.75) +
        ggplot2::geom_point(colour='#b95d35', size=2) +
        ggplot2::facet_wrap(~category, scales='free_y', ncol=3) +
        ggplot2::scale_y_continuous(labels=function(x) format(x,big.mark=',',scientific=FALSE,trim=TRUE)) +
        ggplot2::labs(title='How have the supplied series developed?', x=NULL,
          y=p$measure_label, caption='Separate vertical scales. Gaps are not zero; lines do not bridge absent periods.') +
        tabular_plot_theme()
      plots[[length(plots)+1L]] <- list(plot=plot, title='Development over the supplied periods',
        note='Dots are observed values. Panels use separate vertical scales: compare shape within a panel, not panel heights.',
        height=max(4.2, 2.15*ceiling(length(unique(good$category))/3)))
    } else {
      good <- d[!is.na(d$value),,drop=FALSE]
      if(nrow(good)) {
        plot <- ggplot2::ggplot(good, ggplot2::aes(source_row,value)) +
          ggplot2::geom_point(colour='#247c85',size=2.5) +
          ggplot2::labs(title='Observed values in source order',x='Source data record',y=p$measure_label) + tabular_plot_theme()
        plots[[length(plots)+1L]] <- list(plot=plot,title='Supplied observations',
          note='No observation dates or category totals have been invented.',height=4.4)
      }
    }
  }
  comparison <- tabular_records(analysis$comparisons)
  if(nrow(comparison)) {
    comparison$latest <- as.numeric(comparison$latest)
    comparison$percent <- as.numeric(comparison$percent)
    comparison <- comparison[comparison$category %in% unlist(analysis$chart_categories),,drop=FALSE]
    latest <- comparison[!is.na(comparison$latest),,drop=FALSE]
    if(nrow(latest)) {
      latest$category <- factor(latest$category,levels=latest$category[order(latest$latest)])
      plot <- ggplot2::ggplot(latest,ggplot2::aes(latest,category)) +
        ggplot2::geom_col(fill='#247c85',width=.67) +
        ggplot2::scale_x_continuous(labels=function(x)format(x,big.mark=',',scientific=FALSE,trim=TRUE)) +
        ggplot2::labs(title=paste('Observed values in',substr(p$latest_period,1,4)),
          x=p$measure_label,y=NULL) + tabular_plot_theme()
      plots[[length(plots)+1L]] <- list(plot=plot,title='Latest selected period',
        note='Each bar is a separate observed category value. Categories are not summed into a population burden.',
        height=max(4, .32*nrow(latest)+1.5))
    }
    relative <- comparison[!is.na(comparison$percent),,drop=FALSE]
    if(nrow(relative)) {
      relative$category <- factor(relative$category,levels=relative$category[order(relative$percent)])
      plot <- ggplot2::ggplot(relative,ggplot2::aes(percent,category)) +
        ggplot2::geom_vline(xintercept=0,colour='#9fb0b2',linewidth=.4) +
        ggplot2::geom_segment(ggplot2::aes(x=0,xend=percent,yend=category),colour='#b7ced1',linewidth=2) +
        ggplot2::geom_point(colour='#b95d35',size=3) +
        ggplot2::labs(title=paste(substr(p$latest_period,1,4),'versus',substr(p$reference_period,1,4)),
          x='Change from the selected reference (%)',y=NULL) + tabular_plot_theme()
      plots[[length(plots)+1L]] <- list(plot=plot,title='Within-category change',
        note='One observation at each selected period. Percentage changes are not statistical significance, severity or outbreak alerts.',
        height=max(4,.32*nrow(relative)+1.5))
    }
  }
  histogram <- tabular_records(analysis$histogram)
  if(technical && nrow(histogram)) {
    for(key in c('left','right','count')) histogram[[key]] <- as.numeric(histogram[[key]])
    plot <- ggplot2::ggplot(histogram) +
      ggplot2::geom_rect(ggplot2::aes(xmin=left,xmax=right,ymin=0,ymax=count),fill='#247c85',colour='white') +
      ggplot2::labs(title='Distribution of supplied row values',x=p$measure_label,y='Observations') + tabular_plot_theme()
    plots[[length(plots)+1L]] <- list(plot=plot,title='Distribution diagnostic',
      note='Unweighted row-value distribution across selected categories and periods; not a distribution of individual health outcomes.',height=4.5)
  }
  plots
}

# Formatting and stakeholder structure only: saved analysis remains unrounded.
tabular_display_number <- function(value, digits=1, preserve_whole=FALSE) {
  if(is.null(value) || length(value)!=1) return('Not available')
  number <- suppressWarnings(as.numeric(value))
  if(is.na(number) || !is.finite(number)) return('Not available')
  if(number != 0 && abs(number) < 0.05)
    return(formatC(number, format='g', digits=3, decimal.mark='.'))
  if(preserve_whole && number == trunc(number)) digits <- 0
  number <- round(number, digits)
  if(number == 0) number <- 0
  formatC(number, format='f', digits=digits, big.mark=',', decimal.mark='.')
}

tabular_display_table <- function(rows, columns, period='year') {
  d <- tabular_records(rows)
  if(!nrow(d)) return('<p>No compatible results are available for this selection.</p>')
  d <- d[,intersect(columns,names(d)),drop=FALSE]
  integer_fields <- c('n','rows','missing_values','missing_dates','periods')
  decimal_fields <- c('mean','sd','q1','median','q3')
  observed_fields <- c('min','max','baseline','latest','difference')
  for(key in intersect(integer_fields,names(d)))
    d[[key]] <- vapply(d[[key]],function(v)tabular_display_number(v,0),character(1))
  for(key in intersect(decimal_fields,names(d)))
    d[[key]] <- vapply(d[[key]],function(v)tabular_display_number(v,1),character(1))
  for(key in intersect(observed_fields,names(d)))
    d[[key]] <- vapply(d[[key]],function(v)tabular_display_number(v,1,TRUE),character(1))
  if('percent' %in% names(d)) d$percent <- vapply(d$percent,function(v) {
    number <- suppressWarnings(as.numeric(v))
    if(is.na(number)) 'Not available' else paste0(if(number>0) '+' else '',tabular_display_number(number,1),'%')
  },character(1))
  for(key in intersect(c('first_period','last_period'),names(d)))
    d[[key]] <- vapply(d[[key]],function(v) {
      if(is.na(v)) 'Not available' else substr(v,1,if(identical(period,'year'))4 else 10)
    },character(1))
  labels <- c(category='Series',n='Valid observations',rows='Rows',missing_values='Missing values',
              missing_dates='Missing dates',periods='Selected periods',first_period='First period',
              last_period='Last period',mean='Mean',sd='SD',min='Minimum',q1='25th percentile',
              median='Median',q3='75th percentile',max='Maximum',baseline='Reference value',
              latest='Latest value',difference='Absolute change',percent='Change (%)',note='Interpretation')
  names(d) <- vapply(names(d),function(key)if(key %in% names(labels))labels[[key]] else key,character(1))
  paste0(html_table(d),'<p class="chart-note">Display rounding only: summaries use one decimal place; observation counts use whole numbers. ',
         'Small nonzero values retain significant digits. Full precision is retained in analysis.json.</p>')
}

tabular_enriched_html <- function(document='report') {
  if(!document %in% c('report','methods')) stop('Unsupported tabular view')
  x <- jsonlite::fromJSON('tabular_context.json',simplifyVector=FALSE)
  a <- x$analysis; p <- a$parameters; profile <- x$profile
  technical <- identical(profile$layout,'technical')
  public <- identical(profile$layout,'editorial')
  period <- x$parameters$period
  date_label <- function(value) {
    if(is.null(value)) return('Not selected')
    substr(value,1,if(identical(period,'year'))4 else 10)
  }
  section <- function(id,title,body) paste0('<section class="report-section" id="',esc(id),'"><h2>',esc(title),'</h2>',body,'</section>')
  table <- function(rows,columns) tabular_display_table(rows,columns,period)
  disclosure <- function(label,body) paste0('<details class="report-disclosure"><summary>',esc(label),'</summary>',body,'</details>')
  cards <- function(values,labels) paste0('<div class="report-cards">',paste(vapply(seq_along(values),function(i)
    paste0('<article class="report-card"><span class="card-number">',esc(values[i]),'</span><span class="card-label">',esc(labels[i]),'</span></article>'),character(1)),collapse=''),'</div>')
  link <- function(href,label,current=FALSE) paste0('<a href="',href,'"',if(current)' aria-current="page"' else '', '>',esc(label),'</a>')
  front_label <- if(technical)'Data & charts' else if(public)'Main findings' else 'Monitoring brief'
  navigation <- paste0('<nav class="report-tabs" aria-label="Report views">',
    link('report.html',front_label,document=='report'),
    link('methods.html','Methods & detailed statistics',document=='methods'),
    link('#provenance','Source & downloads'),'</nav>')
  selected_dates <- unlist(a$periods)
  selected_dates <- if(length(selected_dates))vapply(selected_dates,date_label,character(1)) else character()
  coverage <- if(length(selected_dates))paste('Selected periods:',paste(selected_dates,collapse=', ')) else 'Snapshot: no observation dates were supplied.'
  gaps <- unlist(a$unrepresented_calendar_periods)
  gap_note <- if(length(gaps)) paste0('Not represented in this supplied selection: ',
    paste(vapply(gaps,date_label,character(1)),collapse=', '),
    '. No value is assigned to those periods; they are not displayed as zero.') else ''
  quality <- paste0('<p>',tabular_display_number(a$overview$missing_values,0),' missing numeric values in ',
    tabular_display_number(a$overview$rows,0),' supplied observations. ',
    'This describes completeness of the supplied table, not completeness of disease surveillance.</p>')
  limitations <- paste0('<p>These are descriptive observations, not evidence of causes, clinical severity, statistical significance or an outbreak. ',
    'Testing, surveillance and reporting can affect recorded notifications. No cross-disease total is presented as a count of distinct people.</p>')
  stats_note <- paste0('<p class="chart-note">Statistics summarize the available observations in each separate series. ',
    'A mean can be fractional even when individual case counts are whole numbers. SD describes variation between observations, not uncertainty around the mean. ',
    'Quartiles may lie between observed counts. Missing and unselected years are not filled in.</p>')
  comparisons <- Filter(function(row)!is.null(row$difference),a$comparisons)
  if(length(comparisons)) comparisons <- comparisons[order(vapply(comparisons,function(row)abs(row$difference),numeric(1)),decreasing=TRUE)]
  brief <- function(limit=3) {
    if(!length(comparisons)) return('<p>No eligible reference-period comparison was requested or available.</p>')
    paste0('<ul class="priority-list">',paste(vapply(head(comparisons,limit),function(row)paste0('<li><strong>',esc(row$category),'</strong><br>',
      tabular_display_number(row$baseline,1,TRUE),' → ',tabular_display_number(row$latest,1,TRUE),' ',esc(p$unit),
      if(is.null(row$percent))' · percentage unavailable' else paste0(' · ',if(row$percent>0)'+' else '',tabular_display_number(row$percent,1),'%'),
      '</li>'),character(1)),collapse=''),'</ul>',
      '<p class="chart-note">Selected by largest absolute change among comparable series—not clinical importance. ',
      esc(date_label(p$reference_period)),' versus ',esc(date_label(p$latest_period)),'.</p>')
  }
  plots <- if(document=='report')tabular_graphs(a,technical) else list()
  plot_html <- function(kind) {
    titles <- vapply(plots,function(item)item$title,character(1))
    wanted <- switch(kind,trend=c('Development over the supplied periods','Supplied observations'),
                     latest='Latest selected period',change='Within-category change',distribution='Distribution diagnostic')
    index <- which(titles %in% wanted)
    if(!length(index)) return('')
    item <- plots[[index[1]]]
    paste0('<figure class="report-figure">',chart_image(item$plot,item$title,width=9,height=item$height),
      '<figcaption>',esc(item$note),' <a href="methods.html#statistics">Detailed statistics and methods</a>.</figcaption></figure>')
  }
  css <- '<style>
header#title-block-header{display:none}
.tabular-enriched{max-width:1240px;margin:auto;padding:18px;color:#18343c}
.tabular-enriched.audience-editorial{max-width:960px}
.tabular-enriched .report-hero{background:#173f63;color:#fff;padding:28px;border-radius:16px;margin:8px 0 16px}
.tabular-enriched .report-hero h1,.tabular-enriched .report-hero p,.tabular-enriched .report-hero .audience-kicker{color:#fff!important;opacity:1!important}
.tabular-enriched .report-hero h1{font-size:clamp(1.8rem,4vw,2.6rem);line-height:1.15;margin:10px 0 16px}
.tabular-enriched .report-hero p{font-size:1rem;line-height:1.6;margin:8px 0}
.tabular-enriched .audience-kicker{font-size:1rem;font-weight:700;letter-spacing:.04em}
.tabular-enriched.audience-editorial .report-hero{background:#f7f3ec}
.tabular-enriched.audience-editorial .report-hero h1,.tabular-enriched.audience-editorial .report-hero p,.tabular-enriched.audience-editorial .audience-kicker{color:#173f63!important}
.tabular-enriched .report-tabs{position:sticky;top:0;z-index:20;display:flex;gap:10px;flex-wrap:wrap;background:#fff;padding:12px 0;border-bottom:2px solid #d9e5e8;margin:0 0 22px}
.tabular-enriched .report-tabs a,.tabular-enriched .report-cta{display:inline-block;padding:11px 16px;border:2px solid #173f63;border-radius:8px;color:#173f63!important;background:#fff;font-size:1rem;font-weight:700;text-decoration:none;line-height:1.35}
.tabular-enriched .report-tabs a[aria-current=page],.tabular-enriched .report-cta.primary{background:#173f63;color:#fff!important}
.tabular-enriched a:focus-visible,.tabular-enriched summary:focus-visible{outline:3px solid #b95d35;outline-offset:4px}
.tabular-enriched .report-section{background:white;border:1px solid #dce6e8;border-radius:12px;padding:24px;margin:22px 0;scroll-margin-top:110px}
.tabular-enriched .report-section h2{margin:0 0 16px;color:#173f63;font-size:1.5rem}
.tabular-enriched .report-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:20px 0}
.tabular-enriched .report-card{padding:18px;background:#edf4f5;border-radius:10px;border-top:4px solid #247c85}
.tabular-enriched .card-number{display:block;font-size:1.8rem;font-weight:750;color:#173f63;line-height:1.2}
.tabular-enriched .card-label{display:block;color:#28474f;font-size:1rem;margin-top:8px}
.tabular-enriched .report-figure{margin:12px 0}.tabular-enriched .report-figure img{width:100%;height:auto}
.tabular-enriched figcaption,.tabular-enriched .chart-note{color:#354f58;font-size:.98rem;line-height:1.6}
.tabular-enriched .monitor-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px}
.tabular-enriched .monitor-grid .report-section{margin:0;min-width:0}
.tabular-enriched .priority-list{padding-left:22px}.tabular-enriched .priority-list li{padding:10px 0;line-height:1.7}
.tabular-enriched .report-disclosure{padding:16px;border:1px solid #dce6e8;border-radius:9px;margin:16px 0;background:#fafcfc}
.tabular-enriched .report-disclosure summary{cursor:pointer;font-weight:700;color:#173f63;font-size:1.05rem;padding:4px}
.tabular-enriched .coverage-inline{color:#354f58;font-size:1rem;line-height:1.6}
.tabular-enriched .story-lead{font-size:1.2rem;line-height:1.8;max-width:70ch}
.tabular-enriched .report-footer{padding:24px 0;border-top:2px solid #d9e5e8;margin-top:28px}
@media(max-width:800px){.tabular-enriched .monitor-grid{grid-template-columns:1fr}.tabular-enriched .report-hero,.tabular-enriched .report-section{padding:18px}.tabular-enriched .report-tabs a{flex:1 1 180px;text-align:center}}
</style>'
  heading <- if(document=='methods')'Methods & detailed statistics' else if(technical)
    'Data explorer & statistical audit' else if(public)'What changed in the reported numbers?' else 'Monitoring briefing'
  parts <- c(css,paste0('<div class="dashboard tabular-enriched audience-',esc(profile$layout),'" data-tabular-audience="',esc(x$audience),'">'),
    paste0('<header class="report-hero"><div class="audience-kicker">',esc(profile$display_name),'</div><h1>',esc(heading),
      '</h1><p>',esc(p$title),'</p><p>',esc(p$geography_label),' · ',esc(p$measure_label),' · unit: ',esc(p$unit),
      '</p><p>',esc(p$source_label),'</p></header>'),navigation,'<main>')
  if(document=='methods') {
    parts <- c(parts,section('statistics','Descriptive statistics for each series',paste0(
      table(a$category_statistics,c('category','n','missing_values','mean','sd','min','q1','median','q3','max')),stats_note)),
      section('coverage','Coverage of the supplied selection',paste0('<p class="coverage-inline">',esc(coverage),'</p>',
        if(nzchar(gap_note))paste0('<p>',esc(gap_note),'</p>') else '',
        table(a$category_statistics,c('category','rows','periods','first_period','last_period','missing_dates')))),
      section('comparison-detail','Reference-period comparisons',table(a$comparisons,c('category','baseline','latest','difference','percent','note'))),
      section('parameters','Calculation policy',paste0('<p>Statistics give each available row equal weight within its category. Quartiles use inclusive linear interpolation; SD uses n−1. ',
        'No category-period observations or different disease series are pooled. Comparisons require exactly one non-missing observation at each explicitly selected period.</p>',
        '<p>Percentage change = 100 × (latest − reference) ÷ reference. It is unavailable for non-positive baselines. Trend lines stop at absent periods. ',
        'Display rounding does not change the full-precision saved results.</p>')))
    if(length(p$context_notes)) parts <- c(parts,section('source-context','Source interpretation notes',paste0('<ul>',
      paste(vapply(p$context_notes,function(note)paste0('<li>',esc(note),'</li>'),character(1)),collapse=''),'</ul>')))
  } else if(technical) {
    parts <- c(parts,section('overview','Research overview',paste0(
      cards(c(a$overview$rows,a$overview$categories,a$overview$periods,a$overview$missing_values),
            c('Retained observations','Separate series','Selected periods','Missing values')),
      '<p>Inspect the saved values, their coverage and descriptive variation before reusing them in scientific work.</p>',
      '<p><a class="report-cta" href="methods.html#statistics">Open quartiles, ranges and full statistical methods</a></p>')),
      section('research-statistics','Statistical overview',paste0(table(a$category_statistics,c('category','n','mean','median','sd')),stats_note)),
      section('data-quality','Selection and missingness',paste0(quality,'<p class="coverage-inline">',esc(coverage),'</p>',
        if(nzchar(gap_note))disclosure('Coverage note',paste0('<p>',esc(gap_note),'</p>')) else '')),
      section('series-trends','Series development and coverage',plot_html('trend')),
      section('distribution','Row-value distribution diagnostic',plot_html('distribution')),
      disclosure('Inspect latest values and reference-period changes',paste0(plot_html('latest'),plot_html('change'))))
  } else if(!public) {
    parts <- c(parts,section('overview','Monitoring scope',paste0(
      cards(c(date_label(p$reference_period),date_label(p$latest_period),a$overview$categories,a$overview$missing_values),
            c('Reference period','Latest selected period','Series in the file','Missing numeric values')),
      '<p>This is a descriptive review of supplied national observations—not an alert classification or a recommendation to act.</p>')),
      section('monitoring-priorities','Changes to review',brief()),
      '<div class="monitor-grid">',section('latest-values','Latest selected values',plot_html('latest')),
      section('reference-change','Change against the reference',plot_html('change')),'</div>',
      section('comparison-values','Counts and comparison eligibility',table(a$comparisons,c('category','baseline','latest','difference','percent','note'))),
      section('data-quality','Quality and scope before interpretation',paste0(quality,
        disclosure('Which periods are included?',paste0('<p>',esc(coverage),'</p><p>',esc(gap_note),'</p>')))),
      disclosure('Inspect development over time',plot_html('trend')))
  } else {
    lead <- if(length(comparisons)) {
      row <- comparisons[[1]]
      paste0('<p class="story-lead"><strong>',esc(row$category),'</strong> has the largest absolute change among the comparable series: ',
        tabular_display_number(row$baseline,1,TRUE),' → ',tabular_display_number(row$latest,1,TRUE),' ',esc(p$unit),
        '. That does not mean it has the greatest severity or risk.</p>')
    } else '<p class="story-lead">Explore the observations supplied for this report. No reference-period comparison has been inferred.</p>'
    main_chart <- plot_html('change')
    if(!nzchar(main_chart)) main_chart <- plot_html('trend')
    parts <- c(parts,section('overview','The main finding',paste0(lead,
      '<p>Recorded numbers can change because disease occurrence, testing and reporting change. These data alone do not establish the cause.</p>')),
      section('public-main-chart','How the series compare',paste0(main_chart,
        '<p>Read a percentage change alongside the original counts. A large percentage can start from a small number.</p>')),
      section('how-to-read','What these figures can and cannot tell us',paste0(
        '<p>Each disease is shown separately. The report does not add different diseases together as if they were different people. ',
        'Missing values are not counted as zero, and no outbreak or severity threshold is calculated.</p>',
        '<p><a class="report-cta primary" href="methods.html">See the source, detailed statistics and explanations</a></p>')),
      disclosure('See the counts behind the comparison',table(a$comparisons,c('category','baseline','latest','percent','note'))),
      disclosure('Explore the separate series over time',plot_html('trend')),
      section('data-quality','What is missing?',paste0(quality,
        disclosure('About the selected years',paste0('<p>',esc(coverage),'</p><p>',esc(gap_note),'</p>')))))
  }
  if(document=='report') {
    parts <- c(parts,section('observations','Original observations',disclosure('Open the searchable and sortable observation table',
      paste0('<p>Filtering and sorting change only the view, not the saved results. “Missing” marks an absent field.</p>',x$rows_html))))
    if(length(a$category_statistics)>length(a$chart_categories)) parts <- c(parts,
      paste0('<p class="coverage-inline">Charts show the first ',length(a$chart_categories),
        ' categories in source order. All categories remain in the saved results and tables.</p>'))
  }
  parts <- c(parts,section('limitations','Interpretation and uncertainty',limitations),
    section('provenance','Source and downloadable evidence',paste0('<p><a href="provenance.json" download>Render provenance</a> · ',
      '<a href="../analysis.json" download>Full-precision statistics and row references</a> · ',
      '<a href="../bundle/manifest.json" download>Prepared bundle manifest</a> · ',
      '<a href="../bundle/provenance.json" download>Preparation provenance</a></p>',
      '<p>Source labels and units are supplied annotations. The same verified rows and saved results support all three audience views.</p>')),
    '</main><footer class="report-footer">',link('report.html',front_label),
    ' · <a class="report-cta" href="methods.html">Methods & detailed statistics</a></footer></div>')
  paste(parts,collapse='\n')
}
