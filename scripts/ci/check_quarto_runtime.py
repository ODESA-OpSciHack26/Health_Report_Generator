"""Fail closed unless the R-free pilot executed exactly the reviewed quarto_runtime tests.

The pilot job renders eight reviewed node IDs in an R-free image. Counting testcases is not
enough: a set comparison hides duplicates, and a missing ID can be masked by an extra one.
This check works on the emitted record list and reports missing, unexpected and duplicate IDs
separately, rejects skipped, failed and errored testcases, and fails closed when the report is
absent or malformed.
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter

EXPECTED = frozenset({
    'tests/test_pilot_figures.py::test_real_quarto_restores_multiple_figures_and_shows_intermediate_placeholders',
    'tests/test_pilot_figures.py::test_caller_does_not_publish_when_restoration_fails',
    'tests/test_pilot_render_structure.py::test_table_scroll_ends_at_table_and_details_survive[researcher-report-2]',
    'tests/test_pilot_render_structure.py::test_table_scroll_ends_at_table_and_details_survive[public-report-4]',
    'tests/test_pilot_render_structure.py::test_methods_tables_are_balanced_and_have_no_details',
    'tests/test_tabular_python_render.py::test_python_generation_through_documented_cli',
    'tests/test_tabular_python_render.py::test_v2_integrity_rejects_tampered_artifact_without_source_check',
    'tests/test_tabular_python_render.py::test_invalid_identity_fails_before_rendering',
})

DEFAULT_REPORT = '/app/rfree-quarto-runtime.xml'


class QuartoRuntimeReportError(Exception):
    """Raised for an absent, unreadable or malformed JUnit report."""


def node_id(case):
    """Normalized 'path::test[param]' id for one testcase record, or None when malformed."""
    classname = (case.get('classname') or '').strip()
    name = (case.get('name') or '').strip()
    if not classname or not name:
        return None
    return classname.replace('.', '/') + '.py::' + name


def inspect(xml_path):
    """Return (evidence, problems); problems is empty only for the reviewed exact set."""
    try:
        root = ET.parse(xml_path).getroot()
    except (OSError, ET.ParseError) as error:
        raise QuartoRuntimeReportError(f'cannot read JUnit report {xml_path}: {error}') from error
    records = root.findall('.//testcase')
    ids, malformed = [], []
    for case in records:
        identifier = node_id(case)
        if identifier is None:
            malformed.append(
                f'classname={case.get("classname")!r} name={case.get("name")!r}')
        else:
            ids.append(identifier)
    counts = Counter(ids)
    evidence = {
        'records': len(records),
        'ids': ids,
        'duplicates': sorted(key for key, count in counts.items() if count > 1),
        'missing': sorted(EXPECTED - set(ids)),
        'unexpected': sorted(set(ids) - EXPECTED),
        'malformed': malformed,
        'skipped': [node_id(case) or repr(case.get('name')) for case in records
                    if case.find('skipped') is not None],
        'failed': [node_id(case) or repr(case.get('name')) for case in records
                   if case.find('failure') is not None or case.find('error') is not None],
    }
    problems = []
    if malformed:
        problems.append(f'malformed records ({len(malformed)}): {malformed}')
    if evidence['duplicates']:
        problems.append(f'duplicate node IDs: {evidence["duplicates"]}')
    if evidence['missing']:
        problems.append(f'missing node IDs: {evidence["missing"]}')
    if evidence['unexpected']:
        problems.append(f'unexpected node IDs: {evidence["unexpected"]}')
    if len(records) != len(EXPECTED):
        problems.append(f'expected {len(EXPECTED)} testcase records, found {len(records)}')
    if evidence['skipped']:
        problems.append(f'skipped testcases are not allowed: {evidence["skipped"]}')
    if evidence['failed']:
        problems.append(f'failed or errored testcases: {evidence["failed"]}')
    return evidence, problems


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else DEFAULT_REPORT
    try:
        evidence, problems = inspect(path)
    except QuartoRuntimeReportError as error:
        print(f'QUARTO_RUNTIME_ENFORCEMENT_ERROR {error}')
        return 1
    print('QUARTO_RUNTIME_RECORDS', evidence['records'])
    for identifier in sorted(evidence['ids']):
        print('  QUARTO_RUNTIME_CASE', identifier)
    if problems:
        for problem in problems:
            print(f'QUARTO_RUNTIME_PROBLEM {problem}')
        print('QUARTO_RUNTIME_ENFORCEMENT_FAILED')
        return 1
    print('QUARTO_RUNTIME_ENFORCEMENT_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
