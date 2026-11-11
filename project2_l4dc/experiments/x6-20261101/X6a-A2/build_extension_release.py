"""Local stdlib release builder after exact X6b design-job acceptance."""
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
    p=argparse.ArgumentParser();p.add_argument('--name',required=True)
    p.add_argument('--exact-accepted-quote',required=True);a=p.parse_args()
    assert re.fullmatch(r'x6-20261101-a-calibration-v\d+',a.name)
    task=next(parent/'CLAUDE_TASK.md' for parent in ROOT.parents if (parent/'CLAUDE_TASK.md').exists())
    review=task.read_bytes();quote=a.exact_accepted_quote
    assert 'X6a' in quote and 'ACCEPTED' in quote and quote in review.decode('utf-8-sig')
    protocol=(ROOT/'SHA256SUMS').read_bytes()
    for line in protocol.decode().splitlines():
        expected,name=line.split('  ',1);assert sha((ROOT/name).read_bytes())==expected
    names=['frozen_engine.py','estimation.py','extension_only.py','extension_core.py','build_extension_release.py','remote_ops.py',
           'submit_extension.py','PROTOCOL.md','config-X6a-A2.json','X6a-calibration.csv']
    files={name:(ROOT/name).read_bytes() for name in names}
    files['PROTOCOL_SHA256SUMS']=protocol;files['CLAUDE_TASK_approved.md']=review
    approval=dict(experiment='X6a',accepted_stage='REPORT',exact_quote=quote,
        task_sha256=sha(review),protocol_manifest_sha256=sha(protocol))
    files['approval.json']=(json.dumps(approval,indent=2)+'\n').encode()
    plan=dict(id=a.name,experiment='X6a',stage='CALIBRATION_EXTENSION',tasks=1,
              cpus=1,memory_MiB=2048,wall_minutes=10,requested_bound_SU=1/6)
    files['job_plan.json']=(json.dumps(plan,indent=2)+'\n').encode()
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
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B extension_only.py --config config-X6a-A2.json --out "$base/results/x6-20261101/X6a/calibration-A2"
'''.replace('__NAME__',a.name).encode()
    assert b'\r' not in shell;files['run.sbatch']=shell
    hashes={name:sha(payload) for name,payload in files.items()}
    files['SHA256SUMS']=''.join(f'{digest}  {name}\n' for name,digest in hashes.items()).encode()
    folder=ROOT/'packages';folder.mkdir(exist_ok=True)
    archive=folder/(a.name+'.tar.gz');assert not archive.exists()
    with tarfile.open(archive,'w:gz') as tf:
        for name,payload in files.items():
            info=tarfile.TarInfo(name);info.size=len(payload);tf.addfile(info,io.BytesIO(payload))
    manifest=dict(name=a.name,archive=str(archive),archive_sha256=sha(archive.read_bytes()),
                  plan=plan,approval=approval,hashes=hashes)
    (folder/(a.name+'.manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest))


if __name__=='__main__':main()
