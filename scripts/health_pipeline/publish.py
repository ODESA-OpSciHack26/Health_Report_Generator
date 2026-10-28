"""Package and render verified analysis bundles without recalculating statistics."""
import argparse
import csv
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
        'code':{'git_commit':git_commit,'git_worktree_clean':None if git_status is None else git_status=='',
                'workflow_config':workflow_config},
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
            'presentation':{'unit':'percent'},'disclosure':{'distribution':'public'}}
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
                                'sha256':digest(PROJECT/'scripts/health_pipeline/templates/report_helpers.R')}},
            'reproduction':{'entry_point':'snakemake --cores 2',
                            'snapshot_id':loaded.snapshot['snapshot_id']}}
        checked=contracts.check_block(instance,evidence,loaded,
                                      project_root=project_root,results_root=results_root)
    except contracts.ContractError as exc:
        return {'status':'failed','instance_id':instance_id,'code':exc.code,'detail':str(exc),
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

KNOWN_BLOCKS = ('intro','reference-comparison','limitations','reproduction')
COMPOSITION_CONTRACT = 'health-report/composition-recipe/1'
COMPOSITION_CONTRACT_V2 = 'health-report/composition-recipe/2'
TOPIC_ID = re.compile(r'[a-z0-9][a-z0-9_-]*')

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
        if set(entry) != expected:
            raise ValueError(f'Invalid fields for block {block!r}: expected {sorted(expected)}')
        if contract == COMPOSITION_CONTRACT_V2 and block == 'reference-comparison':
            topic = entry['topic']
            if not isinstance(topic, str) or not TOPIC_ID.fullmatch(topic):
                raise ValueError(f'Invalid topic id for block instance {instance!r}: {topic!r}')
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
    return recipe

def composition_provenance(recipe, path, blocks):
    """Record the recipe and the checked instance identity behind every block entry."""
    checked = {record['instance_id']: record for record in blocks}
    instances = []
    for entry in recipe['blocks']:
        instance = {'block': entry['block'], 'instance_id': entry['instance_id']}
        record = checked.get(entry['instance_id']) if entry['block'] == 'reference-comparison' else None
        if record is not None:
            instance['topic'] = entry.get('topic')
            instance['binding'] = 'explicit' if entry.get('topic') else 'deterministic'
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
                # same value the R renderer uses for its DOM identity.
                records=[build_block(bundle,Path(bundle).parents[2],PROJECT,entry['instance_id'],entry.get('topic'))
                         for entry in recipe['blocks'] if entry['block']=='reference-comparison']
                provenance['blocks']=records
                provenance['composition']=composition_provenance(recipe,composition,records)
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
            validate_published_evidence(output.parent)
        if recipe is not None and provenance is not None and recipe.get('contract')==COMPOSITION_CONTRACT_V2:
            failed=[r for r in provenance.get('blocks',[]) if r.get('status')!='verified']
            if failed:
                detail='; '.join(f"{r.get('instance_id')}: {r.get('code','failed')} {r.get('detail','')}".strip() for r in failed)
                raise ValueError(f'Composed report has failed explicit reference binding(s): {detail}')

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
