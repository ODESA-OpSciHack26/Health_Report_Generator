# Shared presentation only. All metrics and their lineage are calculated in Python.
read_bundle <- function(path = '.') {
  manifest <- jsonlite::fromJSON(file.path(path, 'bundle.json'))
  for(n in names(manifest$files)) {
    if(digest::digest(file=file.path(path,n),algo='sha256') != manifest$files[[n]]) stop(paste('Bundle integrity failed:',n))
  }
  cfg <- jsonlite::fromJSON(file.path(path, 'stakeholder.json'))
  read <- function(n) read.csv(file.path(path, n), stringsAsFactors=FALSE, check.names=FALSE)
  list(cfg=cfg, classes=read('pathogen_class.csv'), series=read('series.csv'), metrics=read('metrics.csv'),
       selection=read('selection.csv'), checks=read('checks.csv'), sources=read('sources.csv'),
       lineage=read('lineage.csv'), manifest=jsonlite::fromJSON(file.path(path,'bundle.json')))
}
show_section <- function(b, name) name %in% b$cfg$outputs
headline_table <- function(b) {
  m <- b$metrics
  m[m$metric_type %in% c('period_change','reference_change') & grepl(':main$',m$subject),
    c('metric_id','subject','metric_type','value','unit')]
}
change_table <- function(b) {
  m <- b$metrics
  m[m$metric_type %in% c('period_change','reference_change') & !grepl(':',m$subject),
    c('metric_id','subject','metric_type','value','unit')]
}

esc <- function(x) as.character(htmltools::htmlEscape(as.character(x)))
metric_value <- function(b,id) { x<-b$metrics$value[match(id,b$metrics$metric_id)]; if(length(x)) x else NA_real_ }
format_pct <- function(x,digits=0) ifelse(is.na(x),'Not available',sprintf(paste0('%+.',digits,'f%%'),as.numeric(x)))
fmt_num <- function(x) if(is.null(x) || is.na(x)) '—' else format(as.numeric(x), big.mark = ',', scientific = FALSE, trim = TRUE)
fmt_pct <- function(x, digits = 1L) if(is.null(x) || is.na(x)) '—' else sprintf(paste0('%+.', as.integer(digits), 'f%%'), as.numeric(x))
label_topic <- function(b,x) {
  labels<-setNames(b$classes$label,b$classes$topic)
  ifelse(x %in% names(labels),labels[x],gsub('_',' ',x,fixed=TRUE))
}
report_year <- function(b) b$cfg$years[2]
sensitivity_label <- function(b) paste(label_topic(b,b$cfg$sensitivity_exclude),collapse=', ')
group_topics <- function(b) unique(b$selection$topic[b$selection$status=='included' & tolower(as.character(b$selection$group_eligible))=='true'])
report_theme <- function() ggplot2::theme_minimal(base_size=13,base_family='sans') +
  ggplot2::theme(panel.grid.minor=ggplot2::element_blank(),panel.grid.major.x=ggplot2::element_blank(),
  panel.grid.major.y=ggplot2::element_line(colour='#dfe6e5',linewidth=.3),
  plot.background=ggplot2::element_rect(fill='white',colour=NA),panel.background=ggplot2::element_rect(fill='white',colour=NA),
  text=ggplot2::element_text(colour='#18343c'),axis.text=ggplot2::element_text(colour='#52656b',size=12),
  axis.title=ggplot2::element_text(size=11),legend.position='top',legend.title=ggplot2::element_blank(),legend.text=ggplot2::element_text(size=11),plot.margin=ggplot2::margin(12,15,5,5))
plot_group_totals <- function(b) {
  d<-b$metrics[b$metrics$metric_type=='group_total' & b$metrics$subject %in% c('viral:main','bacterial:main'),]
  d$group<-factor(d$subject,levels=c('viral:main','bacterial:main'),labels=c('Viral','Bacterial'))
  ggplot2::ggplot(d,ggplot2::aes(factor(year),value,fill=group))+
    ggplot2::geom_col(position=ggplot2::position_dodge(width=.74),width=.64)+
    ggplot2::scale_fill_manual(values=c('Viral'='#b95d35','Bacterial'='#247c85'))+
    ggplot2::scale_y_continuous(labels=function(x)paste0(x/1000,'k'),expand=ggplot2::expansion(mult=c(0,.08)))+
    ggplot2::labs(x=NULL,y='Reported cases')+report_theme()
}

plot_groups <- function(b) {
  subjects <- c('viral:main', 'bacterial:main')
  labels <- c('Viral', 'Bacterial')

  if(length(b$cfg$sensitivity_exclude)) {
    subjects <- c(subjects, 'viral:sensitivity')
    labels <- c(labels, paste('Viral without', sensitivity_label(b)))
  }

  colours <- c('#b95d35', '#247c85', '#7e728e')[seq_along(subjects)]
  linetypes <- c('solid', 'solid', 'dashed')[seq_along(subjects)]

  available <- subjects %in% b$metrics$subject[
    b$metrics$metric_type == 'group_index'
  ]
  subjects <- subjects[available]
  labels <- labels[available]
  colours <- colours[available]
  linetypes <- linetypes[available]

  d <- b$metrics[
    b$metrics$metric_type == 'group_index' &
      b$metrics$subject %in% subjects,
  ]
  d$group <- factor(d$subject, levels=subjects, labels=labels)

  # Display existing indices as percentage changes.
  d$change <- d$value - 100

  ggplot2::ggplot(
    d,
    ggplot2::aes(year, change, colour=group, linetype=group)
  ) +
    ggplot2::geom_hline(
      yintercept=0, colour='#9fb0b2', linewidth=.4
    ) +
    ggplot2::geom_line(linewidth=1) +
    ggplot2::geom_point(size=2) +
    ggplot2::scale_colour_manual(values=setNames(colours, labels)) +
    ggplot2::scale_linetype_manual(values=setNames(linetypes, labels)) +
    ggplot2::scale_x_continuous(
      breaks=sort(unique(c(
        b$cfg$index_base_year,
        b$cfg$years[1],
        b$cfg$years[2] - 2,
        b$cfg$years[2]
      )))
    ) +
    ggplot2::scale_y_continuous(
      labels=function(x) paste0(ifelse(x > 0, '+', ''), x, '%')
    ) +
    ggplot2::labs(
      x=NULL,
      y=paste('Change from', b$cfg$index_base_year)
    ) +
    report_theme() +
    ggplot2::guides(
      colour=ggplot2::guide_legend(nrow=2),
      linetype=ggplot2::guide_legend(nrow=2)
    )
}

friendly_changes <- function(b) {
  d<-b$metrics[b$metrics$metric_type=='reference_change' & b$metrics$subject %in% group_topics(b),]
  d<-d[order(d$value,decreasing=TRUE),];topics<-d$subject
  count_at<-function(y) b$series$value[match(paste(topics,y),paste(b$series$topic,b$series$year))]
  data.frame(Disease=label_topic(b,topics),Baseline=count_at(b$cfg$reference_year),Latest=count_at(report_year(b)),Change=d$value,check.names=FALSE)
}
plot_changes <- function(b) {
  d<-friendly_changes(b);d$Disease<-factor(d$Disease,levels=rev(d$Disease))
  ggplot2::ggplot(d,ggplot2::aes(Change,Disease))+
    ggplot2::geom_vline(xintercept=0,colour='#9fb0b2',linewidth=.4)+
    ggplot2::geom_segment(ggplot2::aes(x=0,xend=Change,yend=Disease),colour='#c0d0d1',linewidth=2)+ggplot2::geom_point(colour='#247c85',size=3)+
    ggplot2::scale_x_continuous(labels=function(x)paste0(ifelse(x>0,'+',''),x,'%'))+
    ggplot2::labs(x=paste('Change in reported cases,',report_year(b),'versus',b$cfg$reference_year),y=NULL)+
    report_theme()+ggplot2::theme(panel.grid.major.y=ggplot2::element_blank(),panel.grid.major.x=ggplot2::element_line(colour='#dfe6e5',linewidth=.3))
}
plot_disease <- function(b,topic,compact=FALSE) {
  s<-b$series[b$series$topic==topic,]
  ggplot2::ggplot(s,ggplot2::aes(year,incidence)) + ggplot2::geom_line(colour='#247c85',linewidth=1)+ggplot2::geom_point(colour='#247c85',size=2)+
    ggplot2::labs(title=s$label[1],x='Year',y='Per 100,000 people')+report_theme()
}
plot_small_multiples <- function(b) {
  ggplot2::ggplot(b$series,ggplot2::aes(year,incidence))+ggplot2::geom_line(colour='#247c85')+
    ggplot2::geom_point(colour='#247c85',size=1)+ggplot2::facet_wrap(~label,scales='free_y',ncol=3)+
    ggplot2::labs(x='Year',y='Per 100,000 people')+report_theme()
}
chart_image <- function(plot,alt,width=6,height=3.8) {
  p<-tempfile(fileext='.png');on.exit(unlink(p));ggplot2::ggsave(p,plot,width=width,height=height,dpi=180,bg='white')
  paste0('<img alt="',esc(alt),'" src="',knitr::image_uri(p),'">')
}
report_navigation <- function(b,methods=FALSE,format='html',pdf=TRUE) {
  paste0('<header class="dash-nav"><span class="dash-brand">SURVEILLANCE / ',if(b$cfg$geography=='CHFL')'SWITZERLAND + LIECHTENSTEIN' else 'SWITZERLAND','</span><nav aria-label="Reports">',
         if(!methods)'<span class="nav-active">Findings</span>' else '<a href="report.html">Findings</a>',
         if(methods)'<span class="nav-active">Methods &amp; sources</span>' else '<a href="methods.html">Methods &amp; sources</a>',
         if(pdf) paste0('<a href="',if(methods)'methods.pdf' else 'report.pdf','">PDF version</a>') else '',
         '</nav></header>')
}
report_metadata <- function(b) {
  pr <- read_provenance()
  scope <- if(!is.null(pr$composition)) pr$composition$display_scope else NULL
  label <- if(!is.null(scope))
    paste0(length(scope$displayed_topics), ' topics displayed in this report; ',
           length(group_topics(b)), ' contributing to underlying group sums')
    else paste0(length(group_topics(b)), ' diseases in the group comparison')
  paste0('<div class="report-meta"><span>', esc(label),
         '</span><span>National case notifications</span><span class="snapshot">Snapshot ',
         substr(b$manifest$snapshot_id,1,16),'</span></div>')
}
summary_cards <- function(b) {
  ids<-c('viral:main:reference_change','bacterial:main:reference_change');labels<-c('Viral notifications','Bacterial notifications')
  if(length(b$cfg$sensitivity_exclude)){ids<-c(ids,'viral:sensitivity:reference_change');labels<-c(labels,paste('Viral, without',sensitivity_label(b)))}
  available <- ids %in% b$metrics$metric_id
  ids <- ids[available]
  labels <- labels[available]
  paste0('<div class="metric-grid">',paste(vapply(seq_along(ids),function(i)paste0('<article class="metric-card"><div class="metric-label">',esc(labels[i]),'</div><div class="metric-value">',format_pct(metric_value(b,ids[i])),'</div><p>',report_year(b),' compared with ',b$cfg$reference_year,'</p></article>'),character(1)),collapse=''),'</div>')
}
friendly_table <- function(b) {
  d<-friendly_changes(b);d$Baseline<-format(d$Baseline,big.mark=',',scientific=FALSE,trim=TRUE);d$Latest<-format(d$Latest,big.mark=',',scientific=FALSE,trim=TRUE);d$Change<-format_pct(d$Change,1)
  names(d)<-c('Disease',paste('Cases in',b$cfg$reference_year),paste('Cases in',report_year(b)),'Change')
  d
}
html_table <- function(d) paste0('<div class="table-scroll">',as.character(knitr::kable(d,format='html',escape=TRUE,row.names=FALSE,table.attr='class="report-table" data-searchable="true"')),'</div>')
reference_block <- function(b,evidence_file='',variant='legacy',instance_id=NULL) {
  composed <- identical(variant,'composed')
  if(composed && (is.null(instance_id) || !nzchar(instance_id)))
    stop('A composed reference-comparison block needs an instance id')
  inspect_id <- if(composed) paste0(instance_id,'-inspect') else 'block-reference-comparison-inspector'
  panel <- function(inner) if(composed) inner else paste0('<section class="chart-panel full" id="block-reference-comparison">',inner,'</section>')
  if(!nzchar(evidence_file)) return('')
  unavailable <- function(reason) panel(paste0('<h2>Reference comparison unavailable</h2>',
    '<p class="caption">The retained block record could not be used, so no values are shown.</p>',
    '<div class="audit-row"><span>Reason</span><strong>',esc(reason),'</strong></div>'))
  if(!knitr::is_html_output()) return('')
  if(!file.exists(evidence_file)) return(unavailable(paste('evidence file is missing:',evidence_file)))
  record <- tryCatch(jsonlite::fromJSON(evidence_file,simplifyVector=FALSE),error=function(e) NULL)
  if(is.null(record)) return(unavailable('evidence file is not valid JSON'))
  if(is.null(record$blocks) || !length(record$blocks)) return(unavailable('evidence file carries no blocks'))
  if(!is.null(instance_id) && nzchar(instance_id)) {
    # Select by instance id AND expected block type. No first-record fallback.
    matches <- Filter(function(x) identical(x$instance_id,instance_id) &&
                        identical(x$component$type,'reference-comparison'),record$blocks)
    if(!length(matches)) return(unavailable(paste('no checked reference-comparison record for block instance',instance_id)))
    block <- matches[[1]]
  } else {
    typed <- Filter(function(x) identical(x$component$type,'reference-comparison'),record$blocks)
    if(!length(typed)) return(unavailable('evidence file carries no reference-comparison block'))
    block <- typed[[1]]
  }
  row <- function(k,v) paste0('<div class="audit-row"><span>',esc(k),'</span><strong>',esc(v),'</strong></div>')
code_row <- function(k,v) paste0('<div class="audit-row"><span>',esc(k),'</span><strong><code>',
                                 gsub('--','&#45;&#45;',esc(v),fixed=TRUE),'</code></strong></div>')
  if(!identical(block$status,'verified')) {
    return(panel(paste0('<h2>Reference comparison unavailable</h2>',
      '<p class="caption">The saved block did not pass its contract checks, so no values are shown.</p>',
      row('Reason',paste0(block$code,': ',block$detail)))))
  }
  fmt <- function(x) format(as.numeric(x),big.mark=',',scientific=FALSE,trim=TRUE)
  pct_digits <- if(!is.null(block$effective$presentation$digits)) as.integer(block$effective$presentation$digits) else 1L
  pct <- if(identical(block$result$availability,'available')) sprintf(paste0('%+.',pct_digits,'f%%'),as.numeric(block$result$value)) else 'Not available'
  trace <- paste(vapply(block$trace,function(t) paste0(t$field,' = ',t$value,' (',t$source,')'),character(1)),collapse='; ')
  if(composed) {
    editorial <- identical(presentation_profile(b)$layout, 'editorial')
    plain <- composition_copy_for(b)$reference(b, block, pct, fmt)
    return(paste0('<div class="finding', if(editorial) ' finding--editorial' else '', '">',
      if(editorial) paste0('<div class="audience-explanation"><p>', plain, '</p></div>') else '',
      '<p class="finding-value">',esc(pct),'</p>',
      '<p class="finding-meta">',esc(label_topic(b,block$subject)),' · reported cases in ',esc(block$latest_year),
      ' compared with ',esc(block$reference_year),
      if(editorial) '' else paste0(' · measure ', esc(block$measure)), '</p>',
      '<div class="finding-counts"><div><span>',esc(block$reference_year),'</span><strong>',fmt(block$reference_count$value),'</strong></div>',
      '<div><span>',esc(block$latest_year),'</span><strong>',fmt(block$latest_count$value),'</strong></div></div>',
      if(!editorial) paste0('<div class="audience-explanation"><p>', plain, '</p></div>') else '',
      '<p class="finding-caution">Notification changes reflect surveillance and testing as well as disease occurrence; they do not establish disease severity or statistical significance.</p>',
      '<details class="block-inspect" id="',esc(inspect_id),'"><summary>Inspect this block</summary>',
      row('Result metric',block$result$metric_id),
      row('Bound counts',paste(block$reference_count$metric_id,'and',block$latest_count$metric_id)),
      row('Formula',block$result$formula), row('Availability',block$result$availability),
      row('Reported measure',block$measure), row('Snapshot',block$snapshot$snapshot_id),
      row('Snapshot path',block$snapshot$snapshot_path), row('Reference year',block$reference_year),
      row('Latest year',block$latest_year), row('Effective settings',trace),
      row('Analysis code',paste0(block$implementation$analysis$file,' · ',substr(block$implementation$analysis$sha256,1,16))),
      row('Render code',paste0(block$implementation$presentation$file,' · ',substr(block$implementation$presentation$sha256,1,16))),
      row('Analytical identity',block$identities$analytical), row('Result identity',block$identities$result),
      row('Instance identity',block$identities$instance), code_row('Entry point',block$reproduction$entry_point),
      row('Retained source record',paste0(block$lineage$source_file,' record ',block$lineage$source_row)),
      '<p class="caption">Identities show that these records agree with each other; they do not prove the numbers are correct. Opening this panel performs no calculation.</p>',
      '</details></div>'))
  }
  paste0('<section class="chart-panel full" id="block-reference-comparison">',
    '<h2>',esc(label_topic(b,block$subject)),': ',esc(pct),' in ',esc(block$latest_year),' compared with ',esc(block$reference_year),'</h2>',
    '<p class="caption">Saved comparison read from the analysis bundle. This report does not recalculate it.</p>',
    row(paste('Reported cases in',block$reference_year),fmt(block$reference_count$value)),
    row(paste('Reported cases in',block$latest_year),fmt(block$latest_count$value)),
    row('Percentage change',paste0(pct,' (percent)')),
    row('Reported measure',block$measure),
    '<details class="block-inspector" id="block-reference-comparison-inspector"><summary>Evidence and identities</summary>',
    '<div class="audit-panel" id="block-data"><h3>Data and scope</h3>',
    row('Snapshot',block$snapshot$snapshot_id),
    row('Snapshot path',block$snapshot$snapshot_path),
    row('Result metric',block$result$metric_id),
    row('Bound counts',paste(block$reference_count$metric_id,'and',block$latest_count$metric_id)),
    row('Formula',block$result$formula),
    row('Availability',block$result$availability),
    '</div><div class="audit-panel" id="block-method"><h3>Method and parameters</h3>',
    row('Reference year',block$reference_year),
    row('Latest year',block$latest_year),
    row('Effective settings',trace),
    '</div><div class="audit-panel" id="block-implementation"><h3>Implementation identities</h3>',
    row('Analysis code',paste0(block$implementation$analysis$file,' · ',substr(block$implementation$analysis$sha256,1,16))),
    row('Render code',paste0(block$implementation$presentation$file,' · ',substr(block$implementation$presentation$sha256,1,16))),
    row('Analytical identity',block$identities$analytical),
    row('Result identity',block$identities$result),
    row('Instance identity',block$identities$instance),
    '</div><div class="audit-panel" id="block-reproduction"><h3>Reproduction</h3>',
    code_row('Entry point',block$reproduction$entry_point),
    row('Retained source record',paste0(block$lineage$source_file,' record ',block$lineage$source_row)),
    '<p class="caption">Identities show that these records agree with each other; they do not prove the numbers are correct. Opening this panel performs no calculation.</p>',
    '</div></details></section>')
}
findings_html <- function(b,navigation=TRUE,evidence_file='') {
  panel<-function(title,caption,plot,note,width=6,height=3.8) paste0('<section class="chart-panel"><h2>',esc(title),'</h2><p class="caption">',esc(caption),'</p>',chart_image(plot,title,width,height),'<div class="chart-note">',note,'</div></section>')
  year<-report_year(b);ref<-b$cfg$reference_year
  excluded<-paste(label_topic(b,b$cfg$exclude_from_group_totals),collapse=', ')
  rising <- all(c(metric_value(b,'viral:main:reference_change'),metric_value(b,'bacterial:main:reference_change'))>0,na.rm=FALSE)
  title <- if(isTRUE(rising)) paste0('More notifications in ',year,'.<br>Different patterns behind the rise.') else paste0('Disease notifications:<br>the ',year,' picture.')
  concentrated <- length(b$cfg$sensitivity_exclude)>0 && isTRUE(metric_value(b,'viral:main:reference_change')>0 && metric_value(b,'viral:sensitivity:reference_change')<=0)
  has_sensitivity <- 'viral:sensitivity:reference_change' %in% b$metrics$metric_id
  change_title <- if(concentrated) {
    paste('The viral rise is concentrated in', sensitivity_label(b))
  } else if(has_sensitivity && length(b$cfg$sensitivity_exclude)) {
    paste('How does excluding', sensitivity_label(b), 'change the picture?')
  } else {
    'How have the selected disease groups changed?'
  }
  parts<-c(presentation_open(b),if(navigation)report_navigation(b),paste0('<div class="eyebrow">Annual disease briefing · ',paste(b$cfg$years,collapse='–'),' · comparison with ',ref,'</div><h1>',title,'</h1>'),report_metadata(b))
  parts <- c(parts, selection_intro(b))
  if(show_section(b,'headline'))parts<-c(parts,summary_cards(b))
  parts<-c(parts,'<div class="chart-grid">')
  if(show_section(b,'group_totals'))parts<-c(parts,panel('How many cases were reported?','Annual totals for the selected diseases',plot_group_totals(b),paste0('Source: FOPH dashboard exports · sum of selected national case notifications. ',esc(excluded),' excluded. Only the reference and configured reporting years are shown. <a href="methods.html#selection">How calculated</a>')))
  if(show_section(b,'group_index'))parts<-c(parts,panel(change_title,paste0('Change from ',b$cfg$index_base_year,'; 0% means the same number of cases'),plot_groups(b),'Source: the same selected case series · percentage change from each group’s baseline total. This compares trends, not absolute disease burden. <a href="methods.html#calculations">How calculated</a>'))
  parts<-c(parts,'</div>')
  if(show_section(b,'small_multiples'))parts<-c(parts,paste0('<section class="chart-panel full"><h2>Which diseases changed most?</h2><p class="caption">Reported cases in ',year,' compared with ',ref,'</p>',chart_image(plot_changes(b),'Disease-specific changes in reported cases',9,4.7),'<div class="chart-note">Source: selected national FOPH case series. Right of zero = more notifications; left = fewer. Percentage changes do not measure disease severity or statistical significance.</div>'))
  if(show_section(b,'change_table'))parts<-c(parts,paste0('<details><summary>View the figures behind the comparison</summary>',html_table(friendly_table(b)),'<div class="table-note">Source: selected FOPH annual national case counts. Change = (latest count − baseline count) ÷ baseline count × 100. Values are rounded for display. <a href="methods.html#calculations">View calculation details</a></div></details>'))
  parts<-c(parts,reference_block(b,evidence_file))
  if(show_section(b,'small_multiples'))parts<-c(parts,'</section>')
  parts <- c(parts, technical_findings(b))
  parts <- c(parts, audience_extras(b))
  parts<-c(parts,'<footer class="dash-footer"><span>Notifications reflect surveillance and testing as well as disease occurrence.</span><a href="methods.html">Read the methods &amp; source report →</a></footer></div>')
  paste(parts,collapse='\n')
}
# Source state is recorded once, in provenance (publish.py), and only read here. A record that
# predates the field is reported as not recorded; this helper never re-derives cleanliness from a
# Git SHA. Availability is a separate statement and is always reported beside the state.
source_state_note <- function(pr) {
  s <- if(!is.null(pr$code)) pr$code$source_state else NULL
  list(
    state = if(!is.null(s$state)) as.character(s$state) else 'unknown',
    label = if(!is.null(s$label)) as.character(s$label) else 'source state not recorded',
    detail = if(!is.null(s$detail)) as.character(s$detail) else
      'Source state was not recorded in this provenance record, so source identity is unverified.',
    availability = if(!is.null(s$availability)) as.character(s$availability) else
      'Neither the source checkout nor the container image is part of this package; both must be supplied separately.')
}

methods_html <- function(b,navigation=TRUE,prefix='data/',pdf=TRUE) {
    y <- report_year(b)
  ref <- b$cfg$reference_year
  pr_m <- read_provenance()
  note_m <- source_state_note(pr_m)
  comp_m <- if(!is.null(pr_m$composition)) pr_m$composition else NULL
  recs_m <- if(!is.null(pr_m$blocks)) pr_m$blocks else list()
  ok_m <- function(x, type) identical(x$status,'verified') && identical(x$component$type, type)
  scope_m <- if(!is.null(comp_m)) comp_m$display_scope else NULL
  standalone_m <- if(!is.null(scope_m)) unlist(scope_m$standalone_topics) else character(0)
  composed_m <- !is.null(comp_m)
  requested_ref_ids <- if(composed_m && length(comp_m$effective_recipe))
    vapply(Filter(function(e) identical(as.character(e$block), 'reference-comparison'),
                  comp_m$effective_recipe), function(e) as.character(e$instance_id), character(1))
    else character(0)
  refs_m <- Filter(function(x) identical(x$component$type, 'reference-comparison'), recs_m)
  resolved_ref <- NULL
  if(length(requested_ref_ids)) {
    matched <- Filter(function(x) identical(x$instance_id, requested_ref_ids[[1]]) &&
                        identical(x$status, 'verified'), refs_m)
    if(length(matched) == 1L) resolved_ref <- matched[[1]]
  }
  requested_ref_unavailable <- length(requested_ref_ids) > 0L && is.null(resolved_ref)
  series_m <- Filter(function(x) ok_m(x,'series-trend'), recs_m)
  monitoring_m <- Filter(function(x) ok_m(x,'monitoring-overview'), recs_m)
  resolved_series <- if(length(series_m)) series_m[[1]] else NULL
  resolved_monitoring <- if(length(monitoring_m)) monitoring_m[[1]] else NULL
  available <- c('viral:main', 'bacterial:main')
  available <- available[
    paste0(available, ':reference_change') %in% b$metrics$metric_id
  ]
  if(!length(available)) stop('No main-group metrics available')
  trace_subject <- available[1]
  trace_label <- if(trace_subject == 'viral:main') {
    'Viral notifications'
  } else {
    'Bacterial notifications'
  }
  a <- metric_value(b, paste0(trace_subject, ':', ref, ':total'))
  z <- metric_value(b, paste0(trace_subject, ':', y, ':total'))
  fmt<-function(x)format(x,big.mark=',',scientific=FALSE,trim=TRUE)
  row<-function(k,v)paste0('<div class="audit-row"><span>',esc(k),'</span><strong>',esc(v),'</strong></div>')
  selected<-b$selection[,c('topic','status','reason','group_eligible')];selected$topic<-label_topic(b,selected$topic);selected$group_eligible<-ifelse(tolower(as.character(selected$group_eligible))=='true','Yes','No');names(selected)<-c('Disease or signal','Selection','Reason','In main group')
  sources<-b$sources[b$sources$status=='ok',c('topic','publishing_date','used')];sources$topic<-label_topic(b,sources$topic);sources$used<-ifelse(tolower(as.character(sources$used))=='true','Yes','No');names(sources)<-c('Disease or signal','Published','Used in analysis')
  parts<-c(presentation_open(b),if(navigation)report_navigation(b,TRUE,pdf=pdf),'<div class="eyebrow">Companion report / Methods &amp; sources</div><h1>Where the findings come from.</h1>',report_metadata(b),'<div class="audit-grid"><section class="audit-panel" id="selection"><h2>What is included?</h2>',row('Geography',if(b$cfg$geography=='CHFL')'Switzerland + Liechtenstein' else 'Switzerland'),row('Reporting years',paste(b$cfg$years,collapse='–')),row('Reference year',ref))
  for(cls in c('viral', 'bacterial')) {
    topics <- unique(b$series$topic[
      b$series$pathogen_class == cls &
      b$series$topic %in% group_topics(b)
    ])

    if(!length(topics)) {
      parts <- c(parts, row(
        paste(tools::toTitleCase(cls), 'group'),
        'Not selected for group analysis'
      ))
      next
    }

    parts <- c(
      parts,
      row(
        paste(tools::toTitleCase(cls), 'group'),
        paste(length(topics), 'diseases')
      ),
      paste0(
        '<p class="caption">',
        esc(paste(label_topic(b, topics), collapse=', ')),
        '.</p>'
      )
    )
  }
  trace_body <- if(!is.null(resolved_ref)) {
    rr <- resolved_ref
    paste0('<h3>', esc(label_topic(b, rr$subject)), ': ', fmt_pct(rr$result$value, rr$effective$presentation$digits),
      ' in ', esc(rr$latest_year), ' versus ', esc(rr$reference_year), '</h3>',
      row(paste('Saved cases in', rr$latest_year), fmt_num(rr$latest_count$value)),
      row(paste('Saved cases in', rr$reference_year), fmt_num(rr$reference_count$value)),
      row('Saved result metric', rr$result$metric_id),
      row('Bound count metrics', paste(rr$reference_count$metric_id, 'and', rr$latest_count$metric_id)),
      row('Formula recorded with the saved result', paste0('(', fmt_num(rr$latest_count$value), ' − ',
        fmt_num(rr$reference_count$value), ') ÷ ', fmt_num(rr$reference_count$value), ' × 100')),
      '<p class="caption">The saved percentage was produced by the analysis workflow with this formula; ',
      'this report displays the saved value and does not recalculate it. The lineage export links the ',
      'bound counts to each disease and to its original source records.</p>')
  } else if(requested_ref_unavailable) {
    paste0('<h3>Requested reference comparison unavailable</h3>',
      '<p class="caption">This recipe requests reference-comparison instance ',
      esc(requested_ref_ids[[1]]), ', but the published evidence contains no verified record ',
      'with that instance id and type. No substitute finding is shown in methods.</p>')
  } else if(!is.null(resolved_series)) {
    sr <- resolved_series
    paste0('<h3>', esc(label_topic(b, sr$selection$topic)), ': saved annual series</h3>',
      row('Saved observation years', paste(sr$periods$effective, collapse = ', ')),
      row('Requested years', paste(sr$periods$requested, collapse = '–')),
      row('Missing years', if(length(sr$missing_years)) paste(sr$missing_years, collapse = ', ') else 'none'),
      row('Series artifact', paste0(sr$artifact$file, ' · ', substr(sr$artifact$digest, 1, 16))),
      '<p class="caption">Each displayed point is a saved annual observation bound through its count metric. ',
      'Missing years are gaps, not zeros; no trend, interpolation or smoothing is calculated at render time.</p>',
      if(composed_m && !length(requested_ref_ids))
        '<p class="caption">This composition selects no standalone reference-comparison block.</p>' else '')
  } else if(composed_m) {
    paste0('<h3>No standalone reference selected</h3>',
      '<p class="caption">This composition selects no standalone reference-comparison block. ',
      'The displayed-block accounts above describe what the report actually shows.</p>')
  } else {
    paste0('<h3>', esc(trace_label), ': ', format_pct(metric_value(b, paste0(trace_subject, ':reference_change')), 1),
      ' versus ', ref, '</h3>',
      row(paste('Selected cases in', y), fmt(z)),
      row(paste('Selected cases in', ref), fmt(a)),
      row('Calculation', paste0('(', fmt(z), ' − ', fmt(a), ') ÷ ', fmt(a), ' × 100')),
      '<p class="caption">This legacy methods path traces the saved group result because no composed ',
      'finding record was supplied. The saved result is displayed, not recalculated.</p>')
  }
  denominator_note <- if('incidence' %in% b$metrics$metric_type)
    paste0(' The lineage also retains population denominators for the saved incidence metrics; ',
           'those rates are not displayed in this report, and the displayed count changes are not population-adjusted.')
    else ''
  parts<-c(parts,paste0('<div class="chart-note">Excluded from group sums: ',
    esc(paste(label_topic(b,b$cfg$exclude_from_group_totals),collapse=', ')),
    '. Sentinel estimates are not pooled with mandatory case notifications.</div></section>',
    '<section class="audit-panel" id="calculations"><h2>Trace a finding, not a code</h2>', trace_body,
    denominator_note, '</section>',
    '<section class="audit-panel full" id="comparability"><h2>Cross-year comparability</h2>',
    '<p>These are comparisons of saved notification counts under the recorded selection rules. ',
    'Cross-year surveillance-method comparability (case definitions, reporting obligations, testing and ',
    'diagnostic practice, date assignment, source methodology) has not been systematically evaluated. ',
    'Matching source identifiers, units or file digests do not establish stable surveillance methods over time.</p></section>',
    '<section class="audit-panel full" id="classification"><h2>Classification, eligibility and completeness</h2>',
    '<p>Topics enter the analysis only when a dataset is assigned to the report’s supported analytical ',
    'classification and is compatible in source, measure and geography. “Unclassified” means not assigned to ',
    'that classification; it is not evidence that a disease is absent or that no source data exist.</p>',
    '<p>Eligibility requires the reference year and every reporting-window year. An annual value is preferred; ',
    'a monthly series is accepted only with 12 distinct months in the year. A missing required period excludes ',
    'the dataset with a recorded reason. Competing sources are resolved by the configured source priority. ',
    '“Complete compatible series” describes period and aggregation completeness, not complete ascertainment ',
    'of infection.</p>',
    '<p class="table-note">Analytical inclusion is separate from group-sum membership: a topic can be included ',
    'and still be excluded from group totals. The workflow configuration digest is recorded in the provenance ',
    'sidecar and the retained selection records are downloadable below.</p></section>',
    if(!is.null(resolved_monitoring)) paste0('<section class="audit-panel full" id="baseline"><h2>Baseline interpretation</h2>',
      '<p>The monitoring table shows only comparisons recorded in the saved bundle. For this scope the reference ',
      'comparison runs from ', esc(if(length(resolved_monitoring$rows) && length(resolved_monitoring$rows[[1]]$comparisons)) paste0(resolved_monitoring$rows[[1]]$comparisons[[1]]$from_year, ' to ', resolved_monitoring$rows[[1]]$comparisons[[1]]$to_year) else 'the reference year to the latest year'),
      '; period comparisons cover the reporting window. Percentage size and sometimes direction depend on the ',
      'chosen baseline, and an endpoint percentage does not summarise the intervening annual trajectory.</p></section>') else '',
    '<section class="audit-panel full" id="reproduction"><h2>Reproduction routes</h2>',
    '<p>Distinguish three routes: (1) rendering this report from the saved bundle with the composition recipe; ',
    '(2) the original analysis that produced the saved bundle; (3) the published integrity/inspection example, ',
    'which verifies saved files and does not rerun analysis. The rendering entry point recorded for each block ',
    'is shown in its inspector; the effective recipe digest appears under “Report settings and source files”.</p>',
    '<p class="table-note">', esc(note_m$detail), ' ', esc(note_m$availability), '</p></section>'))
  if(show_section(b,'excluded'))parts<-c(parts,paste0('<section class="audit-panel full"><h2>Dataset selection</h2>',html_table(selected),'<div class="table-note">Source: the saved selection table. “Included” means eligible for disease-level analysis; “In main group” additionally applies the configured source and disease exclusions.</div></section>'))
  if(show_section(b,'quality'))parts<-c(parts,quality_methods_html(b))
  if(show_section(b,'sources'))parts<-c(parts,paste0('<section class="audit-panel full"><h2>Sources and audit files</h2>',html_table(sources),'<div class="table-note">Source: the dataset registry and original export descriptions. Dates are publisher release dates. Full paths, data and metadata fingerprints are retained in the downloadable source registry.</div><div class="download-links">',paste(vapply(c('sources.csv','selection.csv','lineage.csv','metrics.csv','checks.csv','snapshot.json'),function(n)paste0('<a download href="',prefix,n,'">',esc(n),'</a>'),character(1)),collapse=''),'</div><details><summary>Technical identifiers and exact snapshot</summary><p class="snapshot">',esc(b$manifest$snapshot_id),'</p><p>Full metric identifiers are in metrics.csv. The findings report uses human-readable names instead of printed M-codes. CSV record numbers count the header as record 1; multiline CSV fields may span several text lines.</p></details></section>'))
  # Displayed-block accounts come from verified records only; absent blocks get no narrative.
  block_row <- function(title, description, anchor, limitation) paste0(
    '<h3>', esc(title), '</h3><p>', description, '</p>',
    '<p><a href="report.html#', esc(anchor), '">Open the corresponding report block</a></p>',
    '<p class="table-note">Limitation: ', esc(limitation), '</p>')
  block_items <- character(0)
  for (rec in recs_m) {
    if(!identical(rec$status,'verified')) next
    type <- rec$component$type
    if(identical(type,'reference-comparison')) block_items <- c(block_items, block_row(
      paste0('Reference comparison: ', label_topic(b, rec$subject)),
      paste0('Displays the saved percentage result ', rec$result$metric_id, ' bound to saved counts ',
             rec$reference_count$metric_id, ' (', fmt_num(rec$reference_count$value), ') and ',
             rec$latest_count$metric_id, ' (', fmt_num(rec$latest_count$value), '). ',
             'The saved result is displayed, not recalculated.'), rec$instance_id,
      'Descriptive percent change only; no causal or statistical inference.'))
    if(identical(type,'series-trend')) block_items <- c(block_items, block_row(
      paste0('Annual series: ', label_topic(b, rec$selection$topic)),
      paste0('Displays saved annual rows for the requested window ', paste(rec$periods$requested, collapse='–'),
             ', each bound through its saved count metric. Missing years are gaps, never zeros, and no ',
             'interpolation is performed across them.'), rec$instance_id,
      'Display of saved observations only; no trend model or smoothing.'))
    if(identical(type,'series-collection')) block_items <- c(block_items, paste0(
      '<h3>Annual series collection: ', length(rec$members), ' topics</h3>',
      '<p>Displays saved annual rows for ', length(rec$members), ' topics from one collection record. ',
      'Each member is a separately checked series record bound through its own count metrics; ',
      'missing years are gaps, never zeros. Panels are display-only and open independently.</p>',
      '<p><a href="report.html#', esc(rec$instance_id), '">Open the collection</a> &#183; topics: ',
      paste(vapply(rec$members, function(m) paste0('<a href="report.html#', esc(m$instance_id), '">',
        esc(label_topic(b, m$selection$topic)), '</a>'), character(1)), collapse = ', '), '</p>',
      '<p class="table-note">Limitation: display of saved observations only; no trend model, smoothing, ',
      'shared scale or cross-topic comparison.</p>'))
    if(identical(type,'coverage-selection')) block_items <- c(block_items, block_row(
      'Coverage and selection',
      'Summarises saved selection records: dataset decisions, included and excluded topics, saved observations and the topics this recipe binds. It is not a measure of disease occurrence.',
      rec$instance_id, 'Saved record summary; per-year completeness is not available.'))
    if(identical(type,'sensitivity-comparison')) block_items <- c(block_items, block_row(
      'Sensitivity comparison',
      'Compares the saved main and sensitivity specifications, their member/input metric lists, totals and saved reference changes. Differences come from saved member lists, not re-estimation.',
      rec$instance_id, 'No robustness, significance or uncertainty assessment is made.'))
    if(identical(type,'monitoring-overview')) block_items <- c(block_items, block_row(
      'Monitoring overview',
      'Shows each included topic’s latest saved observation inside the reporting window, with any saved reference and period comparisons resolved separately and endpoint counts read from their bound input metrics.',
      rec$instance_id, 'Descriptive latest values and saved comparisons; sparklines are not implemented.'))
  }
  if(length(block_items)) parts<-c(parts,'<section class="audit-panel full" id="displayed-blocks"><h2>Methods for the displayed blocks</h2>', block_items, '</section>')
  repro_text <- paste0('<p>The package publishes its effective recipe at <a href="reproduction/composition.json">reproduction/composition.json</a> and a rendering record at <a href="reproduction/reproduction.json">reproduction/reproduction.json</a>. The record gives the supported rendering invocation with labelled placeholders, the recipe digest, the pinned environment and the original-analysis entry point; placeholders must be supplied from a retained checkout, published saved bundle and original snapshot root. The analysis-bundle files listed in bundle.json, plus the manifest, do not contain raw snapshot exports.</p><p>Integrity/inspection example: verifying saved files and digests is not production-analysis reproduction. A portable replay of the original analysis is not currently possible from the published package alone.</p><p class="table-note">', esc(note_m$detail), ' ', esc(note_m$availability), '</p>')
  parts<-c(parts, paste0('<section class="audit-panel full" id="reproduction-access"><h2>Reproduction access</h2>', repro_text, '</section>'))
  parts<-c(parts,'<footer class="dash-footer"><span>Descriptive comparisons do not establish causes, severity or statistical significance.</span><a href="report.html">← Back to findings</a></footer></div>');paste(parts,collapse='\n')
}

presentation_profile <- function(b) {
  p <- b$cfg$presentation
  if(is.null(p)) {
    return(list(
      display_name='Public health', layout='dashboard',
      detail_level='monitoring', version='legacy'
    ))
  }
  if(!p$layout %in% c('dashboard', 'editorial', 'technical')) {
    stop('Unsupported presentation layout')
  }
  p
}
presentation_open <- function(b) {
  p <- presentation_profile(b)
  paste0('<div class="dashboard audience-', esc(p$layout), '">')
}
selection_intro <- function(b) {
  p <- presentation_profile(b)
  included <- if(!is.null(b$selection) && nrow(b$selection))
    sort(unique(b$selection$topic[tolower(as.character(b$selection$status)) == 'included']))
    else sort(unique(as.character(b$classes$topic)))
  in_sums <- if(!is.null(b$selection) && nrow(b$selection)) group_topics(b) else included
  outside_sums <- setdiff(included, in_sums)
  pr <- read_provenance()
  scope <- if(!is.null(pr$composition)) pr$composition$display_scope else NULL
  standalone <- if(!is.null(scope)) unlist(scope$standalone_topics) else character(0)
  monitored <- if(!is.null(scope)) unlist(scope$monitoring_topics) else character(0)
  displayed <- if(!is.null(scope)) unlist(scope$displayed_topics) else character(0)
  groups <- if(!is.null(scope)) scope$group_summaries else list()
  overlap <- intersect(standalone, monitored)
  group_text <- if(length(groups))
    paste0('The report also displays saved group summaries (',
           paste(vapply(groups, function(g) as.character(g$subject), character(1)), collapse = ', '),
           ') whose member topics are listed in the block evidence.')
    else 'This report displays no group-summary block.'
  outside_bits <- vapply(outside_sums, function(topic) {
    base <- paste0(label_topic(b, topic), ' is included in the saved analysis but excluded from group sums.')
    where <- if(topic %in% monitored) ' This report displays it in the monitoring table.'
             else if(topic %in% standalone) ' This report displays it individually.'
             else ' Individual display depends on the blocks selected for this report.'
    paste0(base, where)
  }, character(1))
  technical <- paste0(
    '<p><strong>Diseases included in the saved analysis:</strong> ',
    esc(paste(label_topic(b, included), collapse = ', ')), ' (', length(included), ' topics).</p>',
    '<p><strong>Contributing to group sums:</strong> ',
    esc(paste(label_topic(b, in_sums), collapse = ', ')), ' (', length(in_sums), ' topics).</p>',
    if(length(outside_bits)) paste0('<p>', paste(esc(outside_bits), collapse = ' '), '</p>') else '',
    '<p><strong>Displayed by this report:</strong> ',
    esc(if(length(displayed)) paste(label_topic(b, displayed), collapse = ', ') else 'none'),
    if(length(standalone)) paste0(' — standalone: ', esc(paste(label_topic(b, standalone), collapse = ', '))) else '',
    if(length(monitored)) paste0('; monitoring table: ', esc(paste(label_topic(b, monitored), collapse = ', '))) else '',
    if(length(overlap)) paste0(' (', esc(paste(label_topic(b, overlap), collapse = ', ')), ' appears in both)') else '',
    '. ', esc(group_text), '</p>')
  if(identical(p$layout, 'editorial')) {
    lead <- if(length(displayed)) paste0('This report shows reported ',
      paste(tolower(label_topic(b, displayed)), collapse = ' and '), ' cases in ',
      composition_geography(b), ': annual values for ',
      paste(b$cfg$years, collapse = '–'), ' and a separate comparison with ',
      b$cfg$reference_year, '.')
      else paste0('This report shows saved annual notification counts for ', composition_geography(b), '.')
    return(paste0('<section class="selection-intro"><p class="audience-label">',
      esc(p$display_name), ' · ', esc(p$layout), ' presentation</p>',
      '<p><strong>What this report shows.</strong> ', esc(lead), '</p>',
      '<p>Reported cases are not a count of every infection. Changes may reflect surveillance and testing ',
      'as well as disease occurrence; the figures are descriptive.</p>',
      '<details class="block-inspect" id="intro-scope"><summary>How the analysis was selected</summary>',
      technical,
      '<p>These are recorded notifications; the figures do not establish causes or statistical significance.</p>',
      '</details></section>'))
  }
  paste0('<section class="selection-intro"><p class="audience-label">',
    esc(p$display_name), ' · ', esc(p$layout), ' presentation</p>', technical,
    '<p>These are recorded notifications, not all infections. Changes may reflect surveillance and testing ',
    'as well as disease occurrence. The figures are descriptive; they do not establish causes or statistical significance.</p>',
    '</section>')
}

technical_findings <- function(b) {
  if(presentation_profile(b)$layout != 'technical') return('')
  totals <- b$metrics[
    b$metrics$metric_type == 'group_total',
    c('metric_id', 'subject', 'year', 'value', 'unit')
  ]
  paste0(
    '<section class="audit-panel full"><h2>Technical group totals</h2>',
    html_table(totals),
    '<p class="table-note">Source: metrics.csv in the verified analysis bundle. ',
    'Identifiers support lookup in lineage.csv; no statistics are recalculated here.</p>',
    '<h2>Disease-level comparison</h2>', html_table(friendly_table(b)),
    '</section>'
  )
}

source('audience_reports.R')

# --- Block composition (experimental): order and membership come from a recipe file. ---
# Each registry entry is explicit renderer metadata: label for navigation, whether the
# block is the primary finding, and a renderer that receives the recipe entry. The entry's
# instance_id is the section's DOM identity and is passed into the renderer so descendant
# ids can be namespaced per instance.
composition_labels <- c(intro = 'Context', 'series-trend' = 'Time trend',
                        'series-collection' = 'Time trends by topic',
                        'coverage-selection' = 'What this report covers',
                        'monitoring-overview' = 'Monitoring overview',
                        'sensitivity-comparison' = 'Sensitivity comparison',
                        'reference-comparison' = 'Reference comparison',
                        limitations = 'Limitations', reproduction = 'Reproduction')

# One explicit mapping from the existing presentation layout to composed-block explanation.
# No new configuration field: layout/detail_level already live in each audience's stakeholder.json.
composition_geography <- function(b)
  if(identical(b$cfg$geography,'CHFL')) 'Switzerland and Liechtenstein' else 'Switzerland'

composition_copy <- list(
  technical = list(
    reference = function(b, block, pct, fmt) paste0(
      'Saved comparison: result metric ', esc(block$result$metric_id),
      ' is the percent change in annual reported ', esc(block$measure), ' for ',
      esc(label_topic(b, block$subject)), ' in ', esc(block$latest_year), ' compared with ',
      esc(block$reference_year), '. Bound counts: ', esc(block$reference_count$metric_id), ' (',
      esc(fmt(block$reference_count$value)), ') and ', esc(block$latest_count$metric_id), ' (',
      esc(fmt(block$latest_count$value)), '). Unit ', esc(block$result$unit), '; formula ',
      esc(block$result$formula), '; scope ', esc(composition_geography(b)), '; period type ',
      esc(b$cfg$period_type), '; displayed value ', esc(pct),
      '. This block is a descriptive comparison of saved records: it supplies no inferential ',
      'uncertainty estimate and no causal conclusion.'),
    limitation = paste0('Automated checks test data handling and consistency; they do not establish ',
                        'the completeness or accuracy of the source counts.')
  ),
  dashboard = list(
    reference = function(b, block, pct, fmt) paste0(
      'Monitoring context: latest saved annual notification counts for the included topics and the ',
      'recorded comparisons available in this bundle. Observed change: ', esc(pct),
      ' in reported ', esc(block$measure), ' for ', esc(label_topic(b, block$subject)), ' in ',
      esc(block$latest_year), ' compared with ', esc(block$reference_year), ' (',
      esc(fmt(block$reference_count$value)), ' and ', esc(fmt(block$latest_count$value)),
      ' reported cases). Scope: ', esc(composition_geography(b)),
      ' national notification counts; reporting years ', esc(paste(b$cfg$years, collapse='–')),
      ', reference year ', esc(block$reference_year),
      '. This indicator describes national reported notifications only: it provides no canton- or ',
      'institution-specific evidence, applies no operational threshold and supports no ',
      'recommendation, and it does not measure infection incidence, clinical severity or ',
      'statistical significance.'),
    limitation = paste0('Automated checks test data handling and consistency, not the completeness ',
                        'or accuracy of the source counts. No operational threshold or recommendation ',
                        'is derived from them.')
  ),
  editorial = list(
    reference = function(b, block, pct, fmt) paste0(
      'In plain terms: ', esc(fmt(block$latest_count$value)), ' ', esc(block$measure), ' of ',
      esc(tolower(label_topic(b, block$subject))), ' were reported in ', esc(block$latest_year),
      ', compared with ', esc(fmt(block$reference_count$value)), ' in ', esc(block$reference_year),
      '. That is a change of ', esc(pct), ' between the two years. Reported notifications are counts ',
      'of cases reported to the surveillance system, not a count of every infection. More ',
      'notifications do not necessarily mean a matching rise in infections or in how severe the ',
      'illness is; this comparison is descriptive and is not a statistical test.'),
    limitation = paste0('The data went through automated checks for handling and consistency. ',
                        'These checks cannot prove that the reported counts are complete or accurate.')
  )
)

composition_copy_for <- function(b) {
  copy <- composition_copy[[presentation_profile(b)$layout]]
  if(is.null(copy)) composition_copy$technical else copy
}

composed_limitations <- function(b) paste0(document_limits(b),
  '<div class="audience-explanation"><p>', esc(composition_copy_for(b)$limitation), '</p></div>',
  quality_summary_html(b))

# --- Saved data-quality records and report settings (no recalculation) ---
quality_check_titles <- c(
  no_duplicate_rows = 'Duplicate rows',
  periods_parseable = 'Periods parseable',
  values_numeric = 'Values numeric',
  finite_values = 'Values finite',
  no_negative_counts = 'No negative counts',
  value_present = 'Missing values',
  year_equals_sum_of_months = 'Annual total vs sum of months',
  cantons_sum_to_national = 'Cantons vs national total',
  metadata_schema = 'Source metadata schema',
  metadata_conflict = 'Conflicting source metadata')

quality_check_meanings <- c(
  no_duplicate_rows = 'Counts rows repeated for the same dataset, measure, period and group set.',
  periods_parseable = 'Counts rows whose period could not be parsed as a date.',
  values_numeric = 'Counts rows whose value is not numeric.',
  finite_values = 'Counts rows with an infinite value.',
  no_negative_counts = 'Counts negative case or consultation counts.',
  value_present = 'Share of rows with a missing value. 50% or more is a warning because the report selection needs complete values.',
  year_equals_sum_of_months = 'Compares an annual total with the sum of 12 monthly rows (2% tolerance). Skipped when no complete pair exists.',
  cantons_sum_to_national = 'Compares 26 cantons with the CH national total (5% tolerance). Skipped unless exactly 26 cantons and a CH total exist.',
  metadata_schema = 'Records source metadata that failed the expected schema.',
  metadata_conflict = 'Records identical data bytes carrying different metadata.')

quality_check_title <- function(code) {
  if(code %in% names(quality_check_titles)) quality_check_titles[[code]] else 'Unknown check'
}
quality_check_meaning <- function(code) {
  if(code %in% names(quality_check_meanings)) quality_check_meanings[[code]]
  else 'No plain-language explanation is available for this check yet.'
}
quality_dataset_label <- function(b, ids) {
  idx <- match(ids, as.character(b$sources$dataset_id))
  topic <- ifelse(is.na(idx), as.character(ids), as.character(b$sources$topic[idx]))
  source <- ifelse(is.na(idx), 'source not recorded', as.character(b$sources$source_system[idx]))
  paste0(label_topic(b, topic), ' · ', source)
}

# Shared preparation: the report summary and the methods detail are built from this one
# data frame, so totals and groups cannot drift between pages.
quality_results <- function(b) {
  checks <- b$checks
  dataset_id <- as.character(checks$dataset_id)
  check <- as.character(checks$check)
  status <- toupper(as.character(checks$status))
  detail <- as.character(checks$detail)
  sel <- b$selection
  sel_id <- as.character(sel$dataset_id)
  sel_rows <- vapply(dataset_id, function(x) sum(sel_id == x), integer(1))
  sel_first <- match(dataset_id, sel_id)
  sel_status <- ifelse(sel_rows == 1, as.character(sel$status[sel_first]), NA_character_)
  sel_reason <- ifelse(sel_rows == 1, as.character(sel$reason[sel_first]), NA_character_)
  src <- match(dataset_id, as.character(b$sources$dataset_id))
  topic <- ifelse(is.na(src), NA_character_, as.character(b$sources$topic[src]))
  source <- ifelse(is.na(src), NA_character_, as.character(b$sources$source_system[src]))
  dataset_label <- ifelse(is.na(src), 'Source metadata not recorded',
                          paste0(label_topic(b, topic), ' · ', source))
  selection <- ifelse(sel_rows == 0, 'No selection record',
                ifelse(sel_rows > 1, paste0('Ambiguous selection mapping (', sel_rows, ' rows)'),
                  ifelse(tolower(sel_status) == 'included', 'Included in selected inputs',
                    paste0('Excluded from selected inputs',
                           ifelse(nzchar(sel_reason), paste0(' — ', sel_reason), '')))))
  relevance <- ifelse(sel_rows == 0, 'Relevance not established (no selection record)',
                ifelse(sel_rows > 1, 'Relevance not established (ambiguous selection mapping)',
                  ifelse(tolower(sel_status) == 'included',
                         'Dataset recorded as included in the selected inputs',
                         'Dataset recorded as excluded from the selected inputs')))
  d <- data.frame(status = status, check = check, detail = detail, dataset_id = dataset_id,
                  dataset_label = dataset_label, selection = selection, relevance = relevance,
                  selection_rows = sel_rows,
                  check_title = vapply(check, quality_check_title, character(1)),
                  check_meaning = vapply(check, quality_check_meaning, character(1)),
                  stringsAsFactors = FALSE)
  d$rank <- match(d$status, c('FAIL', 'WARN', 'PASS', 'SKIP'))
  d$rank[is.na(d$rank)] <- 9L
  d <- d[order(d$rank, d$check, d$dataset_id, d$detail), , drop = FALSE]
  rownames(d) <- NULL
  d
}

quality_totals <- function(d) {
  list(total = nrow(d), rules = length(unique(d$check)), datasets = length(unique(d$dataset_id)),
       pass = sum(d$status == 'PASS'), warn = sum(d$status == 'WARN'),
       skip = sum(d$status == 'SKIP'), fail = sum(d$status == 'FAIL'))
}

quality_totals_sentence <- function(t) paste0(
  t$total, ' recorded check-result rows covering ', t$rules,
  ' distinct rule identifiers and ', t$datasets, ' datasets: ',
  t$pass, ' PASS, ', t$skip, ' SKIP, ', t$warn, ' WARN, ', t$fail, ' FAIL.')

quality_view_sentence <- function(b) switch(presentation_profile(b)$layout,
  technical = 'Technical view: saved check identifiers, recorded diagnostics and selection records are shown unchanged. Validation was not rerun for this report.',
  dashboard = 'Monitoring view: warnings are tied to the affected dataset and its recorded selection decision. A warning is not an operational threshold or a recommendation.',
  'In plain words: the automatic checks look for data problems such as missing values. These are notes about the source data, not findings about disease levels.')

# Concise main-report summary with a direct route to the detailed methods section.
quality_summary_html <- function(b) {
  d <- quality_results(b)
  t <- quality_totals(d)
  attention <- d[d$status %in% c('WARN', 'FAIL'), , drop = FALSE]
  categories <- ''
  if(nrow(attention)) {
    codes <- unique(attention$check)
    categories <- paste0('<ul class="quality-categories">', paste(vapply(codes, function(code) {
      rows <- attention[attention$check == code, , drop = FALSE]
      n_datasets <- length(unique(rows$dataset_id))
      paste0('<li>', esc(quality_check_title(code)), ' (<code>', esc(code), '</code>): ',
             nrow(rows), ' ', ifelse(nrow(rows) == 1, 'result', 'results'), ' across ',
             n_datasets, ' dataset', ifelse(n_datasets == 1, '', 's'), '</li>')
    }, character(1)), collapse = ''), '</ul>')
  }
  excluded <- sum(grepl('excluded from the selected inputs', attention$relevance, fixed = TRUE))
  included <- sum(grepl('included in the selected inputs', attention$relevance, fixed = TRUE))
  unresolved <- nrow(attention) - excluded - included
  relevance <- if(!nrow(attention))
    'No WARN or FAIL results are recorded in this bundle. That is not proof that source counts are complete or accurate.'
  else if(included == 0 && unresolved == 0)
    "These warnings concern datasets recorded as excluded from this report's selected inputs. Finding-level warning relevance has not been evaluated."
  else
    'Some warnings concern datasets recorded as included, or their selection mapping is unresolved. Finding-level warning relevance has not been evaluated.'
  paste0('<div id="quality-summary"><p><strong>Data quality:</strong> ', quality_totals_sentence(t), '</p>',
    '<details class="quality-warnings" id="quality-warnings"><summary>What was flagged?</summary>',
    categories,
    '<p class="table-note">', esc(quality_view_sentence(b)), '</p>',
    '<p class="table-note">', esc(relevance), '</p>',
    if('quality' %in% b$cfg$outputs)
      '<p><a href="methods.html#quality-checks">Inspect all checks and detailed warning explanations</a> · <a href="data/checks.csv" download>Download exact check results — CSV</a></p>' else '',
    '</details></div>')
}

quality_explanation_html <- function(d, code) {
  rows <- d[d$check == code & d$status %in% c('WARN', 'FAIL'), , drop = FALSE]
  handling <- unique(rows$selection)
  diagnostics <- paste0('<li>', esc(rows$dataset_label[seq_len(nrow(rows))]), ' (<code>',
                        esc(rows$dataset_id), '</code>): <strong>', esc(rows$status), '</strong> — “',
                        esc(rows$detail), '”</li>', collapse = '')
  limit <- if(identical(code, 'value_present'))
    paste0('The recorded percentage is the share of rows in that harmonised dataset whose value is missing ',
           '(the value_present rule uses the mean of the missing-value indicator). It does not identify which ',
           'years, measures or individual records are missing, and it is not a statement about the displayed comparison.')
  else paste0('The diagnostic text is shown exactly as recorded. Its denominator and affected years, measures or ',
              'records are not re-derived here.')
  paste0('<details class="quality-explanation"><summary>', esc(quality_check_title(code)), ' (<code>', esc(code),
    '</code>) — ', nrow(rows), ' ', ifelse(nrow(rows) == 1, 'result', 'results'), ' across ',
    length(unique(rows$dataset_id)), ' dataset', ifelse(length(unique(rows$dataset_id)) == 1, '', 's'), '</summary>',
    '<p><strong>What the rule tests:</strong> ', esc(quality_check_meaning(code)), '</p>',
    '<p><strong>What the saved diagnostics say:</strong></p><ul>', diagnostics, '</ul>',
    '<p><strong>Affected dataset and recorded fields:</strong> the rows above are the complete saved results for this rule. ',
    'Period or variable details are shown only where the recorded diagnostic contains them.</p>',
    '<p><strong>Recorded selection handling:</strong> ', esc(paste(handling, collapse = '; ')), '.</p>',
    '<p><strong>Supported interpretation:</strong> this is a dataset-level data-quality result. It does not establish ',
    'which displayed findings, if any, are affected; finding-level warning relevance has not been evaluated.</p>',
    '<p><strong>Limits:</strong> ', esc(limit), '</p>',
    '<p class="table-note">Original diagnostic and stable identifiers are preserved in the results table below and in ',
    '<a href="data/checks.csv" download>checks.csv</a>.</p></details>')
}

quality_methods_html <- function(b) {
  d <- quality_results(b)
  t <- quality_totals(d)
  p <- presentation_profile(b)
  cfg <- b$cfg
  attention <- d[d$status %in% c('WARN', 'FAIL'), , drop = FALSE]
  default_status <- if(nrow(attention)) 'ATTENTION' else 'ALL'
  status_values <- c('ATTENTION', 'ALL', 'WARN', 'FAIL', 'PASS', 'SKIP')
  status_labels <- c('Warnings and failures', 'All results', 'WARN', 'FAIL', 'PASS', 'SKIP')
  status_options <- paste0(vapply(seq_along(status_values), function(i) paste0(
    '<option value="', status_values[i], '"',
    if(identical(status_values[i], default_status)) ' selected' else '', '>',
    status_labels[i], '</option>'), character(1)), collapse = '')
  checks <- sort(unique(d$check))
  check_options <- paste0('<option value="ALL">All check rules</option>',
    paste(vapply(checks, function(code) paste0('<option value="', esc(code), '">',
      esc(quality_check_title(code)), ' (', esc(code), ')</option>'), character(1)), collapse = ''))
  explanations <- paste(vapply(unique(d$check[d$status %in% c('WARN', 'FAIL')]),
                               function(code) quality_explanation_html(d, code), character(1)), collapse = '')
  row_html <- vapply(seq_len(nrow(d)), function(i) {
    status_class <- paste0('quality-status quality-status--', tolower(d$status[i]))
    search <- tolower(paste(d$dataset_label[i], d$dataset_id[i], d$check[i], d$detail[i]))
    paste0('<tr data-status="', esc(d$status[i]), '" data-check="', esc(d$check[i]),
           '" data-search="', esc(search), '">',
      '<td><span class="', status_class, '">', esc(d$status[i]), '</span></td>',
      '<td>', esc(d$check_title[i]), '</td>',
      '<td><code>', esc(d$check[i]), '</code></td>',
      '<td>', esc(d$dataset_label[i]), '</td>',
      '<td class="quality-id"><code>', esc(d$dataset_id[i]), '</code></td>',
      '<td class="quality-diagnostic">', esc(d$detail[i]), '</td>',
      '<td>', esc(d$selection[i]), '</td>',
      '<td>', esc(d$relevance[i]), '</td></tr>')
  }, character(1))
  size <- function(name) if(file.exists(name)) paste0(' (', format(file.size(name), big.mark = ',', scientific = FALSE, trim = TRUE), ' bytes)') else ''
  paste0('<style>',
    '.quality-results{max-height:32rem;overflow:auto;border:1px solid #dfe6e5;border-radius:8px}',
    '.quality-results table{min-width:72rem;margin:0}',
    '.quality-results thead th{position:sticky;top:0;background:#fff;z-index:1}',
    '.quality-controls{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end;margin:12px 0}',
    '.quality-controls>div{min-width:0;flex:1 1 14rem;max-width:100%}',
    '.quality-controls select,.quality-controls input{max-width:100%;width:100%;box-sizing:border-box}',
    '.quality-controls label{display:block;font-size:12px;color:#52656b}',
    '.quality-diagnostic{max-width:22rem;overflow-wrap:anywhere}',
    '.quality-id{overflow-wrap:anywhere}',
    '.quality-status--warn{color:#8a5a00;font-weight:600}',
    '.quality-status--fail{color:#a3202b;font-weight:600}',
    '.quality-status--pass{color:#247c85}',
    '.quality-status--skip{color:#52656b}',
    '</style>',
    '<section class="audit-panel full" id="quality-checks">',
    '<h2>Data quality: all recorded check results</h2>',
    '<p class="table-note">Report audience: <strong>', esc(p$display_name), '</strong> (',
    esc(cfg$id), ' · ', esc(p$layout), ' · ', esc(p$detail_level), '). Saved scope: ',
    esc(composition_geography(b)), '; reporting years ', esc(paste(cfg$years, collapse = '–')),
    '; reference year ', esc(cfg$reference_year), '.</p>',
    '<p><a href="report.html#quality-summary">← Back to the report quality summary</a></p>',
    '<p><strong>Counting definitions:</strong> ', quality_totals_sentence(t),
    ' The 50% missing-value threshold is a configured data-validation warning rule, not an operational or clinical threshold and not a guarantee of fitness; missing-value warnings are distinct from classification/source-type exclusion reasons. A check-result row is one recorded result from the saved validation output; aggregation rules such as ',
    'year_equals_sum_of_months and cantons_sum_to_national record one row per compared measure/period, so rows are not ',
    'one rule per dataset. Rows are not affected-record or affected-finding counts. PASS meets the rule; WARN needs ',
    'interpretation; SKIP means the rule could not be applied; FAIL blocks publication. Automated checks are not proof ',
    'that source counts are complete or accurate.</p>',
    '<p class="table-note">', esc(quality_view_sentence(b)), '</p>',
    if(nzchar(explanations)) paste0('<h3>Detailed warning explanations</h3>', explanations) else
      '<p>No WARN or FAIL results are recorded in this bundle.</p>',
    '<h3>All recorded check results</h3>',
    '<div class="quality-controls">',
    '<div><label for="quality-status">Status filter</label><select id="quality-status">', status_options, '</select></div>',
    '<div><label for="quality-check">Check rule filter</label><select id="quality-check">', check_options, '</select></div>',
    '<div><label for="quality-search">Dataset search</label><input id="quality-search" type="search" placeholder="Dataset name or ID"></div>',
    '</div>',
    '<p id="quality-count" aria-live="polite">Showing all ', t$total, ' recorded check results</p>',
    '<div class="quality-results" tabindex="0" role="region" aria-label="Scrollable table of recorded check results">',
    '<table class="report-table" id="quality-results-table">',
    '<caption>All ', t$total, ' recorded check results, ordered with failures first, then warnings, PASS and SKIP, ',
    'then rule and dataset. The status filter starts on warnings and failures when any exist.</caption>',
    '<thead><tr><th scope="col">Status</th><th scope="col">Check</th><th scope="col">Check ID</th>',
    '<th scope="col">Dataset</th><th scope="col">Dataset ID</th><th scope="col">Recorded diagnostic</th>',
    '<th scope="col">Selection record</th><th scope="col">Relevance to report inputs</th></tr></thead>',
    '<tbody>', paste(row_html, collapse = ''), '</tbody></table></div>',
    '<p class="table-note">Source: saved checks.csv, selection.csv and sources.csv from this analysis bundle. ',
    'No validation was rerun for this report. Missing or ambiguous selection mappings are shown explicitly per row.</p>',
    '<h3>Download supporting records</h3><ul class="quality-downloads">',
    '<li><a href="data/checks.csv" download>Download exact check results — CSV</a>', size('checks.csv'), '</li>',
    '<li><a href="data/selection.csv" download>Download selection records — CSV</a>', size('selection.csv'), '</li>',
    '<li><a href="data/sources.csv" download>Download source records — CSV</a>', size('sources.csv'), '</li>',
    '</ul></section>',
    quality_filter_script())
}

quality_filter_script <- function() paste0('<script>', "
(function(){
  var statusEl=document.getElementById('quality-status');
  var checkEl=document.getElementById('quality-check');
  var searchEl=document.getElementById('quality-search');
  var countEl=document.getElementById('quality-count');
  var table=document.getElementById('quality-results-table');
  if(!table||!statusEl||!checkEl||!searchEl||!countEl) return;
  var rows=Array.prototype.slice.call(table.tBodies[0].rows);
  function matches(row){
    var s=statusEl.value, c=checkEl.value, q=searchEl.value.toLowerCase();
    var ok=(s==='ALL')||(s==='ATTENTION'?(row.getAttribute('data-status')==='WARN'||row.getAttribute('data-status')==='FAIL'):row.getAttribute('data-status')===s);
    if(ok&&c!=='ALL'&&row.getAttribute('data-check')!==c) ok=false;
    if(ok&&q&&row.getAttribute('data-search').indexOf(q)===-1) ok=false;
    return ok;
  }
  function apply(){
    var shown=0;
    rows.forEach(function(r){var ok=matches(r); r.hidden=!ok; if(ok) shown++;});
    countEl.textContent='Showing '+shown+' of '+rows.length+' recorded check results';
  }
  statusEl.addEventListener('change',apply);
  checkEl.addEventListener('change',apply);
  searchEl.addEventListener('input',apply);
  apply();
})();
", '</script>')

artifact_meta <- list(
  'stakeholder.json' = list(label = 'exact audience parameters', type = 'JSON'),
  'bundle.json' = list(label = 'bundle manifest', type = 'JSON'),
  'metrics.csv' = list(label = 'Metrics', type = 'CSV'),
  'lineage.csv' = list(label = 'Calculation lineage', type = 'CSV'),
  'checks.csv' = list(label = 'Check results', type = 'CSV'),
  'series.csv' = list(label = 'Plotted series', type = 'CSV'),
  'selection.csv' = list(label = 'Dataset selection decisions', type = 'CSV'),
  'sources.csv' = list(label = 'Source registry', type = 'CSV'),
  'snapshot.json' = list(label = 'Snapshot record', type = 'JSON'),
  'pathogen_class.csv' = list(label = 'Pathogen classes', type = 'CSV'))

artifact_type <- function(name) {
  ext <- tolower(tools::file_ext(name))
  if(ext == 'json') 'JSON' else if(ext == 'csv') 'CSV' else toupper(ext)
}

composed_settings_html <- function(b) {
  pr <- read_provenance()
  p <- presentation_profile(b)
  cfg <- b$cfg
  row <- function(k, v) paste0('<dt>', esc(k), '</dt><dd>', v, '</dd>')
  composition <- 'not composed'
  if(!is.null(pr$composition) && !is.null(pr$composition$effective_recipe)) {
    order <- vapply(pr$composition$effective_recipe, function(x) as.character(x$block), character(1))
    composition <- paste0(esc(pr$composition$audience), ' · recipe ',
                          substr(esc(pr$composition$recipe_sha256), 1, 16), ' · ',
                          esc(paste(order, collapse = ' → ')))
  }
  items <- c(row('Audience', paste0(esc(cfg$id), ' — ', esc(cfg$title))),
             row('Geography', esc(composition_geography(b))),
             row('Reporting years', esc(paste(cfg$years, collapse = '–'))),
             row('Reference year', esc(cfg$reference_year)),
             row('Measures', esc(paste(cfg$measures_preferred, collapse = ', '))),
             row('Excluded from group sums', esc(paste(label_topic(b, cfg$exclude_from_group_totals), collapse = ', '))),
             row('Presentation', paste0(esc(p$display_name), ' · ', esc(p$layout), ' · ', esc(p$detail_level))),
             row('Composition recipe', composition))
  manifest_files <- names(b$manifest$files)
  published <- unique(c(manifest_files, 'bundle.json'))
  rows <- vapply(published, function(n) {
    meta <- artifact_meta[[n]]
    label <- if(is.null(meta)) n else meta$label
    type <- if(is.null(meta)) artifact_type(n) else meta$type
    available <- file.exists(n)
    size <- if(available) format(file.size(n), big.mark = ',', scientific = FALSE, trim = TRUE) else 'not available'
    digest <- if(identical(n, 'bundle.json')) 'not self-digested'
              else if(n %in% manifest_files) substr(b$manifest$files[[n]], 1, 16) else 'not recorded'
    action <- if(available) paste0('<a href="data/', esc(n), '" download>Download ', esc(label), ' — ', esc(type), '</a>')
              else '<span class="table-note">Not published</span>'
    paste0('<tr><td>', esc(label), '<br><code>', esc(n), '</code></td><td>', esc(type),
           '</td><td>', size, '</td><td><code>', esc(digest), '</code></td><td>', action, '</td></tr>')
  }, character(1))
  unavailable <- published[!file.exists(published)]
  subset_note <- paste0('This report folder publishes ', length(published), ' files: the ',
    length(manifest_files), ' analysis-bundle files named by bundle.json plus the manifest itself. ',
    'The raw source exports in the archived snapshot are not part of this download set, and no complete ',
    'source-bundle claim is made. bundle.json is the authoritative list of analysis-bundle files and is not self-digested.')
  if(length(unavailable)) subset_note <- paste0(subset_note, ' Not available at render time: ',
    esc(paste(unavailable, collapse = ', ')), '.')
  paste0('<details class="report-settings" id="report-settings"><summary>Report settings and source files</summary>',
    '<dl class="provenance-list">', paste(items, collapse = ''), '</dl>',
    '<p class="table-note">Audience parameters are the validated settings that produced this report. ',
    'The artifact manifest lists the saved files and their SHA-256 digests so integrity can be checked. ',
    'Matching digests show that the files agree with the manifest; they do not establish scientific correctness.</p>',
    '<table class="report-table"><thead><tr><th scope="col">Artifact</th><th scope="col">Type</th>',
    '<th scope="col">Bytes</th><th scope="col">SHA-256 (first 16)</th><th scope="col">Download</th></tr></thead><tbody>',
    paste(rows, collapse = ''), '</tbody></table>',
    '<p class="table-note">', subset_note, ' Sizes are read from the packaged bundle at render time.</p></details>')
}

# --- Saved annual series block (display only; no count or trend is calculated) ---
# Inspectable plot preparation: one point per saved observation, and a segment group that
# changes whenever the next observed year is not the immediately following year.
series_plot_data <- function(block) {
  obs <- block$observations
  if(is.null(obs) || !length(obs)) return(NULL)
  d <- data.frame(
    year = vapply(obs, function(o) as.integer(o$year), integer(1)),
    value = vapply(obs, function(o) as.numeric(o$value), numeric(1)),
    stringsAsFactors = FALSE)
  d <- d[order(d$year), , drop = FALSE]
  d$segment <- cumsum(c(TRUE, diff(d$year) > 1L))
  d
}

series_value_rows <- function(block) {
  req <- block$periods$requested
  years <- seq.int(as.integer(req[[1]]), as.integer(req[[2]]))
  by_year <- setNames(vapply(block$observations, function(o) as.numeric(o$value), numeric(1)),
                      vapply(block$observations, function(o) as.character(o$year), character(1)))
  found <- as.character(years) %in% names(by_year)
  data.frame(Year = years,
             Value = ifelse(found,
                            format(by_year[as.character(years)], big.mark = ',', scientific = FALSE, trim = TRUE),
                            'Not available'),
             Unit = rep(block$presentation$unit, length(years)),
             Availability = ifelse(found, 'Reported', 'Not available'),
             stringsAsFactors = FALSE)
}

plot_series_trend <- function(block) {
  d <- series_plot_data(block)
  req <- block$periods$requested
  years <- seq.int(as.integer(req[[1]]), as.integer(req[[2]]))
  p <- ggplot2::ggplot(d, ggplot2::aes(year, value)) +
    ggplot2::scale_x_continuous(limits = c(min(years) - 0.2, max(years) + 0.2),
                                breaks = years,
                                labels = function(x) as.character(as.integer(x))) +
    ggplot2::scale_y_continuous(limits = c(0, NA),
                                expand = ggplot2::expansion(mult = c(0, .08)),
                                labels = function(x) format(x, big.mark = ',', scientific = FALSE, trim = TRUE)) +
    ggplot2::labs(x = 'Year', y = paste('Reported', block$selection$measure)) +
    report_theme()
  # A line is only drawn where two or more consecutive years are available. A single
  # observation (or a fully gapped window) is shown as points, never as an invented line.
  if(any(table(d$segment) > 1L)) {
    p <- p + ggplot2::geom_line(ggplot2::aes(group = segment), colour = '#247c85', linewidth = 1)
  }
  p + ggplot2::geom_point(colour = '#247c85', size = 2.6)
}

series_trend_block <- function(b, evidence_file = '', instance_id = NULL) {
  if(is.null(instance_id) || !nzchar(instance_id))
    stop('A composed series-trend block needs an instance id')
  unavailable <- function(reason) paste0(
    '<h3>Reported values over time unavailable</h3>',
    '<p class="caption">The saved series record could not be used, so no values are shown.</p>',
    '<div class="audit-row"><span>Reason</span><strong>', esc(reason), '</strong></div>')
  if(!knitr::is_html_output()) return('')
  if(!nzchar(evidence_file)) return(unavailable('the evidence file was not supplied'))
  if(!file.exists(evidence_file)) return(unavailable(paste('evidence file is missing:', evidence_file)))
  record <- tryCatch(jsonlite::fromJSON(evidence_file, simplifyVector = FALSE),
                     error = function(e) NULL)
  if(is.null(record)) return(unavailable('evidence file is not valid JSON'))
  if(is.null(record$blocks) || !length(record$blocks)) return(unavailable('evidence file carries no blocks'))
  # Select by instance id AND expected block type. No first-record fallback.
  matches <- Filter(function(x) identical(x$instance_id, instance_id) &&
                      identical(x$component$type, 'series-trend'), record$blocks)
  if(!length(matches))
    return(unavailable(paste('no checked series-trend record for block instance', instance_id)))
  block <- matches[[1]]
  if(!identical(block$status, 'verified'))
    return(unavailable(paste0(if(is.null(block$code)) 'failed' else block$code, ': ',
                              if(is.null(block$detail)) '' else block$detail)))

  series_body_html(b, block, instance_id)
}

# Body of one saved annual series panel: heading, chart, exact values, inspector. Reused by the
# single-topic block and by each collection member, so there is exactly one series renderer.
series_body_html <- function(b, block, instance_id) {
  req <- block$periods$requested
  years <- seq.int(as.integer(req[[1]]), as.integer(req[[2]]))
  label <- label_topic(b, block$selection$topic)
  geography <- if(identical(block$selection$geography, 'CHFL'))
    'Switzerland and Liechtenstein' else 'Switzerland'
  unit <- block$presentation$unit
  style <- if(!is.null(block$presentation$style)) as.character(block$presentation$style) else NULL
  compact <- identical(style, 'compact')
  editorial <- identical(presentation_profile(b)$layout, 'editorial')
  span <- paste0(years[[1]], '–', years[[length(years)]])
  alt <- paste0('Annual reported ', unit, ' for ', label, ', ', span,
                '. Missing years are shown as gaps, not zero.')
  values <- series_value_rows(block)
  table_rows <- paste(vapply(seq_len(nrow(values)), function(i) paste0(
    '<tr><td>', esc(values$Year[i]), '</td><td>', esc(values$Value[i]), '</td><td>',
    esc(values$Unit[i]), '</td><td>', esc(values$Availability[i]), '</td></tr>'),
    character(1)), collapse = '')
  bindings <- paste(vapply(block$observations, function(o)
    paste0(esc(o$year), ' → ', esc(o$count_metric_id)), character(1)), collapse = '; ')

  if(editorial) {
    explanation <- paste0(
      'Reported cases of ', esc(label), ' in ', esc(geography), ', ', esc(span),
      '. Each point is the number reported to the national surveillance system in that year; ',
      'reported cases are not a count of every infection.')
  } else {
    explanation <- paste0(
      'Saved annual observations for ', esc(label), ' (', esc(unit), ') in ', esc(geography),
      '. The graph shows the reported years from ', years[[1]], ' to ', years[[length(years)]],
      ' only; it does not interpolate a missing year and does not estimate a trend.')
  }
  if(length(block$missing_years)) explanation <- paste0(explanation,
    if(editorial) paste0(' No data were recorded for ',
                         esc(paste(block$missing_years, collapse = ', ')),
                         ', so the line has a gap there; that is not the same as zero cases.')
    else paste0(' No saved observation exists for ', esc(paste(block$missing_years, collapse = ', ')),
                ', so the line is broken there. A missing year is not a zero count.'))
  if(length(block$observations) == 1L) explanation <- paste0(explanation,
    if(editorial) ' Only one year is available here, so no trend can be described; the value is a single point.'
    else ' Only one saved observation falls inside this window, so no temporal pattern can be assessed and the value is shown as a single point.')
  if(isTRUE(block$periods$reference_outside_window)) explanation <- paste0(explanation,
    if(editorial) paste0(' The ', esc(block$periods$reference_year),
                         ' comparison is shown separately in the reference comparison, not in this chart.')
    else paste0(' The ', esc(block$periods$reference_year),
                ' reference observation belongs to the adjacent reference comparison and lies outside this display window.'))

  # Saved quality records only: dataset-level results, no validation rerun.
  q <- quality_results(b)
  qd <- q[q$dataset_id == block$selection$dataset_id, , drop = FALSE]
  quality <- if(!nrow(qd))
    'No recorded check results for this dataset. That is not evidence that the source counts are complete or accurate.'
  else paste0(nrow(qd), ' recorded check results for this dataset: ',
    sum(qd$status == 'PASS'), ' PASS, ', sum(qd$status == 'WARN'), ' WARN, ',
    sum(qd$status == 'SKIP'), ' SKIP, ', sum(qd$status == 'FAIL'), ' FAIL.',
    ' Dataset-level only; finding-level warning relevance has not been evaluated.')

  row <- function(k, v) paste0('<div class="audit-row"><span>', esc(k), '</span><strong>',
                               esc(v), '</strong></div>')
  code_row <- function(k, v) paste0('<div class="audit-row"><span>', esc(k),
                                    '</span><strong><code>',
                                    gsub('--', '&#45;&#45;', esc(v), fixed = TRUE),
                                    '</code></strong></div>')
  displayed <- paste(block$periods$effective, collapse = ', ')
  missing <- if(length(block$missing_years)) paste(block$missing_years, collapse = ', ') else 'none'
  trace <- paste(vapply(block$trace, function(t)
    paste0(t$field, ' = ', t$value, ' (', t$source, ')'), character(1)), collapse = '; ')

  heading <- if(editorial) paste0('Reported cases over time: ', label)
             else paste0(label, ': reported ', unit, ', ', span)
  meta_line <- if(editorial)
    paste0('<p class="series-meta">', esc(geography), ' · years ', esc(span), '</p>')
    else paste0('<p class="series-meta">', esc(label), ' · measure ', esc(block$selection$measure),
                ' · ', esc(geography), ' · displayed years ', esc(displayed), '</p>')

  paste0('<h3>', esc(heading), '</h3>', meta_line,
    '<figure class="series-figure', if(compact) ' series-figure--compact' else '', '">',
    chart_image(plot_series_trend(block), alt, 7.2, if(compact) 2.4 else 3.6), '</figure>',
    '<p class="caption">', explanation, '</p>',
    '<details class="series-values" id="', esc(paste0(instance_id, '-values')),
    '"><summary>View exact values</summary><div class="table-scroll">',
    '<table class="report-table"><caption>Reported ', esc(unit), ' for ', esc(label),
    ', by requested year. Missing years are marked unavailable, not zero.</caption>',
    '<thead><tr><th scope="col">Year</th><th scope="col">Recorded value</th>',
    '<th scope="col">Unit</th><th scope="col">Availability</th></tr></thead><tbody>',
    table_rows, '</tbody></table></div>',
    '<p class="table-note">Source: saved series.csv rows bound through count metrics. ',
    'Display values are rounded for readability; the exact saved values are in the download.</p></details>',
    '<details class="block-inspect" id="', esc(paste0(instance_id, '-inspect')),
    '"><summary>Inspect this block</summary>',
    row('Topic', label), row('Measure', block$selection$measure), row('Geography', geography),
    row('Dataset', block$selection$dataset_id), row('Source system', block$selection$source_system),
    row('Requested years', paste0(years[[1]], '–', years[[length(years)]])),
    if(!is.null(style)) row('Presentation style', style),
    row('Displayed years', displayed), row('Missing years', missing),
    row('Saved row bindings', bindings),
    row('Method', 'Display of saved annual observations; no source-count or scientific-result recalculation'),
    row('Series artifact', paste0(block$artifact$file, ' · ', substr(block$artifact$digest, 1, 16))),
    row('Snapshot', block$snapshot$snapshot_id),
    row('Reference year', block$periods$reference_year),
    row('Quality context', quality), row('Effective settings', trace),
    row('Analysis code', paste0(block$implementation$analysis$file, ' · ',
                                substr(block$implementation$analysis$sha256, 1, 16))),
    row('Render code', paste0(block$implementation$presentation$file, ' · ',
                              substr(block$implementation$presentation$sha256, 1, 16))),
    row('Analytical identity', block$identities$analytical),
    row('Rows identity', block$identities$rows),
    row('Instance identity', block$identities$instance),
    code_row('Entry point', block$reproduction$entry_point),
    '<p><a href="data/series.csv" download>Download the saved series rows — CSV</a> · ',
    '<a href="data/metrics.csv" download>Download the bound count metrics — CSV</a></p>',
    '<p class="caption">Identities show that these records agree with each other; they do not ',
    'prove the numbers are correct. Opening this panel performs no calculation.</p></details>')
}


# --- Saved annual series collection: one native disclosure panel per topic ---
series_panel_span <- function(block) {
  req <- block$periods$requested
  years <- seq.int(as.integer(req[[1]]), as.integer(req[[2]]))
  paste0(years[[1]], '–', years[[length(years)]])
}

series_collection_block <- function(b, evidence_file = '', instance_id = NULL) {
  if(is.null(instance_id) || !nzchar(instance_id))
    stop('A composed series-collection block needs an instance id')
  unavailable <- function(reason) paste0(
    '<h3>Reported values over time unavailable</h3>',
    '<p class="caption">The saved series collection record could not be used, so no values are shown.</p>',
    '<div class="audit-row"><span>Reason</span><strong>', esc(reason), '</strong></div>')
  if(!knitr::is_html_output()) return('')
  if(!nzchar(evidence_file)) return(unavailable('the evidence file was not supplied'))
  if(!file.exists(evidence_file)) return(unavailable(paste('evidence file is missing:', evidence_file)))
  record <- tryCatch(jsonlite::fromJSON(evidence_file, simplifyVector = FALSE),
                     error = function(e) NULL)
  if(is.null(record)) return(unavailable('evidence file is not valid JSON'))
  matches <- Filter(function(x) identical(x$instance_id, instance_id) &&
                      identical(x$component$type, 'series-collection'), record$blocks)
  if(!length(matches))
    return(unavailable(paste('no checked series-collection record for block instance', instance_id)))
  block <- matches[[1]]
  if(!identical(block$status, 'verified'))
    return(unavailable(paste0(if(is.null(block$code)) 'failed' else block$code, ': ',
                              if(is.null(block$detail)) '' else block$detail)))
  members <- block$members
  if(is.null(members) || !length(members))
    return(unavailable('the collection record carries no member series'))

  default_topic <- if(!is.null(block$presentation$default_topic))
    as.character(block$presentation$default_topic) else NULL
  measure <- as.character(block$measure)
  editorial <- identical(presentation_profile(b)$layout, 'editorial')
  count <- length(members)
  default_label <- NULL
  for(m in members) if(identical(as.character(m$selection$topic), default_topic))
    default_label <- label_topic(b, as.character(m$selection$topic))
  if(is.null(default_label))
    default_label <- label_topic(b, as.character(members[[1]]$selection$topic))
  ordering_text <- if(identical(as.character(block$ordering), 'author')) 'author order'
    else 'deterministic topic order'
  intro <- if(editorial)
    paste0('<p class="collection-intro">Reported ', esc(measure), ' for ', count,
           ' notifiable diseases. <strong>', esc(default_label),
           '</strong> is open first; open another disease to explore it. Each disease is shown on ',
           'its own, not compared against a shared scale.</p>')
  else
    paste0('<p class="collection-intro">Saved annual series for ', count,
           ' topics, one panel each bound through its own count metrics. Panels are independent: ',
           'values, units and gaps belong to the topic in that panel. A missing year is a gap, not zero.</p>')

  body <- character(0)
  for(member in members) {
    topic <- as.character(member$selection$topic)
    label <- label_topic(b, topic)
    open <- identical(topic, default_topic)
    missing <- if(length(member$missing_years)) paste(member$missing_years, collapse = ', ') else NULL
    meta <- paste0(esc(label), ' · ', esc(measure), ' · ', esc(series_panel_span(member)),
                   if(!is.null(missing)) paste0(' · no saved observation for ', esc(missing)) else '')
    body <- c(body, paste0(
      '<details class="series-panel" id="', esc(member$instance_id), '"',
      if(open) ' open' else '', '><summary>', meta, '</summary>',
      series_body_html(b, member, member$instance_id),
      '</details>'))
  }
  members_list <- paste(vapply(members, function(member) paste0(
    '<li><a href="#', esc(member$instance_id), '">', esc(label_topic(b, member$selection$topic)),
    '</a> · <code>', esc(member$instance_id), '</code> · instance ',
    esc(substr(as.character(member$identities$instance), 1, 16)), '</li>'), character(1)),
    collapse = '')
  inspect <- paste0('<details class="block-inspect" id="', esc(paste0(instance_id, '-inspect')),
    '"><summary>Inspect this collection</summary>',
    '<div class="audit-row"><span>Topics</span><strong>', count, ' (', esc(ordering_text), ')</strong></div>',
    '<div class="audit-row"><span>Measure</span><strong>', esc(measure), '</strong></div>',
    '<div class="audit-row"><span>Style</span><strong>', esc(block$presentation$style), '</strong></div>',
    '<div class="audit-row"><span>Default open topic</span><strong>', esc(default_topic), '</strong></div>',
    '<div class="audit-row"><span>Requested years</span><strong>',
    esc(paste(block$periods$requested, collapse = '–')), '</strong></div>',
    '<div class="audit-row"><span>Method</span><strong>Display of saved annual observations; no ',
    'source-count or scientific-result recalculation, no shared or normalised scale</strong></div>',
    '<div class="audit-row"><span>Collection identity</span><strong><code>',
    esc(block$identities$collection), '</code></strong></div>',
    '<h4>Members</h4><ul class="collection-members">', members_list, '</ul>',
    '<p><a href="data/series.csv" download>Download the saved series rows — CSV</a> · ',
    '<a href="data/metrics.csv" download>Download the bound count metrics — CSV</a></p>',
    '<p class="caption">Each member is a separately checked series record. Identities show that ',
    'these records agree with each other; they do not prove the numbers are correct. Opening a ',
    'panel performs no calculation.</p></details>')
  paste0(intro, paste(body, collapse = '\n'), inspect)
}

# --- Composites of saved records: coverage, monitoring, sensitivity (no calculation) ---
composed_record <- function(evidence_file, instance_id, type) {
  if(is.null(instance_id) || !nzchar(instance_id)) return(list(error = 'block instance id is missing'))
  if(!nzchar(evidence_file)) return(list(error = 'the evidence file was not supplied'))
  if(!file.exists(evidence_file)) return(list(error = paste('evidence file is missing:', evidence_file)))
  record <- tryCatch(jsonlite::fromJSON(evidence_file, simplifyVector = FALSE),
                     error = function(e) NULL)
  if(is.null(record)) return(list(error = 'evidence file is not valid JSON'))
  if(is.null(record$blocks) || !length(record$blocks)) return(list(error = 'evidence file carries no blocks'))
  matches <- Filter(function(x) identical(x$instance_id, instance_id) &&
                      identical(x$component$type, type), record$blocks)
  if(!length(matches)) return(list(error = paste('no checked', type, 'record for block instance', instance_id)))
  block <- matches[[1]]
  if(!identical(block$status, 'verified'))
    return(list(error = paste0(if(is.null(block$code)) 'failed' else block$code, ': ',
                               if(is.null(block$detail)) '' else block$detail)))
  list(block = block)
}

composite_unavailable <- function(title, reason) paste0(
  '<h3>', esc(title), ' unavailable</h3>',
  '<p class="caption">The saved record could not be used, so nothing is shown here.</p>',
  '<div class="audit-row"><span>Reason</span><strong>', esc(reason), '</strong></div>')

composite_inspector <- function(block, instance_id, extra = '') paste0(
  '<details class="block-inspect" id="', esc(paste0(instance_id, '-inspect')),
  '"><summary>Inspect this block</summary>',
  '<div class="audit-row"><span>Binding</span><strong>', esc(block$binding), '</strong></div>',
  '<div class="audit-row"><span>Snapshot</span><strong>',
  esc(block$snapshot$snapshot_id), '</strong></div>',
  extra,
  '<div class="audit-row"><span>Analytical identity</span><strong>',
  esc(block$identities$analytical), '</strong></div>',
  '<div class="audit-row"><span>Instance identity</span><strong>',
  esc(block$identities$instance), '</strong></div>',
  '<div class="audit-row"><span>Render code</span><strong>',
  esc(paste0(block$implementation$presentation$file, ' · ',
             substr(block$implementation$presentation$sha256, 1, 16))), '</strong></div>',
  '<div class="audit-row"><span>Binding code</span><strong>',
  esc(paste0(block$implementation$binding$file, ' · ',
             substr(block$implementation$binding$sha256, 1, 16))), '</strong></div>',
  '<div class="audit-row"><span>Contract code</span><strong>',
  esc(paste0(block$implementation$contracts$file, ' · ',
             substr(block$implementation$contracts$sha256, 1, 16))), '</strong></div>',
  '<div class="audit-row"><span>Entry point</span><strong><code>',
  gsub('--', '&#45;&#45;', esc(block$reproduction$entry_point), fixed = TRUE),
  '</code></strong></div>',
  '<p class="caption">Saved records only; opening this panel performs no source-count or scientific-result recalculation.</p></details>')

coverage_selection_block <- function(b, evidence_file = '', instance_id = NULL) {
  picked <- composed_record(evidence_file, instance_id, 'coverage-selection')
  if(!is.null(picked$error)) return(composite_unavailable('Report coverage', picked$error))
  block <- picked$block
  counts <- block$counts
  num <- function(x) if(is.null(x)) '0' else as.character(x)
  years <- if(is.null(block$requested$years)) 'not recorded' else paste(block$requested$years, collapse = '–')
  included <- if(is.null(block$requested$include_topics)) 'not set (historical default)' else paste(unlist(block$requested$include_topics), collapse = ', ')
  excluded_scope <- if(is.null(block$requested$exclude_topics)) 'none' else paste(unlist(block$requested$exclude_topics), collapse = ', ')
  displayed <- if(length(block$displayed_topics)) paste(unlist(block$displayed_topics), collapse = ', ') else 'none'
  groups <- block$displayed_groups
  scope <- read_provenance()$composition$display_scope
  monitored <- if(!is.null(scope)) unlist(scope$monitoring_topics) else character(0)
  group_lines <- if(length(groups)) paste(vapply(groups, function(g) paste0(
      '<li><strong>', esc(g$subject), '</strong> (', esc(g$specification), ') — members: ',
      esc(paste(unlist(g$members), collapse = ', ')), '</li>'), character(1)), collapse = '')
    else '<li>No group summary is bound by this recipe.</li>'
  excluded_dataset_rows <- if(length(block$excluded_datasets)) paste(vapply(
      block$excluded_datasets, function(item) paste0(
        '<tr><td><code>', esc(item$dataset_id), '</code></td><td>', esc(item$topic),
        '</td><td>', esc(item$reason), '</td></tr>'), character(1)), collapse = '')
    else '<tr><td colspan="3">No excluded dataset recorded.</td></tr>'
  excluded_rows <- if(length(block$excluded)) paste(vapply(block$excluded, function(item)
      paste0('<tr><td>', esc(item$topic), '</td><td>',
             esc(paste(unlist(item$reasons), collapse = '; ')), '</td></tr>'), character(1)),
      collapse = '') else '<tr><td colspan="2">No excluded topic recorded.</td></tr>'
  unsupported <- paste(vapply(block$unsupported, function(text) paste0('<li>', esc(text), '</li>'),
                              character(1)), collapse = '')
  bindings <- paste(vapply(block$bindings, function(item) paste0(
      '<div class="audit-row"><span>', esc(item$file), '</span><strong>',
      esc(substr(item$digest, 1, 16)), '</strong></div>'), character(1)), collapse = '')
  paste0('<p class="caption">This block reports what the saved selection records decided. ',
    'Datasets, topics and saved observations are counted separately, and “displayed topics” ',
    'lists only what this recipe actually binds.</p>',
    '<div class="table-scroll"><table class="report-table"><caption>Saved selection counts</caption>',
    '<thead><tr><th scope="col">Record</th><th scope="col">Count</th></tr></thead><tbody>',
    '<tr><td>Datasets recorded</td><td>', num(counts$datasets_total), '</td></tr>',
    '<tr><td>Datasets included</td><td>', num(counts$datasets_included), '</td></tr>',
    '<tr><td>Datasets excluded</td><td>', num(counts$datasets_excluded), '</td></tr>',
    '<tr><td>Topics included in the saved analysis</td><td>', num(counts$topics_included), '</td></tr>',
    '<tr><td>Topics contributing to group sums</td><td>', num(counts$topics_group_sum), '</td></tr>',
    '<tr><td>Topics with only excluded datasets</td><td>', num(counts$topics_excluded), '</td></tr>',
    '<tr><td>Saved annual observations, all years</td><td>', num(counts$observations_total), '</td></tr>',
    '<tr><td>Saved annual observations inside the reporting window</td><td>',
    num(counts$observations_in_window), '</td></tr>',
    '<tr><td>Source registry rows</td><td>', num(counts$source_registry_rows), '</td></tr>',
    '</tbody></table></div>',
    '<p class="table-note">Source registry rows are dataset/source entries in sources.csv, ',
    'not raw observation rows. Saved annual observations count series.csv rows: the total ',
    'includes years outside the reporting window (for example the 2019 comparison reference).</p>',
    '<p class="series-meta">Requested window ', esc(years), ' · included topics ',
    esc(included), ' · excluded topics ', esc(excluded_scope), '</p>',
    '<p><strong>Topics displayed individually by this report:</strong> ', esc(displayed), '.</p>',
    if(length(monitored)) paste0('<p><strong>Topics displayed in the monitoring table:</strong> ',
                                 esc(paste(label_topic(b, monitored), collapse = ', ')), '.</p>') else '',
    '<p><strong>Group summaries displayed:</strong></p><ul>', group_lines, '</ul>',
    '<details class="block-inspect" id="', esc(paste0(instance_id, '-excluded')),
    '"><summary>Excluded topics and recorded reasons</summary>',
    '<div class="table-scroll"><table class="report-table"><thead><tr><th scope="col">Topic</th>',
    '<th scope="col">Recorded reason</th></tr></thead><tbody>', excluded_rows,
    '</tbody></table></div></details>',
    '<details class="block-inspect" id="', esc(paste0(instance_id, '-excluded-datasets')),
    '"><summary>Excluded datasets and recorded reasons</summary>',
    '<div class="table-scroll"><table class="report-table"><thead><tr>',
    '<th scope="col">Dataset</th><th scope="col">Topic</th><th scope="col">Recorded reason</th>',
    '</tr></thead><tbody>', excluded_dataset_rows, '</tbody></table></div>',
    '<p class="table-note">Each row is a saved selection decision for one dataset/source.</p></details>',
    '<h3>Not available</h3><ul>', unsupported, '</ul>',
    composite_inspector(block, instance_id, bindings))
}

monitoring_overview_block <- function(b, evidence_file = '', instance_id = NULL) {
  picked <- composed_record(evidence_file, instance_id, 'monitoring-overview')
  if(!is.null(picked$error)) return(composite_unavailable('Monitoring overview', picked$error))
  block <- picked$block
  endpoint_rows <- paste(vapply(block$rows, function(item) paste0(vapply(item$comparisons, function(cmp) paste0(
      '<tr><td>', esc(label_topic(b, item$topic)), '</td><td>',
      esc(if(identical(cmp$type, 'reference_change')) 'Reference' else 'Period'), '</td><td>',
      esc(cmp$reference$year), '</td><td>', fmt_num(cmp$reference$value), ' ', esc(cmp$reference$unit),
      '</td><td>', esc(cmp$latest$year), '</td><td>', fmt_num(cmp$latest$value), ' ',
      esc(cmp$latest$unit), '</td><td>', fmt_pct(cmp$value), '</td><td>',
      esc(cmp$reference$metric_id), ', ', esc(cmp$latest$metric_id), ', ',
      esc(cmp$metric_id), '</td></tr>'), character(1)), collapse = ''),
      character(1)), collapse = '')
  row_html <- paste(vapply(block$rows, function(item) {
    comparison <- if(!length(item$comparisons)) 'No saved comparison' else paste(
      vapply(item$comparisons, function(cmp) paste0(
        if(identical(cmp$type, 'reference_change')) 'Reference ' else 'Period ',
        fmt_pct(cmp$value), ' (', cmp$from_year, '→', cmp$to_year, ')'), character(1)),
      collapse = '; ')
    paste0('<tr><td>', esc(label_topic(b, item$topic)), '</td><td>',
           esc(if(is.null(item$measure)) '—' else item$measure), '</td><td>',
           esc(if(is.null(item$latest_year)) '—' else item$latest_year), '</td><td>',
           esc(if(is.null(item$latest_value)) 'Not available' else fmt_num(item$latest_value)),
           '</td><td>', esc(comparison), '</td><td>',
           esc(if(is.null(item$availability)) '' else item$availability), '</td></tr>')
  }, character(1)), collapse = '')
  binding_rows <- paste(vapply(block$rows, function(item) paste0(
      '<tr><td>', esc(item$topic), '</td><td>',
      esc(if(is.null(item$latest_metric_id)) '—' else item$latest_metric_id), '</td><td>',
      esc(if(!length(item$comparisons)) '—' else paste(
        vapply(item$comparisons, function(cmp) cmp$metric_id, character(1)), collapse = ', ')),
      '</td></tr>'), character(1)), collapse = '')
  paste0('<p class="caption">One row per included topic, using its latest saved annual value ',
    'inside the reporting window. Units are named per row and are never put on a common scale.</p>',
    '<div class="table-scroll"><table class="report-table"><caption>Latest saved observation by topic</caption>',
    '<thead><tr><th scope="col">Topic</th><th scope="col">Measure</th><th scope="col">Year</th>',
    '<th scope="col">Value</th><th scope="col">Saved comparison</th><th scope="col">Availability</th>',
    '</tr></thead><tbody>', row_html, '</tbody></table></div>',
    '<p class="table-note">', esc(paste(unlist(block$limits), collapse = ' ')), '</p>',
    '<details class="block-inspect" id="', esc(paste0(instance_id, '-endpoints')),
    '"><summary>Comparison endpoints and bound metrics</summary>',
    '<div class="table-scroll"><table class="report-table"><thead><tr>',
    '<th scope="col">Topic</th><th scope="col">Comparison</th><th scope="col">Reference year</th>',
    '<th scope="col">Reference count</th><th scope="col">Latest year</th>',
    '<th scope="col">Latest count</th><th scope="col">Saved change</th>',
    '<th scope="col">Metric IDs</th></tr></thead><tbody>', endpoint_rows,
    '</tbody></table></div>',
    '<p class="table-note">Endpoint counts are read from the saved count metrics named in the ',
    'percentage result inputs; the saved percentage is displayed, never recalculated.</p></details>',
    '<details class="block-inspect" id="', esc(paste0(instance_id, '-bindings')),
    '"><summary>Row bindings</summary><div class="table-scroll"><table class="report-table">',
    '<thead><tr><th scope="col">Topic</th><th scope="col">Latest count metric</th>',
    '<th scope="col">Comparison metric</th></tr></thead><tbody>', binding_rows,
    '</tbody></table></div></details>',
    composite_inspector(block, instance_id))
}

sensitivity_comparison_block <- function(b, evidence_file = '', instance_id = NULL) {
  picked <- composed_record(evidence_file, instance_id, 'sensitivity-comparison')
  if(!is.null(picked$error)) return(composite_unavailable('Sensitivity comparison', picked$error))
  block <- picked$block
  pair_html <- paste(vapply(block$pairs, function(pair) {
    spec_rows <- paste(vapply(pair$specifications, function(spec) paste0(
      '<tr><td>', esc(spec$role), '</td><td>', esc(paste(unlist(spec$members), collapse = ', ')),
      '</td><td>', fmt_num(spec$reference$value), ' ', esc(spec$reference$unit),
      ' (', esc(spec$reference$year), ')</td><td>', fmt_num(spec$latest$value), ' ',
      esc(spec$latest$unit), ' (', esc(spec$latest$year), ')</td><td>',
      fmt_pct(spec$reference_change$value), '</td></tr>'), character(1)), collapse = '')
    evidence_rows <- paste(vapply(pair$specifications, function(spec) paste0(
      '<tr><td>', esc(spec$role), '</td><td>', esc(spec$reference$metric_id), ' (',
      esc(spec$reference$year), ')</td><td>', esc(spec$latest$metric_id), ' (',
      esc(spec$latest$year), ')</td><td>', esc(spec$reference_change$metric_id), '</td><td>',
      esc(paste(unlist(spec$reference_member_metric_ids), collapse = ', ')), '</td><td>',
      esc(paste(unlist(spec$latest_member_metric_ids), collapse = ', ')), '</td><td>',
      esc(paste0(spec$artifact$file, ' · ', substr(spec$artifact$digest, 1, 16))),
      '</td></tr>'), character(1)), collapse = '')
    identical_note <- if(isTRUE(pair$identical_members)) paste0(
      '<p class="table-note">The saved main and sensitivity specifications have the same members',
      if(isTRUE(pair$identical_results)) ' and identical saved results' else '', '.</p>') else ''
    excluded <- if(length(pair$excluded_members))
      paste(unlist(pair$excluded_members), collapse = ', ') else 'none recorded'
    added <- if(length(pair$added_members)) paste(unlist(pair$added_members), collapse = ', ') else 'none recorded'
    paste0('<h3>', esc(pair$class), ' group</h3>',
      '<div class="table-scroll"><table class="report-table"><caption>Saved main and sensitivity specifications</caption>',
      '<thead><tr><th scope="col">Specification</th><th scope="col">Members</th>',
      '<th scope="col">Total in reference year</th><th scope="col">Total in latest year</th>',
      '<th scope="col">Saved reference change</th></tr></thead><tbody>', spec_rows,
      '</tbody></table></div>',
      '<p class="series-meta">Members in main but not in sensitivity: ', esc(excluded),
      ' · members added by sensitivity: ', esc(added), '</p>', identical_note,
      '<details class="block-inspect" id="', esc(paste0(instance_id, '-', pair$class, '-bindings')),
      '"><summary>Metric bindings for the ', esc(pair$class), ' group</summary>',
      '<div class="table-scroll"><table class="report-table"><thead><tr>',
      '<th scope="col">Specification</th><th scope="col">Reference total metric</th>',
      '<th scope="col">Latest total metric</th><th scope="col">Change metric</th>',
      '<th scope="col">Reference-year member metrics</th>',
      '<th scope="col">Latest-year member metrics</th><th scope="col">Artifact</th></tr></thead><tbody>',
      evidence_rows, '</tbody></table></div>',
      '<p class="table-note">Metric identifiers resolve in metrics.csv; matching digests show the ',
      'files agree with the manifest, not that the saved results are scientifically correct.</p></details>')
  }, character(1)), collapse = '')
  paste0('<p class="caption">', esc(block$question), ' Both specifications are read from saved ',
    'metrics; no count is recalculated here.</p>', pair_html,
    '<p class="table-note">', esc(paste(unlist(block$limits), collapse = ' ')), '</p>',
    composite_inspector(block, instance_id))
}

composition_registry <- list(
  intro = list(label = composition_labels[['intro']], primary = FALSE,
    render = function(b, entry, evidence_file='') selection_intro(b)),
  'series-trend' = list(label = composition_labels[['series-trend']], primary = FALSE,
    render = function(b, entry, evidence_file='')
      series_trend_block(b, evidence_file, instance_id=entry$instance_id)),
  'series-collection' = list(label = composition_labels[['series-collection']], primary = FALSE,
    render = function(b, entry, evidence_file='')
      series_collection_block(b, evidence_file, instance_id=entry$instance_id)),
  'coverage-selection' = list(label = composition_labels[['coverage-selection']], primary = FALSE,
    render = function(b, entry, evidence_file='')
      coverage_selection_block(b, evidence_file, instance_id=entry$instance_id)),
  'monitoring-overview' = list(label = composition_labels[['monitoring-overview']], primary = FALSE,
    render = function(b, entry, evidence_file='')
      monitoring_overview_block(b, evidence_file, instance_id=entry$instance_id)),
  'sensitivity-comparison' = list(label = composition_labels[['sensitivity-comparison']], primary = FALSE,
    render = function(b, entry, evidence_file='')
      sensitivity_comparison_block(b, evidence_file, instance_id=entry$instance_id)),
  'reference-comparison' = list(label = composition_labels[['reference-comparison']], primary = TRUE,
    render = function(b, entry, evidence_file='')
      reference_block(b, evidence_file, variant='composed', instance_id=entry$instance_id)),
  limitations = list(label = composition_labels[['limitations']], primary = FALSE,
    render = function(b, entry, evidence_file='') composed_limitations(b)),
  reproduction = list(label = composition_labels[['reproduction']], primary = FALSE,
    render = function(b, entry, evidence_file='')
      paste0(code_disclosure(annual_reproduction_code()),
             '<h3>How this report was produced</h3>',
             provenance_summary(b, raw_links=FALSE),
             '<h3>Exact records and methods</h3>',
             '<p>Exact audience parameters, the bundle manifest, metrics, calculation lineage and the other published files ',
             'are listed with sizes, digests and direct downloads in ',
             '<a href="#report-settings">Report settings and source files</a>.</p>',
             composed_settings_html(b),
             '<p class="composed-note">PDF export of this composed report is not yet available.</p>'))
)

composition_style <- function() paste0('<style>',
  '.composed-report{max-width:980px;margin:0 auto;padding:28px 20px 40px;background:#fff}',
  '.composed-intro{color:#52656b;margin:4px 0 18px;font-size:17px}',
  '.composed-nav{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 26px}',
  '.composed-nav a{font-size:14px;color:#247c85;text-decoration:none}',
  '.composed-block{border:1px solid #dfe6e5;border-radius:14px;padding:22px 24px;margin:0 0 20px;background:#fff}',
  '.composed-block--primary{border:2px solid #247c85}',
  '.composed-report .series-figure{margin:14px 0 8px;width:100%;max-width:680px}',
  '.composed-report .series-figure--compact{margin:10px 0 6px}',
  '.composed-report .series-figure img{display:block;width:100%;max-width:100%;height:auto}',
  '.composed-report .series-panel{border:1px solid #e3eae9;border-radius:10px;margin:10px 0;padding:0 14px 6px}',
  '.composed-report .series-panel>summary{cursor:pointer;padding:12px 2px;font-weight:600;color:#18343c;overflow-wrap:anywhere}',
  '.composed-report .series-panel[open]>summary{border-bottom:1px solid #e3eae9;margin-bottom:10px}',
  '.composed-report summary:focus-visible{outline:3px solid #b95d35;outline-offset:4px}',
  '.composed-report .collection-intro{margin:6px 0 12px}',
  '.composed-report .collection-members{margin:8px 0 12px;padding-left:20px}',
  '.composed-report .collection-members code{overflow-wrap:anywhere}',
  '@media (max-width:480px){.composed-report .series-panel{padding:0 8px 4px}}',
  '.composed-report .table-scroll{overflow-x:auto;max-width:100%}',
  '.composed-report .report-table{max-width:100%}',
  '@media (max-width:480px){.composed-report{padding:20px 12px 28px}.composed-report .finding-counts{gap:18px;flex-wrap:wrap}}',
  '.composed-report .provenance-list dd code,.composed-report .report-settings td code,.composed-report .audit-row strong,.composed-report .audit-row code{min-width:0;overflow-wrap:anywhere;white-space:normal}',
  '.composed-kicker{margin:0 0 4px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#52656b}',
  '.composed-heading{margin:0 0 12px;font-size:21px;color:#18343c}',
  '.finding-value{margin:6px 0 2px;font-size:44px;line-height:1;font-weight:700;color:#247c85}',
  '.finding-meta{margin:6px 0 0;color:#52656b}',
  '.finding-counts{display:flex;gap:34px;margin:16px 0 4px}',
  '.finding-counts span{display:block;font-size:12px;color:#52656b}',
  '.finding-counts strong{font-size:20px;color:#18343c}',
  '.finding-caution{margin:14px 0 0;color:#52656b;font-size:14px}',
  '.block-inspect{margin-top:16px;border-top:1px dashed #dfe6e5;padding-top:10px}',
  '.block-inspect summary{cursor:pointer;color:#247c85;font-weight:600}',
  '</style>')

compose_report_html <- function(b, recipe_path, evidence_file='', registry=composition_registry) {
  if(!nzchar(recipe_path) || !file.exists(recipe_path))
    stop('Composition recipe is missing: ', recipe_path)
  recipe <- tryCatch(jsonlite::fromJSON(recipe_path, simplifyVector=FALSE),
                     error=function(e) stop('Composition recipe is not valid JSON: ', conditionMessage(e)))
  if(!recipe$contract %in% c('health-report/composition-recipe/1','health-report/composition-recipe/2'))
    stop('Unsupported composition contract: ', paste(recipe$contract, collapse=''))
  blocks <- recipe$blocks
  if(!is.list(blocks) || !length(blocks)) stop('Composition recipe needs a non-empty blocks list')
  ids <- vapply(blocks, function(x) x$block, character(1))
  inst <- vapply(blocks, function(x) x$instance_id, character(1))
  unknown <- setdiff(ids, names(registry))
  if(length(unknown)) stop('Unknown block type(s): ', paste(unknown, collapse=', '))
  if(any(!grepl('^[a-z0-9][a-z0-9_-]{2,39}$', inst)))
    stop('Invalid block instance id: ', paste(inst[!grepl('^[a-z0-9][a-z0-9_-]{2,39}$', inst)], collapse=', '))
  if(anyDuplicated(inst))
    stop('Duplicate block instance id: ', paste(unique(inst[duplicated(inst)]), collapse=', '))
  # One checked contract record backs one instance; repetition is refused rather than
  # reusing a record under a second identity.
  if(sum(ids == 'reference-comparison') > 1L)
    stop('Repeated reference-comparison blocks are not supported yet')
  sections <- list()
  for(i in seq_along(ids)) {
    entry <- blocks[[i]]
    spec <- registry[[entry$block]]
    if(!is.list(spec) || !is.function(spec$render) || is.null(spec$label))
      stop('Invalid renderer metadata for block: ', entry$block)
    body <- spec$render(b, entry, evidence_file=evidence_file)
    if(!is.character(body) || !nzchar(body)) stop('Block rendered nothing: ', entry$block)
    primary <- isTRUE(spec$primary)
    sections[[length(sections)+1L]] <- list(id=entry$instance_id, label=spec$label, html=paste0(
      '<section class="composed-block', if(primary) ' composed-block--primary' else '',
      '" id="', esc(entry$instance_id), '"><p class="composed-kicker">', if(primary) 'Primary finding' else 'Supporting block',
      '</p><h2 class="composed-heading">', esc(spec$label), '</h2>', body, '</section>'))
  }
  nav <- paste0('<nav class="composed-nav" aria-label="Report blocks">',
    paste(vapply(sections, function(s) paste0('<a href="#', esc(s$id), '">', esc(s$label), '</a>'),
                 character(1)), collapse=''), '</nav>')
  pr_title <- read_provenance()
  report_title <- if(!is.null(pr_title$composition) && !is.null(pr_title$composition$effective_title))
    pr_title$composition$effective_title else b$cfg$title
  report_subtitle <- if(!is.null(pr_title$composition) && !is.null(pr_title$composition$effective_subtitle))
    pr_title$composition$effective_subtitle else NULL
  paste0('<div class="composed-report">', composition_style(),
    '<p class="composed-intro">', esc(report_title), ' · ', esc(paste(b$cfg$years, collapse='–')),
    ' · reference year ', esc(b$cfg$reference_year), '</p>',
    if(!is.null(report_subtitle)) paste0('<p class="composed-intro composed-subtitle">',
                                        esc(report_subtitle), '</p>') else '', nav,
    paste(vapply(sections, function(s) s$html, character(1)), collapse='\n'),
    '<p class="caption">Composed from saved analysis outputs. The companion ',
    '<a href="methods.html">methods report</a> retains the full selection, lineage and verification detail.</p></div>')
}
