"""Release documentation stays accurate, navigable and free of retired guidance."""
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / 'README.md', ROOT / 'RELEASE_NOTES.md', ROOT / 'CONTRIBUTING.md',
        *sorted((ROOT / 'docs').glob('*.md'))]
LINK = re.compile(r'(?<!\!)\[[^\]]+\]\(([^)\s]+)\)')
RETIRED = (
    'integration/steward-ready-v1',
    'ODESA-OpSciHack26',
    'm4-tabular',
    'pilot-rfree',
    'local-interface',
    'CONNECTOR_SETUP',
    'workflow-preservation-policy',
    'phase-6-ci-hardening',
)


def slug(heading):
    return re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-')


def anchors(path):
    return {slug(m.group(1)) for m in re.finditer(r'^#{1,6}\s+(.*)$', path.read_text(), re.M)}


def test_relative_links_and_anchors_resolve():
    errors = []
    for doc in DOCS:
        for target in LINK.findall(doc.read_text()):
            if re.match(r'[a-z]+:', target):
                continue
            path, _, fragment = target.partition('#')
            dest = (doc.parent / path).resolve() if path else doc
            if not dest.exists():
                errors.append(f'{doc.name}: {target}')
            elif fragment and dest.suffix == '.md' and fragment not in anchors(dest):
                errors.append(f'{doc.name}: missing anchor {target}')
    assert not errors, errors


def test_release_docs_contain_no_retired_guidance():
    """Retired routes and development branches must not come back as instructions."""
    errors = []
    for doc in DOCS:
        text = doc.read_text()
        for marker in RETIRED:
            if marker in text:
                errors.append(f'{doc.relative_to(ROOT)}: {marker}')
    assert not errors, errors


def test_release_documentation_set_is_lean():
    names = sorted(path.name for path in (ROOT / 'docs').glob('*.md'))
    assert names == [
        'composer.md',
        'installation.md',
        'limitations.md',
        'report-generation.md',
        'reproducibility.md',
        'troubleshooting.md',
    ], names
    assert not (ROOT / 'GETTING_STARTED.md').exists()
    assert not (ROOT / 'docs/README.md').exists()


def test_readme_documents_one_command_and_expected_outputs():
    readme = (ROOT / 'README.md').read_text()
    config = yaml.safe_load((ROOT / 'workflow/config.yaml').read_text())
    assert 'snakemake --cores 2' in readme and 'run_all.sh' in readme
    for sid in config['stakeholders']:
        assert f'results/reports/{sid}/report.html' in readme
    for required in ['docs/installation.md', 'docs/report-generation.md',
                     'docs/reproducibility.md', 'docs/troubleshooting.md',
                     'docs/limitations.md', 'CITATION.cff', 'data/README.md']:
        assert required in readme


def test_readme_states_r_rendering_and_release_candidate_identity():
    readme = (ROOT / 'README.md').read_text()
    assert 'R and Quarto' in readme
    assert 'release/composer-r' in readme
    assert 'LarsEBaumann/composer-sandbox' in readme
    assert 'not the final public distribution repository' in readme
    quick_start = readme.split('## Quick start', 1)[1].split('\n## ', 1)[0]
    commands = re.findall(r'^git clone (.+)$', quick_start, re.MULTILINE)
    assert commands == ['https://github.com/LarsEBaumann/composer-sandbox.git']


def test_citation_metadata_is_valid():
    cff = yaml.safe_load((ROOT / 'CITATION.cff').read_text())
    for key in ['cff-version', 'message', 'title', 'authors', 'repository-code', 'abstract']:
        assert cff.get(key), key
    assert cff['authors'] and cff['repository-code'].startswith('https://github.com/')
    assert any(r.get('type') == 'dataset' for r in cff['references'])


def test_data_terms_and_limitations_are_stated():
    data = (ROOT / 'data/README.md').read_text()
    assert 'source attribution' in data and 'Federal Office of Public Health' in data
    assert 'Data/' in data  # retired root remains documented
    limits = (ROOT / 'docs/limitations.md').read_text().lower()
    for topic in ['not infections', 'descriptive', 'influenza', 'national totals', 'revised', 'licence']:
        assert topic in limits, topic


def test_documented_headline_numbers_match_provenance_free_inputs():
    """Docs quote +124% / +21% / -3%; keep them tied to the audience smoke test."""
    smoke = (ROOT / 'tests/dashboard_smoke.R').read_text()
    docs = ((ROOT / 'docs/report-generation.md').read_text()
            + (ROOT / 'docs/limitations.md').read_text()).replace('\u2212', '-')
    for value in ['+124%', '+21%', '-3%']:
        assert value in smoke
        assert value in docs


def test_run_all_is_a_snakemake_wrapper_without_retired_paths(tmp_path):
    script = (ROOT / 'scripts/health_pipeline/run_all.sh').read_text()
    assert 'snakemake' in script and 'Data' not in script.replace('data_root', '')
    env = {
        'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin',
        'HOME': str(tmp_path),
        'XDG_CACHE_HOME': str(tmp_path / 'cache'),
    }
    out = subprocess.run(['bash', str(ROOT / 'scripts/health_pipeline/run_all.sh'), '', '', '--dry-run', '--forceall'],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr[-500:]
    for sid in yaml.safe_load((ROOT / 'workflow/config.yaml').read_text())['stakeholders']:
        assert f'results/reports/{sid}/report.html' in out.stdout
