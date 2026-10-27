"""Hand-calculated statistics, explicit comparisons and gap-safe line segments."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/health_pipeline'))
from tabular_prepare import prepare_payload  # noqa: E402
from tabular_describe import describe, normalize_report_options  # noqa: E402
from test_tabular_render import fake_quarto as _fake_quarto  # noqa: E402

fake_quarto = _fake_quarto


def prepare(text):
    return prepare_payload(text.encode(),source_filename='input.csv',
        mapping={'category':'category','measure':'value','time':'year'},mode='timeseries',period='year')


def test_hand_calculated_statistics_and_comparison():
    data=prepare('category,value,year\nA,1,2019\nA,2,2021\nA,3,2022\nA,4,2023\n')
    result=describe(data,{'reference_period':'2019-01-01','latest_period':'2023-01-01'})
    stats=result['category_statistics'][0]
    assert stats['mean']==2.5 and stats['median']==2.5
    assert stats['q1']==1.75 and stats['q3']==3.25
    assert stats['sd']==pytest.approx(1.2909944487358056)
    comparison=result['comparisons'][0]
    assert comparison['difference']==3 and comparison['percent']==300
    assert comparison['source_rows']==[1,4]
    assert result['unrepresented_calendar_periods']==['2020-01-01T00:00:00']
    rows=result['plot_rows']
    assert rows[0]['segment']!=rows[1]['segment']
    assert rows[1]['segment']==rows[2]['segment']==rows[3]['segment']
    assert sum(item['count'] for item in result['histogram'])==4


def test_missing_and_zero_baseline_are_not_replaced():
    result=describe(prepare('category,value,year\nA,0,2019\nA,10,2025\nB,,2019\nB,2,2025\n'),
                    {'reference_period':'2019-01-01','latest_period':'2025-01-01'})
    assert result['overview']['missing_values']==1
    assert result['comparisons'][0]['difference']==10
    assert result['comparisons'][0]['percent'] is None
    assert result['comparisons'][1]['eligible'] is False
    assert result['category_statistics'][1]['n']==1
    assert result['category_statistics'][1]['sd'] is None


def test_repeated_period_values_are_not_pooled_or_connected():
    result=describe(prepare('category,value,year\nA,1,2019\nA,2,2019\nA,3,2025\n'),
                    {'reference_period':'2019-01-01','latest_period':'2025-01-01'})
    assert result['comparisons'][0]['eligible'] is False
    assert result['comparisons'][0]['percent'] is None
    assert all(not row['line_allowed'] for row in result['plot_rows'])
    assert result['overview']['rows']==3


@pytest.mark.parametrize('options',[{'unknown':1},{'max_categories':True},{'reference_period':'2019-01-01'},
    {'reference_period':'bad','latest_period':'2025-01-01'},{'max_categories':0},{'unit':''}])
def test_invalid_options_rejected(options):
    with pytest.raises(ValueError):
        normalize_report_options(options)


def test_missing_requested_period_rejected():
    with pytest.raises(ValueError,match='must exist'):
        describe(prepare('category,value,year\nA,1,2021\n'),
                 {'reference_period':'2019-01-01','latest_period':'2025-01-01'})


def test_no_implicit_comparisons_and_all_categories_retained():
    result=describe(prepare('category,value,year\nA,1,2021\nB,2,2021\n'),{'max_categories':1})
    assert result['comparisons']==[]
    assert len(result['category_statistics'])==2
    assert result['chart_categories']==['A']


def test_rehashed_false_analysis_is_rejected(tmp_path, fake_quarto):
    import json
    import tabular_render as renderer
    from tabular_bundle import publish_prepared_bundle
    prepared=prepare('category,value,year\nA,1,2021\nA,2,2022\n')
    source=publish_prepared_bundle(prepared,tmp_path/'input')
    output=renderer.render_tabular_reports(source,tmp_path/'output')
    path=output/'analysis.json'
    result=json.loads(path.read_text())
    result['overview']['rows']=999
    path.write_bytes(renderer.bundles._json_bytes(result))
    manifest=json.loads((output/'render_manifest.json').read_text())
    manifest['artifacts']['analysis.json']={'bytes':path.stat().st_size,'sha256':renderer._hash(path)}
    (output/'render_manifest.json').write_bytes(renderer.bundles._json_bytes(manifest))
    with pytest.raises(ValueError,match='independently reproduced'):
        renderer.verify_tabular_reports(output)


def test_version_two_request_keeps_explicit_labels_and_periods(tmp_path):
    import hashlib
    import json
    from tabular_run import load_request
    payload=b'category,value,year\nA,1,2019\nA,2,2025\n'
    request={'schema':'health-report/tabular-request/2',
        'source_sha256':hashlib.sha256(payload).hexdigest(),
        'mapping':{'category':'category','measure':'value','time':'year'},
        'mode':'timeseries','period':'year',
        'report':{'unit':'cases','reference_period':'2019-01-01','latest_period':'2025-01-01'}}
    path=tmp_path/'request.json'
    path.write_text(json.dumps(request))
    loaded=load_request(path)
    assert loaded['report']['unit']=='cases'
    assert loaded['report']['reference_period']=='2019-01-01T00:00:00'
    request['report']=None
    path.write_text(json.dumps(request))
    with pytest.raises(ValueError,match='must be an object'):
        load_request(path)
