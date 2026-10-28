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
format_pct <- function(x,digits=0) ifelse(is.na(x),'Not available',sprintf(paste0('%+.',digits,'f%%'),x))
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
report_metadata <- function(b) paste0('<div class="report-meta"><span>',length(group_topics(b)),' diseases in the group comparison</span><span>National case notifications</span><span class="snapshot">Snapshot ',substr(b$manifest$snapshot_id,1,16),'</span></div>')
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
  if(is.null(record$blocks) || !length(record$blocks)) return(unavailable('evidence file carries no reference-comparison block'))
  if(!is.null(instance_id) && nzchar(instance_id)) {
    matches <- Filter(function(x) identical(x$instance_id,instance_id),record$blocks)
    if(!length(matches)) return(unavailable(paste('no checked record for block instance',instance_id)))
    block <- matches[[1]]
  } else block <- record$blocks[[1]]
  row <- function(k,v) paste0('<div class="audit-row"><span>',esc(k),'</span><strong>',esc(v),'</strong></div>')
  if(!identical(block$status,'verified')) {
    return(panel(paste0('<h2>Reference comparison unavailable</h2>',
      '<p class="caption">The saved block did not pass its contract checks, so no values are shown.</p>',
      row('Reason',paste0(block$code,': ',block$detail)))))
  }
  fmt <- function(x) format(as.numeric(x),big.mark=',',scientific=FALSE,trim=TRUE)
  pct <- if(identical(block$result$availability,'available')) sprintf('%+.1f%%',as.numeric(block$result$value)) else 'Not available'
  trace <- paste(vapply(block$trace,function(t) paste0(t$field,' = ',t$value,' (',t$source,')'),character(1)),collapse='; ')
  if(composed) {
    return(paste0('<div class="finding">',
      '<p class="finding-value">',esc(pct),'</p>',
      '<p class="finding-meta">',esc(label_topic(b,block$subject)),' · reported cases in ',esc(block$latest_year),
      ' compared with ',esc(block$reference_year),' · measure ',esc(block$measure),'</p>',
      '<div class="finding-counts"><div><span>',esc(block$reference_year),'</span><strong>',fmt(block$reference_count$value),'</strong></div>',
      '<div><span>',esc(block$latest_year),'</span><strong>',fmt(block$latest_count$value),'</strong></div></div>',
      '<div class="audience-explanation"><p>',composition_copy_for(b)$reference(b,block,pct,fmt),'</p></div>',
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
      row('Instance identity',block$identities$instance), row('Entry point',block$reproduction$entry_point),
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
    row('Entry point',block$reproduction$entry_point),
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
methods_html <- function(b,navigation=TRUE,prefix='data/',pdf=TRUE) {
    y <- report_year(b)
  ref <- b$cfg$reference_year
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
  parts<-c(parts,paste0('<div class="chart-note">Excluded from group sums: ',esc(paste(label_topic(b,b$cfg$exclude_from_group_totals),collapse=', ')),'. Sentinel estimates are not pooled with mandatory case notifications.</div></section><section class="audit-panel" id="calculations"><h2>Trace a finding, not a code</h2><h3>',esc(trace_label),': ',format_pct(metric_value(b,paste0(trace_subject,':reference_change')),1),' versus ',ref,'</h3>'),row(paste('Selected cases in',y),fmt(z)),row(paste('Selected cases in',ref),fmt(a)),row('Calculation',paste0('(',fmt(z),' − ',fmt(a),') ÷ ',fmt(a),' × 100')),'<p class="caption">The lineage export links these totals to each disease, then to its original source records. It includes the population denominator for calculated rates.</p></section></div>')
  if(show_section(b,'excluded'))parts<-c(parts,paste0('<section class="audit-panel full"><h2>Dataset selection</h2>',html_table(selected),'<div class="table-note">Source: the saved selection table. “Included” means eligible for disease-level analysis; “In main group” additionally applies the configured source and disease exclusions.</div></section>'))
  if(show_section(b,'quality'))parts<-c(parts,quality_methods_html(b))
  if(show_section(b,'sources'))parts<-c(parts,paste0('<section class="audit-panel full"><h2>Sources and audit files</h2>',html_table(sources),'<div class="table-note">Source: the dataset registry and original export descriptions. Dates are publisher release dates. Full paths, data and metadata fingerprints are retained in the downloadable source registry.</div><div class="download-links">',paste(vapply(c('sources.csv','selection.csv','lineage.csv','metrics.csv','checks.csv','snapshot.json'),function(n)paste0('<a download href="',prefix,n,'">',esc(n),'</a>'),character(1)),collapse=''),'</div><details><summary>Technical identifiers and exact snapshot</summary><p class="snapshot">',esc(b$manifest$snapshot_id),'</p><p>Full metric identifiers are in metrics.csv. The findings report uses human-readable names instead of printed M-codes. CSV record numbers count the header as record 1; multiline CSV fields may span several text lines.</p></details></section>'))
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
  topics <- group_topics(b)
  paste0(
    '<section class="selection-intro"><p class="audience-label">',
    esc(p$display_name), ' · ', esc(p$layout), ' presentation</p>',
    '<p><strong>Selected diseases:</strong> ',
    esc(paste(label_topic(b, topics), collapse=', ')), '.</p>',
    '<p>These are recorded notifications, not all infections. ',
    'Changes may reflect surveillance and testing as well as disease occurrence. ',
    'The figures are descriptive; they do not establish causes or statistical significance.</p>',
    '</section>'
  )
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
composition_labels <- c(intro = 'Context', 'reference-comparison' = 'Reference comparison',
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
      'Monitoring question: ', esc(b$cfg$question), ' Observed change: ', esc(pct),
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
    ' A check-result row is one recorded result from the saved validation output; aggregation rules such as ',
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

composition_registry <- list(
  intro = list(label = composition_labels[['intro']], primary = FALSE,
    render = function(b, entry, evidence_file='') selection_intro(b)),
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
  if(!identical(recipe$contract, 'health-report/composition-recipe/1'))
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
  paste0('<div class="composed-report">', composition_style(),
    '<p class="composed-intro">', esc(b$cfg$title), ' · ', esc(paste(b$cfg$years, collapse='–')),
    ' · reference year ', esc(b$cfg$reference_year), '</p>', nav,
    paste(vapply(sections, function(s) s$html, character(1)), collapse='\n'),
    '<p class="caption">Composed from saved analysis outputs. The companion ',
    '<a href="methods.html">methods report</a> retains the full selection, lineage and verification detail.</p></div>')
}
