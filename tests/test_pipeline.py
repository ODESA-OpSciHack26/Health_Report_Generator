"""Data steps behind the reports: inventory -> harmonise -> checks -> CSV, and the render entry points."""
import ast
import json, shutil, subprocess, sys
from pathlib import Path
import pandas as pd
import pytest
import yaml
from harmonise import main as harmonise
from inventory import verify
from checks import validate
from common import verify_gate
from export_csv import export
import render_quarto
ROOT=Path(__file__).resolve().parents[1]
YEARS=[2019,2021,2022,2023,2024,2025]

@pytest.fixture
def project(tmp_path):
    raw=tmp_path/'raw'; out=tmp_path/'out'
    for topic,scale in [('virus',1),('bacterium',2)]:
        p=raw/topic;p.mkdir(parents=True)
        meta={'metaVariables':{'topic':topic,'source':'mandatory_reporting_system','valueCategory':{'column':'valueCategory'}},
              'temporalVariables':{'column':'temporal','typeColumn':'temporal_type'},
              'groupingVariables':{'georegion':{'column':'georegion','typeColumn':'georegion_type','allValue':'all'},'sex':{'column':'sex','allValue':'all'}},
              'valueVariables':{'value':{},'pop':{}},'entryVariables':{'dataComplete':{}}}
        (p/'metadata.json').write_text(json.dumps(meta), encoding='utf-8')
        pd.DataFrame([dict(valueCategory='cases',temporal=str(y),temporal_type='year',georegion='CHFL',georegion_type='CHFL',sex='all',value=(y-2009)*scale,pop=100000,dataComplete='TRUE') for y in YEARS]).to_csv(p/'data.csv',index=False)
    return raw,out

def run(project):
    raw,out=project
    harmonise([str(raw),'--out',str(out)]);validate(out)
    return out

def edit_csv(project,fn,topic='virus'):
    p=project[0]/topic/'data.csv';fn(pd.read_csv(p)).to_csv(p,index=False)

def test_harmonised_values_match_raw_exports(project):
    d=pd.read_parquet(run(project)/'harmonised.parquet')
    virus=d[(d.topic=='virus')&(d.period=='2025')]
    assert virus.value.tolist()==[16]
    assert set(d.topic)=={'virus','bacterium'}

def test_women_only_never_total(project):
    edit_csv(project,lambda d:d.assign(sex='female'))
    d=pd.read_parquet(run(project)/'harmonised.parquet');assert not d[d.topic=='virus'].is_total.any()

@pytest.mark.parametrize('damage',['negative','duplicate','invalid_date','invalid_value','missing_metadata','truncated_metadata','dropped_sex'])
def test_bad_input_blocks_gate(project,damage):
    raw,out=project
    if damage.endswith('metadata'):
        p=raw/'virus/metadata.json'
        if damage=='missing_metadata':p.unlink()
        else:p.write_text('{"broken":', encoding='utf-8')
    else:
        def change(d):
            if damage=='duplicate':return pd.concat([d,d.iloc[:1]])
            if damage=='dropped_sex':return d.drop(columns='sex')
            col='temporal' if damage=='invalid_date' else 'value';d[col]=d[col].astype(object)
            d.loc[0,col]={'negative':-1,'invalid_date':'not-a-date','invalid_value':'oops'}[damage];return d
        edit_csv(project,change)
    harmonise([str(raw),'--out',str(out)])
    with pytest.raises(ValueError,match='blocking'):validate(out)
    assert not (out/'validated.json').exists()

def test_failure_removes_old_success_marker(project):
    out=run(project);d=pd.read_parquet(out/'harmonised.parquet');d.loc[0,'value']=-10;d.to_parquet(out/'harmonised.parquet',index=False)
    with pytest.raises(ValueError):validate(out)
    assert not (out/'validated.json').exists()

def test_stale_gate_is_rejected(project):
    out=run(project);p=out/'checks.csv';p.write_text(p.read_text(encoding='utf-8')+'\n')
    with pytest.raises(ValueError,match='stale'):verify_gate(out)

def test_conflicting_metadata_not_deduplicated(project):
    raw,out=project;shutil.copytree(raw/'virus',raw/'copy')
    p=raw/'copy/metadata.json';m=json.loads(p.read_text(encoding='utf-8'));m['metaVariables']['topic']='another';p.write_text(json.dumps(m), encoding='utf-8')
    harmonise([str(raw),'--out',str(out)])
    with pytest.raises(ValueError,match='blocking'):validate(out)
    assert (pd.read_csv(out/'datasets.csv').status=='ok').sum()==3

def test_exact_duplicates_skipped(project):
    shutil.copytree(project[0]/'virus',project[0]/'copy');out=run(project)
    assert (pd.read_csv(out/'datasets.csv').status=='duplicate_skipped').sum()==1

def test_snapshot_relocation_and_tamper_detection(project,tmp_path):
    out=run(project);copy=tmp_path/'moved';shutil.copytree(out,copy)
    root,m=verify(copy/'snapshot.json');assert root.exists()
    p=root/m['files'][0]['path'];p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(ValueError,match='checksum'):verify(copy/'snapshot.json')

def test_repeatable_harmonised_table_from_snapshot(project,tmp_path):
    first=run(project);other=tmp_path/'second'
    harmonise(['--snapshot',str(first/'snapshot.json'),'--out',str(other)]);validate(other)
    pd.testing.assert_frame_equal(pd.read_parquet(first/'harmonised.parquet'),pd.read_parquet(other/'harmonised.parquet'))
    assert (first/'checks.csv').read_bytes()==(other/'checks.csv').read_bytes()

def test_checks_cli_exit_code(project):
    out=run(project);d=pd.read_parquet(out/'harmonised.parquet');d.loc[0,'value']=-1;d.to_parquet(out/'harmonised.parquet')
    p=subprocess.run([sys.executable,str(ROOT/'scripts/health_pipeline/checks.py'),'--out',str(out)],capture_output=True)
    assert p.returncode!=0

def test_csv_export_matches_parquet(project):
    out=run(project);export(out)
    csv,parquet=pd.read_csv(out/'harmonised.csv',dtype={'period':str}),pd.read_parquet(out/'harmonised.parquet')
    assert list(csv.columns)==list(parquet.columns) and len(csv)==len(parquet)
    assert csv.period.tolist()==parquet.period.tolist() and csv.value.tolist()==parquet.value.tolist()

def test_render_refuses_missing_pipeline_outputs(tmp_path):
    with pytest.raises(SystemExit,match='missing pipeline outputs'):
        render_quarto.render('researcher',tmp_path,tmp_path/'site/researcher.html')
    with pytest.raises(SystemExit,match='no such report'):
        render_quarto.render('unknown',tmp_path,tmp_path/'site/unknown.html')

def test_configured_reports_exist():
    reports=yaml.safe_load((ROOT/'workflow/config.yaml').read_text(encoding='utf-8'))['reports']
    assert reports and all((ROOT/'reports'/f'{name}.qmd').is_file() for name in reports)
    assert set(reports)<=set(render_quarto.reports())

def test_app_disease_list_matches_report_helpers():
    """src/app.py reads the disease list without importing helpers.py; both must agree."""
    tree=ast.parse((ROOT/'reports/utils/helpers.py').read_text(encoding='utf-8'))
    names=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id','')=='ALL_DISEASES')
    app=(ROOT/'src/app.py').read_text(encoding='utf-8')
    assert 'ALL_DISEASES' in app and 'reports" / "utils" / "helpers.py' in app
    assert len(names)>=12
