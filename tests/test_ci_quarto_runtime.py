"""Contract tests for the R-free pilot's exact quarto_runtime enforcement.

The pilot job must fail unless the eight reviewed node IDs executed exactly once each with no
skips, failures or errors. A set-only comparison passes a duplicated complete set, so the
duplicate cases below are the regression that motivated this check.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'ci' / 'check_quarto_runtime.py'
SPEC = importlib.util.spec_from_file_location('check_quarto_runtime', SCRIPT)
assert SPEC is not None and SPEC.loader is not None
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

EXPECTED = sorted(check.EXPECTED)


def _report(path, cases):
    parts = ['<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" ']
    parts.append(f'tests="{len(cases)}">')
    for case in cases:
        parts.append(case)
    parts.append('</testsuite></testsuites>')
    path.write_text(''.join(parts), encoding='utf-8')
    return path


def _case(identifier, outcome=None):
    module, _, name = identifier.partition('::')
    classname = module[:-3].replace('/', '.')
    body = ''
    if outcome == 'skipped':
        body = '<skipped message="not today" />'
    elif outcome == 'failure':
        body = '<failure message="boom" />'
    elif outcome == 'error':
        body = '<error message="boom" />'
    return f'<testcase classname="{classname}" name="{name}" time="0.1">{body}</testcase>'


def _run(tmp_path, cases, argv=()):
    report = _report(tmp_path / 'report.xml', cases)
    return check.main([str(report), *argv])


def test_exact_reviewed_set_passes(tmp_path, capsys):
    assert _run(tmp_path, [_case(identifier) for identifier in EXPECTED]) == 0
    assert 'QUARTO_RUNTIME_ENFORCEMENT_OK' in capsys.readouterr().out


def test_missing_id_fails(tmp_path, capsys):
    cases = [_case(identifier) for identifier in EXPECTED[:-1]]
    assert _run(tmp_path, cases) == 1
    output = capsys.readouterr().out
    assert 'missing node IDs' in output and EXPECTED[-1] in output


def test_unexpected_id_fails(tmp_path, capsys):
    cases = [_case(identifier) for identifier in EXPECTED]
    cases.append(_case('tests/test_pilot_figures.py::test_new_unreviewed_case'))
    assert _run(tmp_path, cases) == 1
    assert 'unexpected node IDs' in capsys.readouterr().out


def test_all_expected_plus_one_duplicate_fails(tmp_path, capsys):
    cases = [_case(identifier) for identifier in EXPECTED]
    cases.append(_case(EXPECTED[0]))
    assert _run(tmp_path, cases) == 1
    output = capsys.readouterr().out
    assert 'duplicate node IDs' in output and EXPECTED[0] in output


def test_duplicated_complete_set_fails(tmp_path, capsys):
    cases = [_case(identifier) for identifier in EXPECTED]
    cases += [_case(identifier) for identifier in EXPECTED]
    assert _run(tmp_path, cases) == 1
    output = capsys.readouterr().out
    assert 'duplicate node IDs' in output
    assert f'expected {len(EXPECTED)} testcase records, found {2 * len(EXPECTED)}' in output


@pytest.mark.parametrize('outcome', ['skipped', 'failure', 'error'])
def test_disallowed_outcome_fails(tmp_path, outcome, capsys):
    cases = [_case(identifier) for identifier in EXPECTED]
    cases[-1] = _case(EXPECTED[-1], outcome=outcome)
    assert _run(tmp_path, cases) == 1
    assert 'QUARTO_RUNTIME_ENFORCEMENT_FAILED' in capsys.readouterr().out


def test_absent_report_fails_closed(tmp_path, capsys):
    assert check.main([str(tmp_path / 'absent.xml')]) == 1
    assert 'ENFORCEMENT_ERROR' in capsys.readouterr().out


def test_malformed_report_fails_closed(tmp_path, capsys):
    broken = tmp_path / 'broken.xml'
    broken.write_text('<testsuite><testcase', encoding='utf-8')
    assert check.main([str(broken)]) == 1
    assert 'ENFORCEMENT_ERROR' in capsys.readouterr().out


def test_collection_level_record_fails(tmp_path, capsys):
    cases = [_case(identifier) for identifier in EXPECTED]
    cases.append('<testcase classname="" name="tests.test_pilot_fonts">'
                 '<skipped message="no fontTools" /></testcase>')
    assert _run(tmp_path, cases) == 1
    output = capsys.readouterr().out
    assert 'malformed records' in output
