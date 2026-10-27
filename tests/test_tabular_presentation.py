"""Presentation regression tests; numerical analysis is covered separately."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def presentation():
    if shutil.which('Rscript') is None:
        pytest.skip('R presentation test requires the report runtime')
    completed = subprocess.run(
        ['Rscript',str(ROOT/'tests/tabular_presentation_smoke.R'),str(ROOT)],
        capture_output=True,text=True,check=True,
    )
    return json.loads(completed.stdout)


def test_display_numbers_are_rounded_without_losing_small_nonzero_values(presentation):
    values = presentation['formatted']
    assert values['mean'] == '991.2'
    assert values['sd'] == '63.3'
    assert values['large'] == '18,496.3'
    assert values['integer'] == '6'
    assert values['missing'] == 'Not available'
    assert float(values['small']) != 0
    methods = presentation['views']['researcher_methods']
    assert '991.166666666667' not in methods
    assert '63.2531949127209' not in methods
    assert '991.2' in methods and '63.3' in methods
    assert '1,036.8' in methods
    assert 'Full precision is retained' in methods


def test_front_pages_have_distinct_structures(presentation):
    views = presentation['views']
    research = views['researcher_report']
    institution = views['health_institution_report']
    public = views['public_report']
    assert 'id="research-statistics"' in research
    assert 'id="monitoring-priorities"' not in research
    assert 'id="monitoring-priorities"' in institution
    assert 'class="monitor-grid"' in institution
    assert 'id="public-main-chart"' in public
    assert 'class="story-lead"' in public
    assert 'id="research-statistics"' not in public
    assert 'class="monitor-grid"' not in public


@pytest.mark.parametrize('audience',['researcher','health_institution','public'])
def test_navigation_and_coverage_are_readable(presentation,audience):
    for document in ['report','methods']:
        view = presentation['views'][f'{audience}_{document}']
        assert 'class="report-tabs"' in view
        assert 'Methods &amp; detailed statistics' in view
        assert 'class="report-footer"' in view
        assert 'aria-current="page"' in view
        assert 'color:#fff!important;opacity:1!important' in view
        assert 'position:sticky;top:0' in view
        assert 'Periods not represented in this supplied selection:' not in view
    methods = presentation['views'][f'{audience}_methods']
    assert '2020-01-01T00:00:00' not in methods
    assert '2020' in methods
    assert 'No value is assigned to those periods' in methods
