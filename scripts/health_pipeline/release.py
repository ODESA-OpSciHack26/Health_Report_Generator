"""Record artifacts, exact code/config hashes, and the actual build environment.

Source identity is resolved through the shared ``source_identity`` module: an explicitly
supplied record is verified against the declared execution inputs and any defect fails
the release instead of downgrading to "unknown". Git fields keep their observed-at-runtime
meaning; the host-reported revision appears only in the additive ``source_identity`` block.
"""
import argparse
import importlib.metadata
import platform
import subprocess
from pathlib import Path

import source_identity
from common import digest, write_json


def command(args):
    try: return subprocess.check_output(args,stderr=subprocess.STDOUT,text=True).strip()
    except (OSError,subprocess.CalledProcessError): return 'unavailable'


def build_release(out, quarto='quarto', source_identity_path=None):
    out = Path(out)
    project = Path.cwd()
    identity = source_identity.resolve(project, source_identity_path)
    artifacts=[p for p in out.rglob('*') if p.is_file() and 'snapshots' not in p.parts and p.name!='release.json']
    source=[p for root in [Path('scripts/health_pipeline'),Path('workflow'),Path('tests')] for p in root.rglob('*') if p.is_file() and not any(x in p.parts for x in ['example_output','__pycache__','.pytest_cache']) and p.suffix not in ['.pyc'] and p.name!='.DS_Store']
    source += [Path('Snakefile'),Path('renv.lock'),Path('.Rprofile')]
    observed_commit = source_identity.observe_commit(project)
    observed_status = source_identity.observe_status(project, include_untracked=True)
    record = {'schema_version':'2.0',
        'git_commit':observed_commit or 'unavailable',
        'git_status':'unavailable' if observed_status is None else observed_status,
        'source_identity':identity,
        'python':platform.python_version(),'platform':platform.platform(),
        'tex':command([quarto,'list','tools']), 'quarto':command([quarto,'--version']),'R':command(['Rscript','-e','sessionInfo()']),
        'r_packages':command(['Rscript','-e','for(p in c("shiny","knitr","rmarkdown","jsonlite","digest")) cat(p,as.character(packageVersion(p)),"\\n")']),
        'python_packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
        'code':{str(p):digest(p) for p in sorted(source)},
        'artifacts':{p.relative_to(out).as_posix():digest(p) for p in sorted(artifacts)}}
    # Before writing the manifest, confirm the inputs still hash to the recorded digest.
    source_identity.assert_unchanged(identity, project)
    write_json(out/'release.json', record)
    return record


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--quarto',default='quarto')
    ap.add_argument('--source-identity',help='Host-collected source-identity record (JSON)')
    a=ap.parse_args()
    build_release(a.out, a.quarto, a.source_identity)
