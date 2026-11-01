"""Release documentation contract: one entry point, supported surface only, no unsafe guidance."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_FILES = ['installation.md', 'composer.md', 'report-generation.md',
             'reproducibility.md', 'troubleshooting.md', 'limitations.md']


def text(name):
    return (ROOT / 'docs' / name).read_text()


def test_installation_is_the_single_setup_entry_point():
    setup = text('installation.md')
    assert 'workflow/toolchain.json' in setup
    assert 'docker compose build report' in setup
    assert setup.count('## ') >= 3
    readme = (ROOT / 'README.md').read_text()
    assert 'docs/installation.md' in readme
    assert '## Quick start' in readme
    assert '## Quick start' not in setup  # one quick start, not competing guides


def test_docs_state_r_rendering_and_the_route_output_matrix():
    generation = text('report-generation.md')
    assert 'R and Quarto' in generation
    for audience in ('researcher', 'health_institution', 'public'):
        assert audience in generation
    assert '| Route | Entry point | HTML | PDF | Shiny app |' in generation
    assert 'HTML-only' in generation


def test_reproducibility_names_versions_provenance_and_verification():
    reproducibility = text('reproducibility.md')
    for required in ('workflow/toolchain.json', 'requirements.lock.txt', 'renv.lock',
                     'snapshot_manifest', 'provenance', 'verify_release.py',
                     'source_identity.py', 'evidence_archive.py'):
        assert required in reproducibility, required


def test_troubleshooting_covers_unsupported_renderer_and_identity_failures():
    troubleshooting = text('troubleshooting.md')
    assert 'invalid choice' in troubleshooting
    assert 'source_identity' in troubleshooting
    assert 'never falls back' in troubleshooting


def test_docs_do_not_instruct_publication_or_tagging():
    for name in DOC_FILES:
        for line in text(name).splitlines():
            assert not re.match(r'^\s*git (?:tag|push)\b', line), (name, line)
            assert not re.match(r'^\s*gh release\b', line), (name, line)


def test_only_the_sandbox_repository_is_named():
    for path in [ROOT / 'README.md', ROOT / 'CONTRIBUTING.md', ROOT / 'RELEASE_NOTES.md',
                 *(ROOT / 'docs').glob('*.md')]:
        content = path.read_text()
        assert 'Health_Report_Generator.git' not in content
        assert 'steward-ready' not in content


def test_docs_keep_uncertainty_and_licence_boundaries():
    limits = (ROOT / 'docs/limitations.md').read_text().lower()
    assert 'descriptive' in limits and 'influenza' in limits
    assert (ROOT / 'LICENSE').read_text().startswith('MIT License')
    assert 'does not license the source data' in (ROOT / 'data/README.md').read_text()
