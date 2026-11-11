"""Build after explicit protocol acceptance; no upload or submission."""
import argparse
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def sha(payload):return hashlib.sha256(payload).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--name',required=True)
    p.add_argument('--exact-accepted-quote',required=True)
    a=p.parse_args()
    assert re.fullmatch(r'x6-20261101-a-resource-v\d+',a.name)
    task=ROOT.parents[1]/'CLAUDE_TASK.md'
    review=task.read_bytes();quote=a.exact_accepted_quote
    assert 'ACCEPTED' in quote and 'X6a' in quote
    assert quote in review.decode('utf-8-sig')
    # The caller must read the complete latest review, not merely match a token.
    contents={name:(ROOT/name).read_bytes() for name in [
        'frozen_engine.py','estimation.py','config-X6a-v1.json',
        'PROTOCOL_X6a_v1.md','prepare_protocol.py','remote_ops.py','accounting.py']}
    protocol_manifest=(ROOT/'SHA256SUMS').read_bytes()
    for line in protocol_manifest.decode().splitlines():
        digest,name=line.split('  ',1)
        assert sha((ROOT/name).read_bytes())==digest
    contents['PROTOCOL_SHA256SUMS']=protocol_manifest
    contents['CLAUDE_TASK_approved.md']=review
    approval=dict(experiment='X6a',accepted_stage='PROTOCOL',exact_quote=quote,
                  task_sha256=sha(review),protocol_manifest_sha256=sha(protocol_manifest))
    contents['approval.json']=(json.dumps(approval,indent=2)+'\n').encode()
    plan=dict(id=a.name,experiment='X6a',stage='PILOT',tasks=8,concurrency=8,
              cpus=1,memory_MiB=2048,wall_minutes=15,requested_bound_SU=2.)
    contents['job_plan.json']=(json.dumps(plan,indent=2)+'\n').encode()
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
python=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python" -B estimation.py resource --config config-X6a-v1.json --out "$base/results/x6-20261101/X6a" --index "$SLURM_ARRAY_TASK_ID"
'''.replace('__NAME__',a.name).encode()
    assert b'\r' not in shell
    contents['run.sbatch']=shell
    hashes={name:sha(payload) for name,payload in contents.items()}
    contents['SHA256SUMS']=''.join(f'{digest}  {name}\n' for name,digest in hashes.items()).encode()
    folder=ROOT/'packages';folder.mkdir(exist_ok=True)
    archive=folder/(a.name+'.tar.gz');assert not archive.exists()
    with tarfile.open(archive,'w:gz') as tf:
        for name,payload in contents.items():
            info=tarfile.TarInfo(name);info.size=len(payload)
            tf.addfile(info,io.BytesIO(payload))
    manifest=dict(name=a.name,archive=str(archive),archive_sha256=sha(archive.read_bytes()),
                  plan=plan,approval=approval,hashes=hashes)
    (folder/(a.name+'.manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest))


if __name__=='__main__':main()
