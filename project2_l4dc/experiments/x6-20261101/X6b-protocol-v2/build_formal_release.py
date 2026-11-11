"""Build an immutable X6b FORMAL release only after explicit acceptance."""
import argparse
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True)
    p.add_argument('--prepared',type=Path,required=True);p.add_argument('--exact-accepted-quote',required=True)
    a=p.parse_args();assert re.fullmatch(r'x6-20261101-b-formal-v\d+',a.name)
    task=next(parent/'CLAUDE_TASK.md' for parent in ROOT.parents if (parent/'CLAUDE_TASK.md').exists())
    review=task.read_bytes();quote=a.exact_accepted_quote
    assert 'X6b' in quote and 'ACCEPTED' in quote and quote in review.decode('utf-8-sig')
    plan=json.loads((a.prepared/'formal-plan.json').read_text())
    config_payload=(a.prepared/'formal-config.json').read_bytes();config=json.loads(config_payload)
    assert sha(config_payload)==plan['formal_config_sha256'] and config['status']=='FORMAL_FROZEN'
    assert plan['total_requested_with_report_SU']<=400 and plan['retries']==0
    files={}
    for name,digest in config['scientific_sources'].items():
        files[name]=(ROOT/name).read_bytes();assert sha(files[name])==digest
    for entry in config['model_registry'].values():
        files[entry['path']]=(a.prepared/entry['path']).read_bytes()
        assert sha(files[entry['path']])==entry['sha256']
    for name in ['submit_formal.py','build_formal_release.py','remote_ops.py','transfer_x6b.py','validate_formal_complete.py']:
        files[name]=(ROOT/name).read_bytes()
    for name in ['formal-config.json','formal-plan.json','measured-costs.csv']:
        files[name]=(a.prepared/name).read_bytes()
    files['PROTOCOL.md']=(ROOT/'PROTOCOL.md').read_bytes()
    files['PROTOCOL_SHA256SUMS']=(ROOT/'SHA256SUMS').read_bytes()
    files['PROTOCOL_CONFIG.json']=(ROOT/'config-X6b-protocol-v2.json').read_bytes()
    assert sha(files['PROTOCOL_CONFIG.json'])==config['protocol_config_sha256']
    files['resolved-config.json']=(ROOT/'resolved-v1/resolved-config.json').read_bytes()
    files['population.json']=(ROOT/'population.json').read_bytes()
    assert sha(files['population.json'])==config['population_result_sha256']
    files['CLAUDE_TASK_approved.md']=review
    approved=dict(experiment='X6b',authorized_action='X6b FORMAL',exact_quote=quote,
                  task_sha256=sha(review),formal_config_sha256=sha(config_payload))
    files['approval.json']=(json.dumps(approved,indent=2)+'\n').encode()
    shell='''#!/usr/bin/env bash
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/__NAME__
cache=$base/cache/x6-20261101
temp=$base/tmp/x6-20261101/job-${SLURM_ARRAY_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B formal_driver.py --config formal-config.json --group "$1" --index "$SLURM_ARRAY_TASK_ID" --out "$base/results/x6-20261101/X6b/formal-v1"
'''.replace('__NAME__',a.name).encode()
    assert b'\r' not in shell;files['run.sbatch']=shell
    hashes={name:sha(data) for name,data in files.items()}
    files['SHA256SUMS']=''.join(f'{digest}  {name}\n' for name,digest in hashes.items()).encode()
    directory=ROOT/'packages';directory.mkdir(exist_ok=True)
    archive=directory/(a.name+'.tar.gz');assert not archive.exists()
    with tarfile.open(archive,'w:gz') as tf:
        for name,data in files.items():
            member=tarfile.TarInfo(name);member.size=len(data);tf.addfile(member,io.BytesIO(data))
    manifest=dict(status='BUILT_AFTER_ACCEPTANCE',name=a.name,archive=str(archive),
                  archive_sha256=sha(archive.read_bytes()),approval=approved,hashes=hashes)
    (directory/(a.name+'.manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest))


if __name__=='__main__':main()
