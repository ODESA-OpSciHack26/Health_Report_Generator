"""Package and render verified analysis bundles without recalculating statistics."""
import argparse
import csv
import hashlib
import math
import os
import json
import shutil
import subprocess
import tempfile
import platform
import re
import importlib.metadata
from datetime import datetime, timezone
from pathlib import Path
from common import digest, write_json
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
TEMPLATE='report_shared.qmd'
PROVENANCE_SCHEMA='health-report-provenance/1.0'
FILTER_KEYS=['period_type','years','reference_year','index_base_year','geography','measures_preferred','compare_by',
             'classes_in_main_comparison','exclude_from_group_totals','sensitivity_exclude','source_priority',
             'group_source_systems','dimension_filters','needs_roles','include_topics','exclude_topics']

def verify_bundle(bundle):
    bundle=Path(bundle); m=json.loads((bundle/'bundle.json').read_text())
    for n,h in m['files'].items():
        if digest(bundle/n)!=h: raise ValueError(f'Bundle integrity failed: {n}')
    return m

def package(bundle,dest):
    bundle,dest=Path(bundle),Path(dest); m=verify_bundle(bundle)
    dest.mkdir(parents=True,exist_ok=True)
    for n in [*m['files'],'bundle.json']:
        shutil.copyfile(bundle/n,dest/n)
    shutil.copyfile(HERE/TEMPLATE,dest/'report.qmd')
    for n in ['report_helpers.R','audience_reports.R','tabular_report.R','tabular_charts.R','app.R','dashboard.css','methods.qmd']:
        shutil.copyfile(HERE/'templates'/n,dest/n)
    write_json(dest/'package.json',{'schema_version':'2.0','files':{p.name:digest(p) for p in sorted(dest.iterdir()) if p.is_file() and p.name!='package.json'}})

# Evidence published beside the report. The shared template links these as data/<name>,
# so the published folder must contain an exact copy or the link is dead.
# (artifact id, bundle file name, reader-facing label, required)
EVIDENCE_ARTIFACTS=(
    ('audience-parameters','stakeholder.json','Exact audience parameters (JSON)',True),
    ('bundle-manifest','bundle.json','Artifact manifest (JSON)',True),
    ('metrics','metrics.csv','Metrics table (CSV)',True),
    ('lineage','lineage.csv','Calculation lineage (CSV)',True),
    ('checks','checks.csv','Validation check records (CSV)',True),
    ('series','series.csv','Plotted series (CSV)',True),
    ('selection','selection.csv','Dataset selection (CSV)',True),
    ('sources','sources.csv','Source registry (CSV)',True),
    ('snapshot','snapshot.json','Snapshot record (JSON)',True),
    ('pathogen-class','pathogen_class.csv','Pathogen classes (CSV)',True),
)

def publish_evidence(bundle,dest):
    """Copy the analysis bundle byte-for-byte into <report>/data and verify digests.

    Every file named by bundle.json is published, plus bundle.json itself. Files are
    copied as saved, never rebuilt. bundle.json carries digests for the other files but is
    not self-digested.
    """
    bundle,dest=Path(bundle),Path(dest); manifest=verify_bundle(bundle)
    dest.mkdir(parents=True,exist_ok=True)
    labels={name:label for _,name,label,_ in EVIDENCE_ARTIFACTS}
    published={}
    for name in sorted(manifest['files'])+['bundle.json']:
        source=bundle/name
        if not source.is_file():
            raise ValueError(f'Bundle file named by the manifest is missing: {name}')
        expected=manifest['files'].get(name)
        if expected is not None and digest(source)!=expected:
            raise ValueError(f'Evidence artifact digest mismatch: {name}')
        target=dest/name
        if not (target.is_file() and digest(target)==digest(source)):
            shutil.copyfile(source,target)
        published[name]={'path':f'data/{name}','sha256':digest(target),'expected':expected,
                         'label':labels.get(name,name)}
    return published

LOCAL_EVIDENCE_LINK=re.compile(r'(?:href|src)="(?!https?:|#|mailto:|data:)([^"]+)"')

def validate_published_evidence(report_dir):
    """Check the final published folder, not the temporary render workspace.

    Both report.html and methods.html are checked for evidence targets: data/ downloads
    plus the co-located methods/provenance documents. The legacy PDF link is out of scope.
    """
    report_dir=Path(report_dir)
    if not (report_dir/'report.html').is_file():
        raise ValueError(f'Published report is missing: {report_dir/"report.html"}')
    missing=[]
    for document in ('report.html','methods.html'):
        html=report_dir/document
        if not html.is_file(): continue
        for target in sorted(set(LOCAL_EVIDENCE_LINK.findall(html.read_text(encoding='utf-8',errors='replace')))):
            if '{' in target or '}' in target: continue  # JavaScript template literal, not a link
            path=target.split('#',1)[0].split('?',1)[0]
            if not path: continue
            if not path.startswith('data/') and path not in ('provenance.json','methods.html','report.html'): continue
            if not (report_dir/path).is_file(): missing.append(f'{document}:{path}')
    if missing: raise ValueError(f'Published report has unresolved local evidence links: {sorted(set(missing))}')
    return True

def _command(args):
    try: return subprocess.check_output(args,stderr=subprocess.STDOUT,text=True,cwd=PROJECT).strip()
    except (OSError,subprocess.CalledProcessError): return None

def _version(name):
    try: return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: return None

def _retrieval(path):
    try: return json.loads(Path(path).read_text())
    except (OSError,ValueError): return None

# Source *availability* is a property of the package, not of the recorded Git state: a clean
# commit identifies a revision but does not give a reader the source checkout or the image.
SOURCE_STATE_AVAILABILITY=('This package contains neither the source checkout nor the container image; '
                          'both must be supplied separately before either can be inspected.')

def source_state_record(code):
    """Reader-facing source-state wording from the recorded Git state only.

    Three states are possible: clean committed source, source with uncommitted changes, and
    unknown. Cleanliness is never inferred from a commit hash, and an unreadable or missing Git
    state is "unknown", never "clean". Availability is reported separately, so a clean commit is
    never presented as proof that a reader has the source.
    """
    code=code if isinstance(code,dict) else {}
    commit=code.get('git_commit'); clean=code.get('git_worktree_clean')
    short=commit[:12] if isinstance(commit,str) and commit else None
    if clean is True and short:
        state,label='clean','clean worktree at the recorded commit'
        detail=(f'Source state recorded at render time: clean worktree at commit {short}. '
                'A clean commit identifies the source revision; it does not by itself provide the source.')
    elif clean is False:
        state,label='uncommitted','uncommitted changes present'
        detail=(f'Source state recorded at render time: commit {short or "not recorded"} with uncommitted '
                'changes present. The Git SHA alone does not identify the full working-tree source.')
    else:
        state,label='unknown','source state not determined'
        detail=('Source state recorded at render time: not determined, because the Git state could not be '
                'read. Source identity is therefore unverified; this is not evidence of a clean tree.')
    return {'state':state,'commit':commit,'label':label,'detail':detail,
            'availability':SOURCE_STATE_AVAILABILITY}

def reproduction_source_state(provenance):
    """The recorded source state used by the published reproduction record.

    Reuses the provenance record rather than re-deriving: without one, the state is recorded as
    not determined instead of being guessed.
    """
    code=(provenance or {}).get('code') if isinstance(provenance,dict) else None
    recorded=(code or {}).get('source_state') if isinstance(code,dict) else None
    return recorded or source_state_record(code or {})

def build_provenance(bundle,fmt,quarto='quarto',data_root=None,workflow_config=None,extra=None):
    """Machine-readable record of what was rendered, from which data, with which parameters."""
    bundle=Path(bundle); m=verify_bundle(bundle)
    cfg=json.loads((bundle/'stakeholder.json').read_text())
    snapshot=json.loads((bundle/'snapshot.json').read_text())
    import pandas as pd
    sources=pd.read_csv(bundle/'sources.csv',dtype=str).fillna('')
    used=sources[sources.used.str.lower().eq('true')]
    roots=[Path(data_root)] if data_root else []
    archive=(bundle.parents[2]/snapshot['snapshot_path']) if snapshot.get('snapshot_path') else None
    if archive is not None: roots.append(archive)
    datasets=[]
    for r in used.sort_values('source_file').itertuples():
        directory=Path(r.source_file).parent
        ret=next((x for x in (_retrieval(root/directory/'retrieval.json') for root in roots) if x),None) or {}
        datasets.append({'dataset_id':r.dataset_id,'export':directory.as_posix(),'topic':r.topic,'source_system':r.source_system,
                         'publishing_date':r.publishing_date or None,'retrieved_at_utc':ret.get('retrieved_at_utc'),
                         'csv_source_url':ret.get('csv_source_url'),'metadata_source_url':ret.get('metadata_source_url'),
                         'data_sha256':r.sha256,'metadata_sha256':r.metadata_sha256})
    dates=lambda k:sorted(d[k] for d in datasets if d[k])
    checks=pd.read_csv(bundle/'checks.csv',dtype=str).fillna('')
    toolchain=PROJECT/'workflow/toolchain.json'
    git_commit=_command(['git','rev-parse','HEAD'])
    git_status=_command(['git','status','--porcelain','--untracked-files=no'])
    code={'git_commit':git_commit,'git_worktree_clean':None if git_status is None else git_status=='',
          'workflow_config':workflow_config}
    # One derived, reader-facing record; every output reads this instead of restating the state.
    code['source_state']=source_state_record(code)
    record={
        'schema':PROVENANCE_SCHEMA,
        'rendered_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'output':{'format':fmt,'documents':[f'report.{fmt}',f'methods.{fmt}'],
                  'shared_template':f'scripts/health_pipeline/{TEMPLATE}','shared_template_sha256':digest(HERE/TEMPLATE),
                  'presentation_helpers_sha256':{n:digest(HERE/'templates'/n) for n in ['report_helpers.R','audience_reports.R','tabular_report.R','tabular_charts.R','methods.qmd','dashboard.css']}},
        'stakeholder':{'id':cfg['id'],'title':cfg['title'],'question':cfg['question'],'presentation':cfg.get('presentation'),
                       'outputs':cfg['outputs'],'parameters_sha256':digest(bundle/'stakeholder.json')},
        'filters':{k:cfg[k] for k in FILTER_KEYS if k in cfg},
        'effective_parameters':cfg,
        'data':{'publisher':'Federal Office of Public Health (FOPH/BAG), Infectious Disease Dashboard (IDD)',
                'api':'https://api.idd.bag.admin.ch/api/v1/export/latest/{dataset}/csv',
                'canonical_root':Path(data_root).as_posix() if data_root and not str(data_root).endswith('.json') else None,
                'snapshot_manifest':Path(data_root).as_posix() if data_root and str(data_root).endswith('.json') else None,
                'snapshot_id':m['snapshot_id'],'snapshot_path':snapshot.get('snapshot_path'),
                'datasets_in_snapshot':len(sources),'datasets_used':len(datasets),
                'publishing_date_range':[dates('publishing_date')[0],dates('publishing_date')[-1]] if dates('publishing_date') else None,
                'retrieved_at_utc_range':[dates('retrieved_at_utc')[0],dates('retrieved_at_utc')[-1]] if dates('retrieved_at_utc') else None,
                'used':datasets},
        'analysis_bundle':{'schema_version':m['schema_version'],'files':m['files']},
        'quality_checks':checks.status.value_counts().sort_index().to_dict(),
        'software':{'python':platform.python_version(),'platform':platform.platform(),
                    'python_packages':{n:_version(n) for n in ['pandas','numpy','pyarrow','jsonschema','snakemake']},
                    'quarto':_command([quarto,'--version']),'R':(_command(['Rscript','--version']) or '').splitlines()[-1:] or None,
                    'toolchain_contract':'workflow/toolchain.json','toolchain_contract_sha256':digest(toolchain) if toolchain.is_file() else None,
                    'r_lockfile_sha256':digest(PROJECT/'renv.lock') if (PROJECT/'renv.lock').is_file() else None,
                    'python_lockfile_sha256':digest(HERE/'requirements.lock.txt')},
        'code':code,
    }
    if record['software']['R']: record['software']['R']=record['software']['R'][0]
    if extra: record['request']=extra
    return record

def _csv_rows(path):
    with Path(path).open('r',encoding='utf-8',newline='') as handle:
        return list(csv.DictReader(handle))

def _select_block_subject(bundle):
    """Deterministic subject rule shared with the retained-bundle compatibility check."""
    metrics=_csv_rows(bundle/'metrics.csv'); selection=_csv_rows(bundle/'selection.csv')
    cfg=json.loads((bundle/'stakeholder.json').read_text())
    excluded=set(cfg.get('exclude_from_group_totals') or [])
    by_metric={row.get('metric_id'):row for row in metrics if row.get('metric_id')}
    choices=[]
    for metric_id,row in by_metric.items():
        subject=row.get('subject') or ''
        if row.get('metric_type')!='reference_change' or ':' in subject or subject in excluded: continue
        try: value=float(row.get('value') or '')
        except ValueError: continue
        inputs=json.loads(row.get('inputs_json') or '[]')
        if len(inputs)!=2 or any(i not in by_metric for i in inputs): continue
        if not any(s.get('topic')==subject and s.get('status')=='included' for s in selection): continue
        choices.append((subject,metric_id,inputs[0],inputs[1],value))
    choices.sort(key=lambda item:item[0])
    return choices[0] if choices else None

def _select_topic_subject(bundle,topic):
    """Resolve one explicitly requested topic from saved bundle records only.

    No fallback to another topic: missing, excluded or ambiguous saved records raise a
    contract error with the recorded selection reasons.
    """
    import composer_contracts as contracts
    metrics=_csv_rows(bundle/'metrics.csv'); selection=_csv_rows(bundle/'selection.csv')
    included=[s for s in selection if s.get('topic')==topic and s.get('status')=='included']
    if not included:
        reasons=sorted({s.get('reason') or '' for s in selection if s.get('topic')==topic and s.get('reason')})
        detail='; '.join(reasons) if reasons else 'no input dataset in this snapshot'
        raise contracts.ContractError('selection', f'topic {topic!r} is not included in this saved bundle: {detail}')
    matches=[r for r in metrics if r.get('metric_type')=='reference_change' and r.get('subject')==topic]
    if not matches:
        raise contracts.ContractError('selection', f'topic {topic!r} has no saved reference_change result')
    if len(matches)>1:
        raise contracts.ContractError('selection', f'topic {topic!r} has {len(matches)} saved reference_change results')
    result=matches[0]; result_id=result['metric_id']
    by_metric={row.get('metric_id'):row for row in metrics if row.get('metric_id')}
    try: inputs=json.loads(result.get('inputs_json') or '[]')
    except ValueError: raise contracts.ContractError('bindings', f'{result_id} has unparsable inputs')
    if len(inputs)!=2 or any(i not in by_metric for i in inputs):
        raise contracts.ContractError('bindings', f'{result_id} does not bind two saved count metrics')
    for mid in inputs:
        row=by_metric[mid]
        if row.get('metric_type')!='count' or row.get('subject')!=topic:
            raise contracts.ContractError('bindings', f'{result_id} input {mid} is not a {topic} count')
    reference_id,latest_id=inputs
    try: value=float(result.get('value') or '')
    except ValueError: raise contracts.ContractError('results', f'{result_id} has no saved numeric value')
    return topic,result_id,reference_id,latest_id,value

def build_block(bundle,results_root,project_root,instance_id='block-reference-comparison',topic=None):
    """Resolve one reference-comparison block from saved bundle records only.

    No percentage is recalculated: the saved metric value, count bindings and lineage
    strings are carried through. A contract failure returns an explicit failed record
    instead of a plausible-looking block. An explicit topic never falls back to another
    topic.
    """
    import composer_contracts as contracts
    bundle=Path(bundle); results_root=Path(results_root)
    try:
        selected=_select_topic_subject(bundle,topic) if topic is not None else _select_block_subject(bundle)
        if selected is None:
            raise contracts.ContractError('selection','no eligible disease-level reference_change metric')
        subject,result_id,reference_id,latest_id,value=selected
        loaded=contracts.load_bundle(bundle)
        scope=contracts.scope_of(loaded.stakeholder)
        parameters={'reference_year':scope['reference_year'],'latest_year':scope['years'][1],
                    'measure':loaded.metrics[reference_id]['unit']}
        instance={'contract':contracts.INSTANCE_CONTRACT,'instance_id':instance_id,
            'component':{'type':'reference-comparison','version':'1'},
            'analysis':{'snapshot_id':loaded.snapshot['snapshot_id'],'scope':scope},
            'bindings':{'reference_count':reference_id,'latest_count':latest_id,'result':result_id},
            'plotted':{'file':contracts.PLOTTED_ARTIFACT,
                       'rows':[{'topic':subject,'year':parameters['reference_year']},
                               {'topic':subject,'year':parameters['latest_year']}],
                       'digest':loaded.manifest['files'][contracts.PLOTTED_ARTIFACT]},
            'presentation':{'unit':'percent','digits':1},'disclosure':{'distribution':'public'}}
        evidence={'contract':contracts.EVIDENCE_CONTRACT,'instance_id':instance_id,
            'inputs':{'metric_ids':[reference_id,latest_id]},
            'calculation':{'method_id':'percent_reference_change','method_version':'1',
                           'formula':'percent_change','parameters':parameters},
            'results':{'metric_id':result_id,'value':value,'unit':'percent',
                       'availability':'available','unavailable_reason':None},
            'implementation':{
                'analysis':{'file':'scripts/health_pipeline/analyse.py',
                            'sha256':digest(PROJECT/'scripts/health_pipeline/analyse.py')},
                'presentation':{'file':'scripts/health_pipeline/templates/report_helpers.R',
                                'sha256':digest(PROJECT/'scripts/health_pipeline/templates/report_helpers.R')},
                'contracts':_code_reference('scripts/health_pipeline/composer_contracts.py'),
                'binding':_code_reference('scripts/health_pipeline/publish.py'),
                'schema':_code_reference('scripts/health_pipeline/config/composer/component-contract/1.json')},
            'reproduction':{'entry_point':'snakemake --cores 2',
                            'snapshot_id':loaded.snapshot['snapshot_id']}}
        checked=contracts.check_block(instance,evidence,loaded,
                                      project_root=project_root,results_root=results_root)
    except contracts.ContractError as exc:
        return {'status':'failed','instance_id':instance_id,
                'component':{'type':'reference-comparison','version':'1'},
                'contract':{'instance':contracts.INSTANCE_CONTRACT,'evidence':contracts.EVIDENCE_CONTRACT},
                'code':exc.code,'detail':str(exc),
                'findings':[{'code':item.code,'subject':item.subject,'detail':item.detail}
                            for item in getattr(exc,'findings',())]}
    lineage=next((row for row in loaded.lineage
                  if row.get('metric_id')==reference_id and row.get('input_kind')=='raw'),{})
    return {'status':'verified','instance_id':instance_id,
            'contract':{'instance':contracts.INSTANCE_CONTRACT,'evidence':contracts.EVIDENCE_CONTRACT},
            'component':{'type':'reference-comparison','version':'1'},'subject':subject,
            'reference_year':parameters['reference_year'],'latest_year':parameters['latest_year'],
            'measure':parameters['measure'],
            'reference_count':{'metric_id':reference_id,'value':loaded.metrics[reference_id]['value']},
            'latest_count':{'metric_id':latest_id,'value':loaded.metrics[latest_id]['value']},
            'result':{'metric_id':result_id,'value':value,'unit':'percent',
                      'formula':'percent_change','availability':'available'},
            'effective':checked.effective,'trace':[dict(item) for item in checked.trace],
            'identities':checked.identities,
            'snapshot':{'snapshot_id':loaded.snapshot['snapshot_id'],
                        'snapshot_path':loaded.snapshot.get('snapshot_path')},
            'implementation':evidence['implementation'],'reproduction':evidence['reproduction'],
            'lineage':{'source_file':lineage.get('source_file'),'source_row':lineage.get('source_row'),
                       'sha256':lineage.get('sha256')}}

def build_series_block(bundle,project_root,instance_id,topic,measure,years=None,presentation=None):
    """Resolve one saved annual series display block from saved rows only.

    The block selects a display subset of already eligible saved observations. It never
    recalculates a count, interpolates a missing year or substitutes a measure/topic.
    An optional closed presentation style changes figure scale and wording only. A failed
    check returns an explicit failed record instead of a plausible-looking chart.
    """
    import composer_contracts as contracts
    bundle=Path(bundle)
    style=None
    try:
        if presentation is not None:
            if not isinstance(presentation,dict) or set(presentation)!={'style'}:
                raise contracts.ContractError('presentation',
                    'presentation must be an object with the single key style')
            style=presentation['style']
            if style not in SERIES_STYLES:
                raise contracts.ContractError('presentation',
                    f'unsupported presentation style {style!r}; supported {list(SERIES_STYLES)}')
        loaded=contracts.load_bundle(bundle)
        scope=contracts.scope_of(loaded.stakeholder)
        reporting=[int(scope['years'][0]),int(scope['years'][1])]
        if years is None:
            start,end=reporting
        else:
            start,end=int(years[0]),int(years[1])
            if start>end:
                raise contracts.ContractError('periods',f'requested years {start}-{end} are not ordered')
            if start<reporting[0] or end>reporting[1]:
                raise contracts.ContractError('periods',
                    f'requested years {start}-{end} are outside the report window {reporting[0]}-{reporting[1]}')

        topic_rows=[row for row in loaded.series if row.get('topic')==topic]
        if not topic_rows:
            raise contracts.ContractError('selection',f'topic {topic!r} has no saved annual series rows')
        measures=sorted({row.get('measure') or '' for row in topic_rows})
        if measure not in measures:
            raise contracts.ContractError('measure',
                f'measure {measure!r} is not saved for topic {topic!r}; saved measures: {measures}')
        rows=[row for row in topic_rows if row.get('measure')==measure]

        included=[row for row in loaded.selection if row.get('topic')==topic and row.get('status')=='included']
        if not included:
            reasons=sorted({row.get('reason') or '' for row in loaded.selection
                            if row.get('topic')==topic and row.get('reason')})
            detail='; '.join(reasons) if reasons else 'no input dataset in this snapshot'
            raise contracts.ContractError('selection',f'topic {topic!r} is not included in this saved bundle: {detail}')
        sources={(row.get('dataset_id'),row.get('source_system')) for row in rows}
        if len(sources)!=1:
            raise contracts.ContractError('selection_ambiguous',
                f'saved series rows for {topic!r}/{measure!r} span {len(sources)} dataset/source pairs')
        dataset_id,source_system=next(iter(sources))
        matching=[row for row in included
                  if row.get('dataset_id')==dataset_id and row.get('source_system')==source_system]
        if not matching:
            raise contracts.ContractError('selection',
                f'no included selection row for dataset {dataset_id!r} / source {source_system!r}')
        if len(matching)>1:
            raise contracts.ContractError('selection_ambiguous',
                'several included selection rows match the bound dataset and source')
        geographies={row.get('geography') for row in rows}
        if len(geographies)!=1:
            raise contracts.ContractError('series_scope_disagreement','saved series rows span several geographies')
        geography=next(iter(geographies))
        if geography!=scope['geography']:
            raise contracts.ContractError('scope_disagreement',
                f'saved series geography {geography!r} differs from the report scope {scope["geography"]!r}')

        by_year={}
        for row in rows:
            try: year=int(str(row.get('year')))
            except (TypeError,ValueError):
                raise contracts.ContractError('invalid_value',
                    f'saved series year {row.get("year")!r} is not an annual integer')
            if year<start or year>end: continue
            if year in by_year:
                raise contracts.ContractError('duplicate_row',
                    f'saved series repeats {topic}:{year} for measure {measure!r}')
            value=row.get('value')
            try: number=float(value)
            except (TypeError,ValueError):
                raise contracts.ContractError('invalid_value',f'unparsable saved number {value!r}')
            if not math.isfinite(number):
                raise contracts.ContractError('nonfinite',f'saved number {value!r} is not finite')
            by_year[year]={'year':year,'count_metric_id':row.get('count_metric_id'),
                           'value':value,'unit':row.get('measure')}
        if not by_year:
            raise contracts.ContractError('selection',
                f'no saved observations for {topic!r}/{measure!r} in {start}-{end}')
        observations=[by_year[year] for year in sorted(by_year)]
        missing=[year for year in range(start,end+1) if year not in by_year]

        artifact_digest=loaded.manifest.get('files',{}).get(contracts.SERIES_ARTIFACT)
        if artifact_digest is None:
            raise contracts.ContractError('artifact',
                f'{contracts.SERIES_ARTIFACT} is not listed in bundle.json')
        document={'contract':contracts.SERIES_CONTRACT,
            'component':{'type':'series-trend','version':'1'},
            'instance_id':instance_id,
            'analysis':{'snapshot_id':loaded.snapshot['snapshot_id'],'scope':scope},
            'selection':{'topic':topic,'measure':measure,'geography':geography,
                         'dataset_id':dataset_id,'source_system':source_system},
            'periods':{'requested':[start,end],'effective':[row['year'] for row in observations],
                       'reference_year':int(scope['reference_year']),
                       'reference_outside_window':int(scope['reference_year']) not in by_year},
            'observations':observations,'missing_years':missing,
            'artifact':{'file':contracts.SERIES_ARTIFACT,'digest':artifact_digest},
            'implementation':{
                'analysis':{'file':'scripts/health_pipeline/analyse.py',
                            'sha256':digest(PROJECT/'scripts/health_pipeline/analyse.py')},
                'presentation':{'file':'scripts/health_pipeline/templates/report_helpers.R',
                                'sha256':digest(PROJECT/'scripts/health_pipeline/templates/report_helpers.R')},
                # Files that actually build, validate and render this block, in the same
                # code-reference shape. Additive: identities never hash implementation.
                'contracts':_code_reference('scripts/health_pipeline/composer_contracts.py'),
                'binding':_code_reference('scripts/health_pipeline/publish.py'),
                'schema':_code_reference(SERIES_SCHEMA)},
            'presentation':{'unit':measure,**({'style':style} if style else {})}}
        checked=contracts.check_series_block(document,loaded,project_root=project_root)
    except contracts.ContractError as exc:
        return {'status':'failed','instance_id':instance_id,
                'component':{'type':'series-trend','version':'1'},
                'contract':{'series':contracts.SERIES_CONTRACT},
                'code':exc.code,'detail':str(exc),
                'findings':[{'code':item.code,'subject':item.subject,'detail':item.detail}
                            for item in getattr(exc,'findings',())]}
    return {'status':'verified','instance_id':instance_id,
            'contract':{'series':contracts.SERIES_CONTRACT},
            'component':{'type':'series-trend','version':'1'},
            'selection':document['selection'],'periods':document['periods'],
            'observations':document['observations'],'missing_years':document['missing_years'],
            'artifact':document['artifact'],'presentation':document['presentation'],
            'effective':checked.effective,'trace':[dict(item) for item in checked.trace],
            'identities':checked.identities,
            'snapshot':{'snapshot_id':loaded.snapshot['snapshot_id'],
                        'snapshot_path':loaded.snapshot.get('snapshot_path')},
            'implementation':document['implementation'],
            'reproduction':{'entry_point':'snakemake --cores 2',
                            'snapshot_id':loaded.snapshot['snapshot_id']}}

COLLECTION_CONTRACT='health-report/series-collection/1'
COLLECTION_IDENTITY_CONTRACT='series-collection-identity/1'
MEMBER_ID_PREFIX='sc'
IDENTIFIER_RE=re.compile(r'[a-z0-9][a-z0-9_-]{2,39}')

def _member_instance_id(collection_instance, topic):
    """Bounded, deterministic member block id: readable topic tail plus a stable digest.

    The id is derived only from the collection instance and the topic, so it is stable when
    the collection is reordered. The digest keeps it unique for long or similar topic slugs;
    the length stays inside the existing 40-character identifier limit.
    """
    token=hashlib.sha256(f'{collection_instance}\x00{topic}'.encode('utf-8')).hexdigest()[:10]
    prefix=f'{MEMBER_ID_PREFIX}-{token}-'
    room=40-len(prefix)
    slug=re.sub(r'[^a-z0-9]+','-',str(topic).lower()).strip('-') or 'topic'
    slug=slug[:max(room,1)].strip('-') or 'topic'
    candidate=f'{prefix}{slug}'
    if len(candidate)>40 or not IDENTIFIER_RE.fullmatch(candidate):
        raise ValueError(f'cannot derive a bounded member instance id for topic {topic!r}')
    return candidate

def _collection_identity(payload):
    """Versioned collection presentation identity; order is an explicit input."""
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()

def build_series_collection(bundle,project_root,instance_id,topics,measure,years=None,presentation=None):
    """One checked collection over per-topic series records built by the existing core.

    This adds aggregation only: every member is a separately checked
    health-report/series-component/1 document produced by build_series_block(). An explicit
    request must resolve completely; a partly resolvable request fails the collection. A member
    with a genuine internal gap stays valid and keeps its gap semantics.
    """
    import composer_contracts as contracts
    bundle=Path(bundle)
    style='standard'; default_topic=None
    try:
        if presentation is not None:
            if not isinstance(presentation,dict) or not set(presentation)<={'style','default_topic'}:
                raise contracts.ContractError('presentation',
                    'presentation accepts only style and default_topic')
            style=presentation.get('style','standard')
            if style not in SERIES_STYLES:
                raise contracts.ContractError('presentation',
                    f'unsupported presentation style {style!r}; supported {list(SERIES_STYLES)}')
            default_topic=presentation.get('default_topic')
        loaded=contracts.load_bundle(bundle)
        eligible=sorted({row.get('topic') for row in loaded.selection
                         if (row.get('status') or '').lower()=='included'})
        if topics=='eligible':
            requested=list(eligible); ordering='eligible-ascending'
        elif isinstance(topics,list) and topics:
            requested=[str(topic) for topic in topics]; ordering='author'
        else:
            raise contracts.ContractError('selection',
                'topics must be "eligible" or a non-empty list of topic ids')
        unknown=[topic for topic in requested if topic not in eligible]
        if unknown:
            raise contracts.ContractError('selection',
                'requested topic(s) are not eligible in this saved bundle: '+', '.join(unknown))
        if len(set(requested))!=len(requested):
            raise contracts.ContractError('selection','requested topics contain a duplicate')
        default_topic=default_topic or requested[0]
        if default_topic not in requested:
            raise contracts.ContractError('presentation',
                f'default_topic {default_topic!r} is not one of the resolved topics')

        members=[]
        for topic in requested:
            member_id=_member_instance_id(instance_id,topic)
            record=build_series_block(bundle,project_root,member_id,topic,measure,years,
                                      {'style':style})
            if record.get('status')!='verified':
                detail=f"{record.get('code','failed')}: {record.get('detail','')}".strip()
                raise contracts.ContractError('member',
                    f'member topic {topic!r} did not resolve ({detail})')
            if (record.get('selection') or {}).get('topic')!=topic:
                raise contracts.ContractError('member_mismatch',
                    f'member record topic {(record.get("selection") or {}).get("topic")!r} '
                    f'does not equal the requested topic {topic!r}')
            if (record.get('selection') or {}).get('measure')!=measure:
                raise contracts.ContractError('member_mismatch',
                    f'member record measure {record["selection"].get("measure")!r} differs from {measure!r}')
            members.append(record)
        member_ids=[member['instance_id'] for member in members]
        if len(set(member_ids))!=len(member_ids):
            raise contracts.ContractError('member','derived member instance ids are not unique')
        periods=[member['periods']['requested'] for member in members]
        if len({tuple(item) for item in periods})!=1:
            raise contracts.ContractError('periods','members resolved different requested periods')
        start,end=periods[0]
        effective=sorted({int(year) for member in members
                          for year in member['periods']['effective']})

        payload={'contract':COLLECTION_IDENTITY_CONTRACT,'instance_id':instance_id,
                 'measure':measure,'style':style,'default_topic':default_topic,
                 'periods':{'requested':[int(start),int(end)],'effective':effective},
                 'members':[{'instance_id':member['instance_id'],
                             'topic':member['selection']['topic'],
                             'status':member['status'],
                             'instance_identity':member['identities']['instance']}
                            for member in members]}
        record={'status':'verified','instance_id':instance_id,
            'component':{'type':'series-collection','version':'1'},
            'contract':{'series':contracts.SERIES_CONTRACT,'collection':COLLECTION_CONTRACT},
            'topics':requested,'ordering':ordering,'measure':measure,
            'presentation':{'style':style,'default_topic':default_topic},
            'periods':payload['periods'],'members':members,
            'identities':{'collection':_collection_identity(payload),
                          'contract':COLLECTION_IDENTITY_CONTRACT,
                          'members':payload['members']},
            'snapshot':{'snapshot_id':loaded.snapshot['snapshot_id'],
                        'snapshot_path':loaded.snapshot.get('snapshot_path')},
            'implementation':dict(members[0].get('implementation') or {}),
            'reproduction':{'entry_point':'snakemake --cores 2',
                            'snapshot_id':loaded.snapshot['snapshot_id']}}
    except contracts.ContractError as exc:
        return {'status':'failed','instance_id':instance_id,
                'component':{'type':'series-collection','version':'1'},
                'contract':{'collection':COLLECTION_CONTRACT},
                'code':exc.code,'detail':str(exc),
                'findings':[{'code':item.code,'subject':item.subject,'detail':item.detail}
                            for item in getattr(exc,'findings',())]}
    return record

def _block_identity(tag, payload):
    canonical = json.dumps([tag, payload], sort_keys=True, separators=(',', ':'),
                            ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _scope_token(scope, contracts):
    fields = [field for field in contracts.SCOPE_FIELDS if field in scope]
    fields += [field for field in contracts.TOPIC_SCOPE_FIELDS if field in scope]
    return {field: contracts.canonical_scope(field, scope[field]) for field in fields}


def _composite_implementation():
    """Same code-reference shape as the series block; no new provenance container."""
    return {'presentation': _code_reference('scripts/health_pipeline/templates/report_helpers.R'),
            'contracts': _code_reference('scripts/health_pipeline/composer_contracts.py'),
            'binding': _code_reference('scripts/health_pipeline/publish.py'),
            'schema': _code_reference(SERIES_SCHEMA)}


def _failed_composite(component, instance_id, exc):
    return {'status': 'failed', 'instance_id': instance_id,
            'component': {'type': component, 'version': '1'},
            'binding': COMPOSITE_BINDING, 'code': exc.code, 'detail': str(exc),
            'findings': [{'code': item.code, 'subject': item.subject, 'detail': item.detail}
                         for item in getattr(exc, 'findings', ())]}


def build_coverage_block(bundle, project_root, instance_id, displayed_topics=None,
                         include_group_scope=False):
    """Saved selection/source coverage: what was requested, included, excluded, displayed.

    Counts datasets, topics, saved observations and actual recipe bindings separately. No
    year-level completeness is derived: the bundle records dataset/topic decisions only.
    """
    import composer_contracts as contracts
    bundle = Path(bundle)
    try:
        loaded = contracts.load_bundle(bundle)
        scope = contracts.scope_of(loaded.stakeholder)
        manifest = loaded.manifest.get('files') or {}
        required = ('selection.csv', 'sources.csv', 'series.csv')
        missing = [name for name in required
                   if name not in manifest or not (bundle / name).is_file()]
        if missing:
            raise contracts.ContractError('artifact',
                'missing saved selection/source/series records: ' + ', '.join(missing))
        for name in required:
            if digest(bundle / name) != manifest[name]:
                raise contracts.ContractError('digest_disagreement',
                    f'{name} differs from the bundle manifest')
        selection = _csv_rows(bundle / 'selection.csv')
        sources = _csv_rows(bundle / 'sources.csv')
        if not selection:
            raise contracts.ContractError('selection', 'the saved selection record is empty')
        included = [row for row in selection if (row.get('status') or '').lower() == 'included']
        excluded = [row for row in selection if (row.get('status') or '').lower() == 'excluded']
        if not included:
            raise contracts.ContractError('selection', 'no dataset is recorded as included')
        topics_included = sorted({row.get('topic') for row in included})
        excluded_reasons = {}
        for row in excluded:
            excluded_reasons.setdefault(row.get('topic'), set()).add(
                row.get('reason') or 'no reason recorded')
        displayed = sorted({topic for topic in (displayed_topics or []) if topic})
        unknown = [topic for topic in displayed if topic not in topics_included]
        if unknown:
            raise contracts.ContractError('selection',
                'displayed topic(s) are not included in the saved selection: '
                + ', '.join(unknown))
        counts = {'datasets_total': len(selection),
                  'datasets_included': len(included),
                  'datasets_excluded': len(excluded),
                  'topics_included': len(topics_included),
                  'topics_excluded': len(excluded_reasons),
                  'topics_group_sum': len([topic for topic in topics_included
                                           if any((row.get('topic') == topic
                                                   and (row.get('group_eligible') or '').lower() == 'true')
                                                  for row in included)]),
                  'observations_total': len(loaded.series),
                  'observations_in_window': sum(
                      1 for row in loaded.series
                      if str(row.get('year', '')).isdigit()
                      and int(scope['years'][0]) <= int(row['year']) <= int(scope['years'][1])),
                  'source_registry_rows': len(sources),
                  'source_registry_used': sum(1 for row in sources
                                              if (row.get('used') or '').lower() == 'true')}
        group_scope = []
        if include_group_scope:
            totals = {}
            for metric in loaded.metrics.values():
                subject = metric.get('subject') or ''
                if ':' in subject and metric.get('metric_type') == 'group_total':
                    totals.setdefault(subject, []).append(metric)
            for group_class in sorted({subject.split(':')[0] for subject in totals}):
                main, sensitivity = f'{group_class}:main', f'{group_class}:sensitivity'
                if main not in totals or sensitivity not in totals:
                    continue
                for label, subject in (('main', main), ('sensitivity', sensitivity)):
                    latest = max(totals[subject], key=lambda item: int(str(item.get('year'))))
                    member_ids = json.loads(latest.get('inputs_json') or '[]')
                    group_scope.append({
                        'subject': subject, 'specification': label,
                        'metric_id': latest['metric_id'],
                        'members': sorted({metric_id.split(':')[0] for metric_id in member_ids})})
        excluded_datasets = [{'dataset_id': row.get('dataset_id'), 'topic': row.get('topic'),
                              'reason': row.get('reason') or 'no reason recorded'}
                             for row in excluded]
        binding = {name: manifest[name] for name in required}
        scope_token = _scope_token(scope, contracts)
        snapshot_id = loaded.snapshot['snapshot_id']
        analytical = _block_identity('coverage-analytical/1',
            {'snapshot_id': snapshot_id, 'scope': scope_token,
             'method': {'id': 'saved_selection_records', 'version': '1'},
             'binding': binding})
        instance = _block_identity('coverage-instance/1',
            {'analytical': analytical, 'instance_id': instance_id,
             'counts': counts, 'displayed_topics': displayed})
    except contracts.ContractError as exc:
        return _failed_composite('coverage-selection', instance_id, exc)
    return {'status': 'verified', 'instance_id': instance_id,
            'component': {'type': 'coverage-selection', 'version': '1'},
            'binding': COMPOSITE_BINDING,
            'requested': {'years': list(scope.get('years') or []),
                          'geography': scope.get('geography'),
                          'include_topics': scope.get('include_topics'),
                          'exclude_topics': scope.get('exclude_topics')},
            'counts': counts,
            'topics_included': topics_included,
            'excluded': [{'topic': topic, 'reasons': sorted(reasons)}
                         for topic, reasons in sorted(excluded_reasons.items())],
            'displayed_topics': displayed,
            'displayed_groups': group_scope,
            'excluded_datasets': excluded_datasets,
            'unsupported': ['A topic-by-year completeness matrix is not available: the saved '
                            'bundle records dataset and topic decisions, not per-year coverage.'],
            'identities': {'analytical': analytical, 'instance': instance},
            'bindings': [{'file': name, 'digest': binding[name]} for name in required],
            'snapshot': {'snapshot_id': snapshot_id,
                         'snapshot_path': loaded.snapshot.get('snapshot_path')},
            'implementation': _composite_implementation(),
            'reproduction': {'entry_point': 'python scripts/health_pipeline/publish.py batch',
                             'snapshot_id': snapshot_id}}


def build_monitoring_block(bundle, project_root, instance_id):
    """One descriptive row per included topic from saved series and comparison metrics."""
    import composer_contracts as contracts
    bundle = Path(bundle)
    try:
        loaded = contracts.load_bundle(bundle)
        scope = contracts.scope_of(loaded.stakeholder)
        start, end = int(scope['years'][0]), int(scope['years'][1])
        included = sorted({row.get('topic') for row in loaded.selection
                           if (row.get('status') or '').lower() == 'included'})
        if not included:
            raise contracts.ContractError('selection', 'no included topic in the saved selection')
        manifest = loaded.manifest.get('files') or {}
        checks = _csv_rows(bundle / 'checks.csv') if 'checks.csv' in manifest else []
        checks_by_dataset = {}
        for row in checks:
            bucket = checks_by_dataset.setdefault(row.get('dataset_id'), {})
            key = (row.get('status') or '').lower()
            bucket[key] = bucket.get(key, 0) + 1
        rows = []
        for topic in included:
            topic_rows = [row for row in loaded.series
                          if row.get('topic') == topic
                          and str(row.get('year', '')).isdigit()
                          and start <= int(row['year']) <= end]
            if not topic_rows:
                rows.append({'topic': topic, 'availability': 'no saved annual observation',
                             'measure': None, 'latest_year': None, 'latest_value': None,
                             'latest_metric_id': None, 'dataset_id': None,
                             'comparisons': [], 'recorded_checks': {}})
                continue
            measures = sorted({row.get('measure') or '' for row in topic_rows})
            if len(measures) != 1:
                raise contracts.ContractError('measure_ambiguous',
                    f'topic {topic!r} saves {len(measures)} measures; a single measure is required')
            latest = max(topic_rows, key=lambda row: int(row['year']))
            metric = loaded.metrics.get(latest.get('count_metric_id') or '')
            if metric is None:
                raise contracts.ContractError('metric_missing',
                    f'latest series row for {topic!r} has no saved count metric')
            comparisons = []
            comparison_types = ('reference_change', 'period_change')
            for metric_type in comparison_types:
                candidates = [m for m in loaded.metrics.values()
                              if m.get('subject') == topic
                              and m.get('metric_type') == metric_type]
                if len(candidates) > 1:
                    raise contracts.ContractError('selection_ambiguous',
                        f'topic {topic!r} saves {len(candidates)} {metric_type} results')
                if not candidates:
                    continue
                item = candidates[0]
                years = []
                endpoint_ids = json.loads(item.get('inputs_json') or '[]')
                endpoints = []
                for metric_id in endpoint_ids:
                    source = loaded.metrics.get(metric_id) or {}
                    if str(source.get('year', '')).isdigit():
                        years.append(str(source['year']))
                    endpoints.append({'year': source.get('year'), 'metric_id': metric_id,
                                      'value': source.get('value'), 'unit': source.get('unit')})
                if len(years) != 2 or len(endpoints) != 2:
                    raise contracts.ContractError('bindings',
                        f'{item["metric_id"]} does not bind two saved count endpoints')
                comparisons.append({'metric_id': item['metric_id'], 'type': metric_type,
                                    'value': item.get('value'), 'unit': item.get('unit'),
                                    'formula': item.get('formula'),
                                    'from_year': years[0], 'to_year': years[1],
                                    'reference': endpoints[0], 'latest': endpoints[1]})
            if not comparisons:
                comparisons = []
            rows.append({'topic': topic, 'availability': 'saved observation',
                         'measure': measures[0], 'latest_year': int(latest['year']),
                         'latest_value': latest.get('value'),
                         'latest_metric_id': latest.get('count_metric_id'),
                         'dataset_id': latest.get('dataset_id'),
                         'comparisons': comparisons,
                         'recorded_checks': checks_by_dataset.get(latest.get('dataset_id'), {})})
        units = sorted({row['measure'] for row in rows if row.get('measure')})
        binding = {name: manifest[name] for name in ('series.csv', 'metrics.csv')
                   if name in manifest}
        scope_token = _scope_token(scope, contracts)
        snapshot_id = loaded.snapshot['snapshot_id']
        analytical = _block_identity('monitoring-analytical/1',
            {'snapshot_id': snapshot_id, 'scope': scope_token,
             'method': {'id': 'saved_latest_observation', 'version': '1'},
             'binding': binding})
        instance = _monitoring_instance_identity(analytical, instance_id, rows)
    except contracts.ContractError as exc:
        return _failed_composite('monitoring-overview', instance_id, exc)
    return {'status': 'verified', 'instance_id': instance_id,
            'component': {'type': 'monitoring-overview', 'version': '1'},
            'binding': COMPOSITE_BINDING,
            'rows': rows, 'units': units,
            'limits': ['One row per included topic with its latest saved annual value. '
                       'No composite score, ranking, alert threshold or common scale is derived.'],
            'identities': {'analytical': analytical, 'instance': instance},
            'bindings': [{'file': name, 'digest': value} for name, value in binding.items()],
            'snapshot': {'snapshot_id': snapshot_id,
                         'snapshot_path': loaded.snapshot.get('snapshot_path')},
            'implementation': _composite_implementation(),
            'reproduction': {'entry_point': 'python scripts/health_pipeline/publish.py batch',
                             'snapshot_id': snapshot_id}}


def build_sensitivity_block(bundle, project_root, instance_id):
    """Saved main/sensitivity group specifications, their members and exact saved results."""
    import composer_contracts as contracts
    bundle = Path(bundle)
    try:
        loaded = contracts.load_bundle(bundle)
        scope = contracts.scope_of(loaded.stakeholder)
        reference_year = str(scope['reference_year'])
        latest_year = str(scope['years'][1])
        by_subject = {}
        for metric in loaded.metrics.values():
            subject = metric.get('subject') or ''
            if ':' in subject and metric.get('metric_type') in (
                    'group_total', 'group_index', 'period_change', 'reference_change'):
                by_subject.setdefault(subject, []).append(metric)

        def total(subject, year):
            for metric in by_subject.get(subject, []):
                if metric.get('metric_type') == 'group_total' and str(metric.get('year')) == year:
                    return metric
            return None

        def change(subject):
            for metric in by_subject.get(subject, []):
                if metric.get('metric_type') == 'reference_change':
                    return metric
            return None

        def members(subject):
            item = total(subject, latest_year)
            if item is None:
                return None
            try:
                ids = json.loads(item.get('inputs_json') or '[]')
            except ValueError:
                raise contracts.ContractError('members', f'{subject} has unparsable member inputs')
            if not ids:
                raise contracts.ContractError('members', f'{subject} records no member metrics')
            return sorted(ids)

        pairs = []
        for group_class in sorted({subject.split(':')[0] for subject in by_subject}):
            main, sensitivity = f'{group_class}:main', f'{group_class}:sensitivity'
            if main not in by_subject or sensitivity not in by_subject:
                continue
            specifications = []
            for label, subject in (('main', main), ('sensitivity', sensitivity)):
                reference_total = total(subject, reference_year)
                latest_total = total(subject, latest_year)
                result = change(subject)
                if reference_total is None or latest_total is None or result is None:
                    raise contracts.ContractError('results',
                        f'{subject} is missing a saved total or reference_change result')
                member_ids = members(subject)
                if member_ids is None:
                    raise contracts.ContractError('members',
                        f'{subject} has no saved group total in {latest_year}')
                try:
                    reference_member_ids = sorted(json.loads(
                        reference_total.get('inputs_json') or '[]'))
                except ValueError:
                    raise contracts.ContractError('members',
                        f'{reference_total["metric_id"]} has unparsable member inputs')
                specifications.append({'subject': subject, 'role': label,
                                       'members': sorted({metric_id.split(':')[0]
                                                          for metric_id in member_ids}),
                                       'member_metric_ids': member_ids,
                                       'reference_member_metric_ids': reference_member_ids,
                                       'latest_member_metric_ids': member_ids,
                                       'reference': {'year': int(reference_year),
                                                     'metric_id': reference_total['metric_id'],
                                                     'value': reference_total.get('value'),
                                                     'unit': reference_total.get('unit')},
                                       'latest': {'year': int(latest_year),
                                                  'metric_id': latest_total['metric_id'],
                                                  'value': latest_total.get('value'),
                                                  'unit': latest_total.get('unit')},
                                       'reference_change': {'metric_id': result['metric_id'],
                                                            'value': result.get('value'),
                                                            'unit': result.get('unit')},
                                       'artifact': {'file': 'metrics.csv',
                                                    'digest': loaded.manifest['files']['metrics.csv']}})
            main_members = set(specifications[0]['members'])
            sensitivity_members = set(specifications[1]['members'])
            pairs.append({'class': group_class, 'specifications': specifications,
                          'excluded_members': sorted(main_members - sensitivity_members),
                          'added_members': sorted(sensitivity_members - main_members),
                          'identical_members': main_members == sensitivity_members,
                          'identical_results': (
                              specifications[0]['reference_change']['value']
                              == specifications[1]['reference_change']['value'])})
        if not pairs:
            raise contracts.ContractError('selection',
                'no class saves both a main and a sensitivity specification')
        scope_token = _scope_token(scope, contracts)
        snapshot_id = loaded.snapshot['snapshot_id']
        metric_ids = sorted({spec['reference_change']['metric_id']
                             for pair in pairs for spec in pair['specifications']})
        binding = {'metrics.csv': loaded.manifest['files']['metrics.csv']}
        analytical = _block_identity('sensitivity-analytical/1',
            {'snapshot_id': snapshot_id, 'scope': scope_token,
             'method': {'id': 'saved_group_specifications', 'version': '1'},
             'metric_ids': metric_ids})
        instance = _block_identity('sensitivity-instance/1',
            {'analytical': analytical, 'instance_id': instance_id,
             'classes': [pair['class'] for pair in pairs]})
    except contracts.ContractError as exc:
        return _failed_composite('sensitivity-comparison', instance_id, exc)
    return {'status': 'verified', 'instance_id': instance_id,
            'component': {'type': 'sensitivity-comparison', 'version': '1'},
            'binding': COMPOSITE_BINDING, 'pairs': pairs,
            'question': ('How do the saved main group specification and its recorded '
                         'sensitivity specification differ?'),
            'limits': ['This compares two saved specifications. It is not a robustness, '
                       'significance or uncertainty assessment.'],
            'identities': {'analytical': analytical, 'instance': instance},
            'bindings': [{'file': 'metrics.csv', 'digest': binding['metrics.csv']}],
            'snapshot': {'snapshot_id': snapshot_id,
                         'snapshot_path': loaded.snapshot.get('snapshot_path')},
            'implementation': _composite_implementation(),
            'reproduction': {'entry_point': 'python scripts/health_pipeline/publish.py batch',
                             'snapshot_id': snapshot_id}}


def _monitoring_instance_identity(analytical, instance_id, rows):
    """Instance identity covering latest values and the bound comparison endpoints."""
    payload = [[row['topic'], row['latest_year'], row['latest_value'],
                [[cmp['type'], cmp['metric_id'], cmp['from_year'], cmp['to_year'],
                  cmp['value']] for cmp in row['comparisons']]]
               for row in rows]
    return _block_identity('monitoring-instance/2',
                           {'analytical': analytical, 'instance_id': instance_id,
                            'rows': payload})


def _resolved_scope(recipe, records):
    """What the recipe actually displays, kept as separate facts.

    ``standalone_topics`` are bound by single-topic blocks (reference, series-trend);
    ``collection_topics`` are the verified members of a series collection; ``monitoring_topics``
    are rows of the monitoring table. None of them is folded into another, so a consumer can
    state what is shown and how.
    """
    by_id = {record['instance_id']: record for record in records}
    standalone, collected, monitored, groups = set(), set(), set(), []
    collection_default = None
    for entry in recipe['blocks']:
        record = by_id.get(entry['instance_id'])
        if not record or record.get('status') != 'verified':
            continue
        kind = (record.get('component') or {}).get('type')
        if kind == 'series-trend':
            standalone.add(record['selection']['topic'])
        elif kind == 'series-collection':
            collected.update((member.get('selection') or {}).get('topic')
                             for member in (record.get('members') or [])
                             if member.get('status') == 'verified')
            collection_default = (record.get('presentation') or {}).get('default_topic')
        elif kind == 'reference-comparison':
            standalone.add(record['subject'])
        elif kind == 'monitoring-overview':
            monitored.update(row['topic'] for row in record['rows']
                             if row.get('availability') == 'saved observation')
        elif kind == 'sensitivity-comparison':
            for pair in record['pairs']:
                for spec in pair['specifications']:
                    groups.append({'subject': spec['subject'],
                                   'specification': spec['role'],
                                   'members': spec['members']})
    return {'standalone_topics': sorted(standalone),
            'collection_topics': sorted(collected),
            'collection_default_topic': collection_default,
            'monitoring_topics': sorted(monitored),
            'displayed_topics': sorted(standalone | collected | monitored),
            'group_summaries': groups}


def _effective_titles(bundle, scope):
    """Reader-facing title/subtitle from the resolved scope; saved metadata is untouched.

    A collection is described as a collection, never by joining every member name into the
    title. The default-open topic carries the focus where a focus is wanted.
    """
    collected = scope.get('collection_topics') or []
    topics = scope['standalone_topics'] or scope['displayed_topics']
    if not topics:
        return None, None
    import composer_contracts as contracts
    loaded = contracts.load_bundle(Path(bundle))
    labels = {}
    for row in loaded.series:
        labels.setdefault(row.get('topic'), row.get('label') or row.get('topic'))
    names = [labels.get(topic) or topic.replace('_', ' ') for topic in topics]
    geography = 'Switzerland and Liechtenstein' if contracts.scope_of(loaded.stakeholder).get('geography') == 'CHFL' else 'Switzerland'
    layout = (loaded.stakeholder.get('presentation') or {}).get('layout')
    default_topic = scope.get('collection_default_topic') or (collected[0] if collected else None)
    default_label = labels.get(default_topic) or (default_topic or '').replace('_', ' ')
    if scope['monitoring_topics']:
        focus = default_label or names[0]
        return ('Notifiable disease monitoring overview',
                f"{geography} · {focus} focus")
    if len(collected) > 1:
        if layout == 'editorial':
            return (f'{default_label}: reported cases and saved comparisons',
                    f'{geography} · {len(collected)} topics available to explore')
        return (f'Annual reported cases for {len(collected)} notifiable diseases',
                f'{geography} · {len(collected)} topics')
    return ', '.join(names) + ': reported cases and saved comparisons', None


COMPOSITE_BLOCKS = ('coverage-selection', 'monitoring-overview', 'sensitivity-comparison')
KNOWN_BLOCKS = ('intro','series-trend','series-collection','reference-comparison','limitations',
                'reproduction',*COMPOSITE_BLOCKS)
COMPOSITE_BINDING = 'saved-records/1'
COMPOSITION_CONTRACT = 'health-report/composition-recipe/1'
COMPOSITION_CONTRACT_V2 = 'health-report/composition-recipe/2'
TOPIC_ID = re.compile(r'[a-z0-9][a-z0-9_-]*')
MEASURE_ID = re.compile(r'[a-z][a-z0-9_]*')

# Closed display styles for the saved-series block. A style changes figure scale and
# presentation wording only: never rows, values, units, gap handling or analytical
# identity. Omitted style keeps the historical single-presentation behaviour.
SERIES_STYLES = ('standard', 'compact')
SERIES_SCHEMA = 'scripts/health_pipeline/config/composer/series-contract/1.json'


def _code_reference(relative):
    """Existing code-reference convention: project-relative path plus its digest."""
    return {'file': relative, 'sha256': digest(PROJECT / relative)}


def _recipe_years(entry, instance):
    """Optional inclusive [start, end] for a series-trend entry. Types only here.

    The reporting window and annual ordering are checked against the saved scope when the
    block is built; a recipe file alone cannot know that window.
    """
    if 'years' not in entry:
        return None
    years = entry['years']
    if (not isinstance(years, list) or len(years) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in years)):
        raise ValueError(f'Invalid years for block instance {instance!r}: expected [start, end] integers')
    if years[0] > years[1]:
        raise ValueError(f'Invalid years for block instance {instance!r}: start is after end')
    return years


def load_composition(path):
    """Validate a block recipe. Order and membership are data, not renderer code.

    v1 keeps the historical deterministic reference binding. v2 requires an explicit
    topic for reference-comparison and rejects any other extra per-block options.
    """
    recipe = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(recipe, dict): raise ValueError('Composition recipe must be an object')
    unknown = set(recipe) - {'contract','audience','blocks'}
    if unknown: raise ValueError(f'Unsupported composition fields: {sorted(unknown)}')
    contract = recipe.get('contract')
    if contract not in (COMPOSITION_CONTRACT, COMPOSITION_CONTRACT_V2):
        raise ValueError(f'Unsupported composition contract: {contract!r}')
    blocks = recipe.get('blocks')
    if not isinstance(blocks, list) or not blocks:
        raise ValueError('Composition recipe needs a non-empty blocks list')
    seen = set()
    for entry in blocks:
        if not isinstance(entry, dict) or 'block' not in entry or 'instance_id' not in entry:
            raise ValueError('Each block needs block and instance_id')
        block, instance = entry['block'], entry['instance_id']
        if block not in KNOWN_BLOCKS:
            raise ValueError(f'Unknown block type: {block!r}')
        expected = {'block','instance_id'}
        if contract == COMPOSITION_CONTRACT_V2 and block == 'reference-comparison':
            expected = {'block','instance_id','topic'}
        if block == 'series-trend':
            if contract != COMPOSITION_CONTRACT_V2:
                raise ValueError('Block series-trend requires composition contract '
                                 f'{COMPOSITION_CONTRACT_V2}')
            expected = {'block','instance_id','topic','measure'}
            if 'years' in entry:
                expected.add('years')
            if 'presentation' in entry:
                expected.add('presentation')
        if block == 'series-collection':
            if contract != COMPOSITION_CONTRACT_V2:
                raise ValueError('Block series-collection requires composition contract '
                                 f'{COMPOSITION_CONTRACT_V2}')
            expected = {'block','instance_id','topics','measure'}
            if 'years' in entry:
                expected.add('years')
            if 'presentation' in entry:
                expected.add('presentation')
        if set(entry) != expected:
            raise ValueError(f'Invalid fields for block {block!r}: expected {sorted(expected)}')
        if contract == COMPOSITION_CONTRACT_V2 and block == 'reference-comparison':
            topic = entry['topic']
            if not isinstance(topic, str) or not TOPIC_ID.fullmatch(topic):
                raise ValueError(f'Invalid topic id for block instance {instance!r}: {topic!r}')
        if block == 'series-trend':
            topic = entry['topic']
            if not isinstance(topic, str) or not TOPIC_ID.fullmatch(topic):
                raise ValueError(f'Invalid topic id for block instance {instance!r}: {topic!r}')
            measure = entry['measure']
            if not isinstance(measure, str) or not MEASURE_ID.fullmatch(measure):
                raise ValueError(f'Invalid measure for block instance {instance!r}: {measure!r}')
            _recipe_years(entry, instance)
            presentation = entry.get('presentation')
            if presentation is not None:
                if not isinstance(presentation, dict) or set(presentation) != {'style'}:
                    raise ValueError(f'Invalid presentation for block instance {instance!r}: '
                                     'expected {"style": "standard"|"compact"}')
                if presentation['style'] not in SERIES_STYLES:
                    raise ValueError(f'Unsupported presentation style for block instance {instance!r}: '
                                     f'{presentation["style"]!r}; supported {list(SERIES_STYLES)}')
        if block == 'series-collection':
            topics = entry['topics']
            if topics != 'eligible':
                if not isinstance(topics, list) or not topics:
                    raise ValueError(f'Invalid topics for block instance {instance!r}: '
                                     'expected "eligible" or a non-empty list')
                if any(not isinstance(topic, str) or not TOPIC_ID.fullmatch(topic) for topic in topics):
                    raise ValueError(f'Invalid topic id for block instance {instance!r}')
                if len(set(topics)) != len(topics):
                    raise ValueError(f'Duplicate topic in block instance {instance!r}')
            measure = entry['measure']
            if not isinstance(measure, str) or not MEASURE_ID.fullmatch(measure):
                raise ValueError(f'Invalid measure for block instance {instance!r}: {measure!r}')
            _recipe_years(entry, instance)
            presentation = entry.get('presentation')
            if presentation is not None:
                if (not isinstance(presentation, dict)
                        or not set(presentation) <= {'style', 'default_topic'}):
                    raise ValueError(f'Invalid presentation for block instance {instance!r}: '
                                     'expected style and optionally default_topic')
                if 'style' in presentation and presentation['style'] not in SERIES_STYLES:
                    raise ValueError(f'Unsupported presentation style for block instance {instance!r}: '
                                     f'{presentation["style"]!r}; supported {list(SERIES_STYLES)}')
                if 'default_topic' in presentation:
                    default_topic = presentation['default_topic']
                    if not isinstance(default_topic, str) or not TOPIC_ID.fullmatch(default_topic):
                        raise ValueError(f'Invalid default_topic for block instance {instance!r}: '
                                         f'{default_topic!r}')
                    if topics != 'eligible' and default_topic not in topics:
                        raise ValueError(f'default_topic {default_topic!r} is not one of the '
                                         f'topics requested by block instance {instance!r}')
        if block in COMPOSITE_BLOCKS and contract != COMPOSITION_CONTRACT_V2:
            raise ValueError(f'Block {block} requires composition contract '
                             f'{COMPOSITION_CONTRACT_V2}')
        if not isinstance(instance, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,39}', instance):
            raise ValueError(f'Invalid block instance id: {instance!r}')
        if instance in seen:
            raise ValueError(f'Duplicate block instance id: {instance!r}')
        seen.add(instance)
    # A reference-comparison block carries a checked contract record. One saved record can
    # only be bound to one instance, so repeated reference blocks are refused rather than
    # silently reusing or relabelling the same identity.
    if sum(1 for entry in blocks if entry['block'] == 'reference-comparison') > 1:
        raise ValueError('Repeated reference-comparison blocks are not supported yet')
    if sum(1 for entry in blocks if entry['block'] == 'series-trend') > 1:
        raise ValueError('Repeated series-trend blocks are not supported yet')
    # A collection binds the same saved rows a standalone series block would; allowing both (or
    # two collections) in one recipe would duplicate the same chart under different identities.
    if sum(1 for entry in blocks if entry['block'] == 'series-collection') > 1:
        raise ValueError('Repeated series-collection blocks are not supported yet')
    if (any(entry['block'] == 'series-collection' for entry in blocks)
            and any(entry['block'] == 'series-trend' for entry in blocks)):
        raise ValueError('A recipe cannot combine series-trend and series-collection blocks')
    return recipe

def composition_provenance(recipe, path, blocks):
    """Record the recipe and the checked instance identity behind every block entry."""
    checked = {record['instance_id']: record for record in blocks}
    instances = []
    for entry in recipe['blocks']:
        instance = {'block': entry['block'], 'instance_id': entry['instance_id']}
        record = checked.get(entry['instance_id'])
        if record is not None and entry['block'] == 'series-collection':
            instance.update({'topics': record.get('topics'), 'measure': record.get('measure'),
                             'presentation': record.get('presentation'),
                             'ordering': record.get('ordering'),
                             'member_instance_ids': [member['instance_id']
                                                     for member in (record.get('members') or [])],
                             'contract': (record.get('contract') or {}).get('collection'),
                             'contract_status': record.get('status'),
                             'collection_identity': (record.get('identities') or {}).get('collection')})
        elif record is not None and entry['block'] == 'series-trend':
            periods = record.get('periods') or {}
            instance.update({
                'topic': entry['topic'], 'measure': entry['measure'],
                'presentation': entry.get('presentation'),
                'requested_years': periods.get('requested'),
                'effective_years': periods.get('effective'),
                'missing_years': record.get('missing_years'),
                'contract': (record.get('contract') or {}).get('series'),
                'contract_instance_id': record['instance_id'],
                'contract_status': record['status'],
                'instance_identity': (record.get('identities') or {}).get('instance')})
        elif record is not None and entry['block'] in COMPOSITE_BLOCKS:
            instance.update({'binding': COMPOSITE_BINDING,
                             'contract_status': record['status'],
                             'instance_identity': (record.get('identities') or {}).get('instance')})
        elif record is not None:
            instance['topic'] = entry.get('topic')
            instance['binding'] = 'explicit' if entry.get('topic') else 'deterministic'
            instance['contract'] = (record.get('contract') or {}).get('instance')
            instance['contract_instance_id'] = record['instance_id']
            instance['contract_status'] = record['status']
            instance['instance_identity'] = (record.get('identities') or {}).get('instance')
        instances.append(instance)
    return {'contract': recipe['contract'], 'audience': recipe.get('audience'),
            'recipe_path': Path(path).resolve().as_posix(), 'recipe_sha256': digest(path),
            'effective_recipe': recipe['blocks'], 'instances': instances, 'mode': 'composed'}

def render(bundle,output,fmt,quarto='quarto',provenance=None,provenance_out=None,composition=None):
    if composition is not None and fmt != 'html':
        raise ValueError('PDF export of a composed report is not supported; '
                         'omit --composition for the legacy PDF')
    recipe=load_composition(composition) if composition is not None else None
    if recipe is not None:
        # A recipe names the audience it was written for; rendering it against another
        # audience's bundle would relabel saved output.
        bundle_stakeholder=json.loads((Path(bundle)/'stakeholder.json').read_text(encoding='utf-8'))
        if recipe.get('audience')!=bundle_stakeholder.get('id'):
            raise ValueError(f"Recipe audience {recipe.get('audience')!r} does not match bundle audience {bundle_stakeholder.get('id')!r}")
    output=Path(output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    # Each format gets a separate build directory so concurrent rendering cannot race.
    with tempfile.TemporaryDirectory(prefix='health-report-') as tmp:
        package(bundle,tmp)
        if provenance is not None:
            # Resolve the block at render time from saved records, then embed the same
            # record in HTML and write it as the sidecar so both stay identical.
            provenance=dict(provenance)
            if recipe is not None:
                # Each recipe entry names its own checked record; the instance id is the
                # same value the R renderer uses for its DOM identity. Records carry their
                # component type so consumers can select without positional fallback.
                # Two passes: coverage needs the topics the other blocks actually resolved
                # (a collection resolves its members at build time), while the published order
                # still follows the recipe.
                built={}
                for entry in recipe['blocks']:
                    if entry['block']=='coverage-selection': continue
                    if entry['block']=='reference-comparison':
                        built[entry['instance_id']]=build_block(
                            bundle,Path(bundle).parents[2],PROJECT,
                            entry['instance_id'],entry.get('topic'))
                    elif entry['block']=='series-trend':
                        built[entry['instance_id']]=build_series_block(
                            bundle,PROJECT,entry['instance_id'],entry['topic'],entry['measure'],
                            entry.get('years'),entry.get('presentation'))
                    elif entry['block']=='series-collection':
                        built[entry['instance_id']]=build_series_collection(
                            bundle,PROJECT,entry['instance_id'],entry['topics'],entry['measure'],
                            entry.get('years'),entry.get('presentation'))
                    elif entry['block']=='monitoring-overview':
                        built[entry['instance_id']]=build_monitoring_block(
                            bundle,PROJECT,entry['instance_id'])
                    elif entry['block']=='sensitivity-comparison':
                        built[entry['instance_id']]=build_sensitivity_block(
                            bundle,PROJECT,entry['instance_id'])
                displayed_topics=set()
                for record in built.values():
                    if record.get('status')!='verified': continue
                    kind=(record.get('component') or {}).get('type')
                    if kind=='series-trend': displayed_topics.add(record['selection']['topic'])
                    elif kind=='series-collection':
                        displayed_topics.update((member.get('selection') or {}).get('topic')
                                                for member in (record.get('members') or []))
                    elif kind=='reference-comparison': displayed_topics.add(record['subject'])
                has_sensitivity=any(item['block']=='sensitivity-comparison'
                                    for item in recipe['blocks'])
                records=[]
                for entry in recipe['blocks']:
                    if entry['block']=='coverage-selection':
                        records.append(build_coverage_block(
                            bundle,PROJECT,entry['instance_id'],sorted(displayed_topics),
                            has_sensitivity))
                    else:
                        record=built.get(entry['instance_id'])
                        if record is not None:      # intro/limitations/reproduction are not records
                            records.append(record)
                provenance['blocks']=records
                provenance['composition']=composition_provenance(recipe,composition,records)
                scope=_resolved_scope(recipe,records)
                provenance['composition']['display_scope']=scope
                title,subtitle=_effective_titles(bundle,scope)
                if title:
                    provenance['composition']['effective_title']=title
                if subtitle:
                    provenance['composition']['effective_subtitle']=subtitle
            else:
                provenance['blocks']=[build_block(bundle,Path(bundle).parents[2],PROJECT)]
            write_json(Path(tmp)/'provenance.json',provenance)
        env = os.environ.copy()
        project = HERE.parents[1]
        env['HEALTH_REPORT_PROJECT'] = str(project)
        env['R_PROFILE_USER'] = str(project / '.Rprofile')
        for document in ['report','methods']:
            command = [quarto,'render',f'{document}.qmd','--to',fmt]
            if document == 'methods':
                command += ['-P', 'download_prefix:data/']
                if composition is not None and fmt == 'html':
                    # No PDF is generated beside this HTML-only package; do not offer one.
                    command += ['-P', 'html_only:true', '-M', 'format-links:false']
            if document == 'report' and provenance is not None:
                # Explicit absolute path: no working-directory lookup in the template.
                command += ['-P', f'evidence_file:{Path(tmp) / "provenance.json"}']
            if document == 'report' and composition is not None:
                command += ['-P', f'block_recipe:{Path(composition).resolve()}']
                if fmt == 'html':
                    # The composed report is HTML-only: suppress Quarto's alternate-format offer.
                    command += ['-M', 'format-links:false']
            subprocess.run(command,cwd=tmp,check=True,env=env)
        # Publish the pair only after both have rendered successfully.
        shutil.copyfile(Path(tmp)/f'report.{fmt}',output)
        shutil.copyfile(Path(tmp)/f'methods.{fmt}',output.parent/f'methods.{fmt}')
        if provenance is not None and provenance_out is not None:
            write_json(provenance_out,provenance)
        if fmt=='html':
            # The shared template links evidence as data/<name>; publish the exact saved
            # artifacts and verify the final folder, not the temporary render workspace.
            publish_evidence(bundle,output.parent/'data')
            if composition is not None:
                reproduction=output.parent/'reproduction'; reproduction.mkdir(exist_ok=True)
                shutil.copyfile(Path(composition),reproduction/'composition.json')
                # Same recorded wording as the methods page; never a separate claim.
                source_state=reproduction_source_state(provenance)
                write_json(reproduction/'reproduction.json',{
                    'entry_point':'python scripts/health_pipeline/publish.py batch',
                    'rendering_command':'python scripts/health_pipeline/publish.py html --bundle <published-saved-bundle>/data --output <output-dir>/report.html --provenance <output-dir>/provenance.json --composition <package>/reproduction/composition.json --data-root <original-snapshot-root>/snapshots/<snapshot-id> --workflow-config <retained-checkout>/workflow/config.yaml',
                    'placeholder_note':'Angle-bracketed values are required inputs to supply; they are not contained in this package.',
                    'required_inputs':['retained source checkout','published saved bundle (data/ files listed in bundle.json)','original snapshot root containing snapshots/<snapshot-id>','writable output directory'],
                    'original_analysis':{'retained_instructions':['README.md','GETTING_STARTED.md','Snakefile in the retained checkout'],'workflow_config':'workflow/config.yaml'},
                    'integrity_example':'verify data/ digests against bundle.json; inspection only, not production replay',
                    'recipe_file':'reproduction/composition.json',
                    'recipe_sha256':digest(composition),
                    'recipe_digest_note':'SHA-256 of the published file bytes; the source path digest in provenance is computed the same way.',
                    'snapshot_id':json.loads((Path(bundle)/'snapshot.json').read_text()).get('snapshot_id'),
                    'analysis_bundle_files':len(json.loads((Path(bundle)/'bundle.json').read_text()).get('files',{})),
                    'input_note':'Rendering needs the published saved bundle data/ files, a retained source checkout and the original snapshot root; raw snapshot exports are not part of this package.',
                    'environment_note':'Use the pinned composer-report container recorded in provenance/software; the image identifier does not by itself grant access.',
                    'source_state':f"{source_state['detail']} {source_state['availability']}",
                    'source_state_status':source_state['state'],
                    'source_availability':source_state['availability']})
            validate_published_evidence(output.parent)
        if recipe is not None and provenance is not None and recipe.get('contract')==COMPOSITION_CONTRACT_V2:
            failed=[r for r in provenance.get('blocks',[]) if r.get('status')!='verified']
            if failed:
                detail=lambda items: '; '.join(
                    f"{r.get('instance_id')}: {r.get('code','failed')} {r.get('detail','')}".strip()
                    for r in items)
                references=[r for r in failed if (r.get('component') or {}).get('type')=='reference-comparison']
                series=[r for r in failed if (r.get('component') or {}).get('type')=='series-trend']
                collections=[r for r in failed
                             if (r.get('component') or {}).get('type')=='series-collection']
                if references:
                    raise ValueError('Composed report has failed explicit reference binding(s): '
                                     + detail(references))
                if series:
                    raise ValueError('Composed report has failed series binding(s): ' + detail(series))
                if collections:
                    raise ValueError('Composed report has failed series collection binding(s): '
                                     + detail(collections))
                composites=[r for r in failed
                            if (r.get('component') or {}).get('type') in COMPOSITE_BLOCKS]
                if composites:
                    raise ValueError('Composed report has failed saved-record binding(s): '
                                     + detail(composites))
                raise ValueError('Composed report has failed block binding(s): ' + detail(failed))

BATCH_AUDIENCES=('researcher','health_institution','public')

def audience_bundle(bundle_root,audience):
    """Resolve one audience's retained bundle. Never fall back to another audience."""
    bundle=Path(bundle_root)/audience/'data'
    if not (bundle/'bundle.json').is_file():
        raise ValueError(f'No retained bundle for audience {audience!r} at {bundle}')
    stakeholder=bundle/'stakeholder.json'
    if not stakeholder.is_file():
        raise ValueError(f'Retained bundle for audience {audience!r} has no stakeholder.json')
    recorded=json.loads(stakeholder.read_text(encoding='utf-8')).get('id')
    if recorded!=audience:
        raise ValueError(f'Bundle audience {recorded!r} does not match requested audience {audience!r}')
    return bundle

def _workflow_record(path):
    if path and Path(path).is_file():
        return {'path':str(path),'sha256':digest(path)}
    return None

def render_composition_batch(bundle_root,recipes_root,output_root,quarto='quarto',data_root=None,
                             workflow_config=None,audiences=BATCH_AUDIENCES):
    """Render one composed HTML report per audience from that audience's own bundle and recipe.

    Every audience must resolve its own retained bundle and a recipe whose declared audience
    matches. Failures are collected so the batch can still report the other outcomes; the
    caller turns any failure into a nonzero exit instead of claiming a complete batch.
    """
    wf=_workflow_record(workflow_config)
    results=[]
    for audience in audiences:
        recipe=Path(recipes_root)/f'{audience}.json'
        try:
            if not recipe.is_file():
                raise ValueError(f'No composition recipe for audience {audience!r} at {recipe}')
            loaded=load_composition(recipe)
            if loaded.get('audience')!=audience:
                raise ValueError(f"Recipe audience {loaded.get('audience')!r} does not match requested audience {audience!r}")
            bundle=audience_bundle(bundle_root,audience)
            output=Path(output_root)/audience/'report.html'
            provenance_out=output.parent/'provenance.json'
            record=build_provenance(bundle,'html',quarto,data_root,wf)
            render(bundle,output,'html',quarto,record,provenance_out,recipe)
            results.append({'audience':audience,'status':'rendered',
                            'report':str(output),'provenance':str(provenance_out)})
        except Exception as exc:
            results.append({'audience':audience,'status':'failed','error':str(exc)})
    return results

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('action',choices=['package','html','pdf','batch'])
    ap.add_argument('--bundle'); ap.add_argument('--output'); ap.add_argument('--quarto',default='quarto')
    ap.add_argument('--provenance',help='Write a machine-readable provenance sidecar here and embed it in HTML')
    ap.add_argument('--data-root',help='Canonical input root recorded in provenance')
    ap.add_argument('--workflow-config',help='Workflow configuration file recorded in provenance')
    ap.add_argument('--composition',help='Block recipe JSON; omit for the legacy presentation')
    ap.add_argument('--bundle-root',help='Batch input root holding <audience>/data bundles')
    ap.add_argument('--recipes',default=str(HERE/'config/composer/compositions'),
                    help='Directory of <audience>.json composition recipes')
    ap.add_argument('--output-root',help='Batch output root; each audience writes <audience>/report.html')
    a=ap.parse_args(argv)
    if a.action=='batch':
        if not a.bundle_root or not a.output_root:
            ap.error('--bundle-root and --output-root are required for batch')
        results=render_composition_batch(a.bundle_root,a.recipes,a.output_root,a.quarto,
                                         a.data_root,a.workflow_config)
        for item in results:
            detail=f" -> {item['report']}" if item['status']=='rendered' else f" ({item['error']})"
            print(f"{item['audience']}: {item['status']}{detail}")
        failed=[item for item in results if item['status']!='rendered']
        if failed:
            raise SystemExit(f"{len(failed)} of {len(results)} composed reports failed: "
                             + ', '.join(item['audience'] for item in failed))
        return
    if not a.bundle or not a.output:
        ap.error('--bundle and --output are required')
    if a.action=='package': package(a.bundle,a.output)
    else:
        record=None
        if a.provenance:
            record=build_provenance(a.bundle,a.action,a.quarto,a.data_root,_workflow_record(a.workflow_config))
        render(a.bundle,a.output,a.action,a.quarto,record,a.provenance,a.composition)

if __name__=='__main__':
    main()
