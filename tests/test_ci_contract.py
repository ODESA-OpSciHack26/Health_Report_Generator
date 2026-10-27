"""CI gates are structurally enforced."""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / '.github/workflows').glob('*.yml'))


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'))


def test_every_action_is_pinned_to_a_commit_sha():
    for path in WORKFLOWS:
        for ref in re.findall(r'uses:\s*(\S+)', path.read_text(encoding='utf-8')):
            assert re.fullmatch(r'[\w.-]+/[\w./-]+@[0-9a-f]{40}', ref), f'{path.name}: {ref}'


def test_dependabot_updates_github_actions():
    config = yaml.safe_load((ROOT / '.github/dependabot.yml').read_text(encoding='utf-8'))
    assert any(u['package-ecosystem'] == 'github-actions' for u in config['updates'])


def test_validate_has_fast_and_full_gates_on_push_and_pr():
    wf = workflow('validate.yml')
    triggers = wf.get('on', wf.get(True))  # PyYAML parses bare `on` as True
    assert 'push' in triggers and 'pull_request' in triggers
    jobs = wf['jobs']
    assert {'fast', 'container', 'full'} <= set(jobs)
    assert jobs['full']['needs'] == 'fast' and jobs['container']['needs'] == 'fast'
    fast = ' '.join(s.get('run', '') for s in jobs['fast']['steps'])
    for command in ['ruff check', 'pytest', 'snakemake --dry-run']:
        assert command in fast


@pytest.mark.parametrize('name,job', [('validate.yml', 'full'), ('refresh-idd-data.yml', 'refresh')])
def test_artifacts_are_uploaded_only_after_all_verification(name, job):
    steps = workflow(name)['jobs'][job]['steps']
    upload = next(i for i, s in enumerate(steps) if 'upload-artifact' in s.get('uses', ''))
    runs = [s.get('run', '') for s in steps[:upload]]
    for gate in ['snakemake --cores 2', 'results/site/researcher.html', 'results/site/public_health.html']:
        assert any(gate in r for r in runs), f'{name}: {gate} must precede upload'
    assert all('continue-on-error' not in s for s in steps)


def test_lint_is_pinned():
    assert re.fullmatch(r'ruff==\d+\.\d+\.\d+\n', (ROOT / 'scripts/ci/requirements-lint.txt').read_text(encoding='utf-8'))
    assert '[tool.ruff.lint]' in (ROOT / 'pyproject.toml').read_text(encoding='utf-8')


def test_no_r_toolchain_remains():
    """The reports are Python + Quarto only; R, renv and TinyTeX are gone everywhere."""
    for path in [*WORKFLOWS, ROOT / 'Dockerfile.report', ROOT / 'compose.yaml', ROOT / 'Snakefile']:
        text = path.read_text(encoding='utf-8').lower()
        for word in ['rscript', 'renv', 'tinytex', 'setup-r', 'rocker/']:
            assert word not in text, f'{path.name}: {word}'
