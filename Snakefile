from pathlib import Path
import shutil
import sys

# Raw FOPH exports -> snapshot -> one cleaned table -> quality checks -> Quarto reports.
# `snakemake --cores 2` builds every report in config `reports` into <out>/site/.
configfile: 'workflow/config.yaml'
P = 'scripts/health_pipeline'
sys.path.insert(0, str(Path(P).resolve()))
from common import digest, object_hash
OUT = config['out'].rstrip('/')
PYTHON = sys.executable
SITE = OUT + '/site'
REPORTS = list(config['reports'])
DATA_ROOT = config['data_root'] if not config.get('snapshot_manifest') else ''
ENVIRONMENT = [f'{P}/requirements.lock.txt', 'reports/utils/requirements.txt']
# Everything a report reads besides its own .qmd; render_quarto.py copies reports/utils next to it.
REPORT_CODE = sorted(str(p) for p in Path('reports/utils').iterdir()
                     if p.is_file() and p.name not in ('index.html', 'requirements.txt')) + [f'{P}/render_quarto.py']

for name in REPORTS:
    if not Path(f'reports/{name}.qmd').exists():
        raise ValueError(f'config reports lists {name}, but reports/{name}.qmd does not exist')

HTML = expand(SITE + '/{report}.html', report=REPORTS)
PROVENANCE = expand(SITE + '/provenance_{report}.json', report=REPORTS)

rule all:
    input: HTML, PROVENANCE, SITE + '/index.html'

if not config.get('snapshot_manifest'):
    ROOT = Path(config['data_root'])
    RAW = sorted({str(p) for csv in ROOT.rglob('data.csv') for p in [csv,*csv.parent.glob('*.json')]})
    if not RAW:
        raise ValueError(f'No raw datasets in {ROOT}; set data_root or snapshot_manifest')
    ENTRIES = [{'path':Path(p).relative_to(ROOT).as_posix(),'sha256':digest(p),'bytes':Path(p).stat().st_size} for p in RAW]
    SID = object_hash(ENTRIES)
    ARCHIVED = [f'{OUT}/snapshots/{SID}/'+e['path'] for e in ENTRIES]
    SNAPSHOT = OUT+'/snapshot.json'
    rule inventory:
        input: raw=RAW, code=[f'{P}/inventory.py',f'{P}/common.py']
        output: manifest=SNAPSHOT, archived=ARCHIVED, archive_manifest=f'{OUT}/snapshots/{SID}/manifest.json'
        params: root=str(ROOT), out=OUT
        shell: '{PYTHON:q} {P}/inventory.py {params.root:q} --out {params.out:q}'
else:
    SNAPSHOT = config['snapshot_manifest']
    from inventory import verify
    ARCHIVE_ROOT, MANIFEST = verify(SNAPSHOT)
    ARCHIVED = [str(ARCHIVE_ROOT/f['path']) for f in MANIFEST['files']]

rule harmonise:
    input: snapshot=SNAPSHOT, archive=ARCHIVED, code=[f'{P}/harmonise.py',f'{P}/common.py',f'{P}/inventory.py'], env=ENVIRONMENT
    output: parquet=OUT+'/harmonised.parquet', datasets=OUT+'/datasets.csv', roles=OUT+'/role_log.csv', manifest=OUT+'/harmonised_snapshot.json'
    params: out=OUT
    shell: '{PYTHON:q} {P}/harmonise.py --snapshot {input.snapshot:q} --out {params.out:q}'

rule validate:
    input: parquet=OUT+'/harmonised.parquet', datasets=OUT+'/datasets.csv', manifest=OUT+'/harmonised_snapshot.json', code=[f'{P}/checks.py',f'{P}/common.py'], env=ENVIRONMENT
    output: checks=OUT+'/checks.csv', gate=OUT+'/validated.json'
    params: out=OUT
    shell: '{PYTHON:q} {P}/checks.py --out {params.out:q}'

# The reports read the cleaned table as CSV and publish its checksum in their
# Provenance section; harmonise.py writes Parquet, so the CSV is derived here.
rule harmonised_csv:
    input: parquet=OUT+'/harmonised.parquet', gate=OUT+'/validated.json', code=[f'{P}/export_csv.py'], env=ENVIRONMENT
    output: OUT+'/harmonised.csv'
    params: out=OUT
    shell: '{PYTHON:q} {P}/export_csv.py --out {params.out:q}'

# The gate stops a report from being built on a table that has not passed checks.py.
rule report:
    input: cleaned=OUT+'/harmonised.csv', snapshot=OUT+'/harmonised_snapshot.json', datasets=OUT+'/datasets.csv',
           checks=OUT+'/checks.csv', gate=OUT+'/validated.json', qmd='reports/{report}.qmd', code=REPORT_CODE, env=ENVIRONMENT
    output: html=SITE+'/{report}.html', provenance=SITE+'/provenance_{report}.json'
    wildcard_constraints: report='|'.join(REPORTS)
    params: results=OUT, data_root=DATA_ROOT or config.get('snapshot_manifest')
    shell: '{PYTHON:q} {P}/render_quarto.py --report {wildcards.report:q} --results {params.results:q} '
           '--output {output.html:q} --data-root {params.data_root:q}'

# The landing page links to the reports by file name, so it is published only once they all exist.
rule landing:
    input: page='reports/utils/index.html', reports=HTML
    output: SITE+'/index.html'
    run:
        shutil.copyfile(input.page, output[0])
