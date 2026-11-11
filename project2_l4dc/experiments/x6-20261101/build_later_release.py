"""Concrete FORMAL/REPORT release builder, usable only after exact acceptance.

Preparation itself uses only stdlib and does not submit. Numerical analysis
sources are frozen with FORMAL so REPORT cannot change the registered analysis
silently. Read the complete current review log before invoking this helper.
"""
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
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['FORMAL','REPORT'],required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--exact-accepted-quote',required=True)
    parser.add_argument('--exact-protocol-accepted-quote',required=True)
    parser.add_argument('--resource-plan',required=True,type=Path)
    parser.add_argument('--formal-manifest',type=Path)
    parser.add_argument('--report-version',default='v1')
    a=parser.parse_args()
    assert re.fullmatch(r'x6-20261101-a-(formal|report)-v\d+',a.name)
    assert re.fullmatch(r'v\d+',a.report_version)
    review=(ROOT.parents[1]/'CLAUDE_TASK.md').read_bytes()
    latest=review.decode('utf-8-sig')
    for quote in [a.exact_accepted_quote,a.exact_protocol_accepted_quote]:
        assert 'X6a' in quote and 'ACCEPTED' in quote and quote in latest
    resource=json.loads(a.resource_plan.read_text(encoding='utf-8-sig'))
    assert resource['status']=='RESOURCE_COMPLETE_FORMAL_PROPOSAL_NOT_SUBMITTED'
    minutes=resource['proposed_formal_wall_minutes'] if a.stage=='FORMAL' else 60
    assert 1<=minutes<=30 if a.stage=='FORMAL' else minutes==60
    contents={name:(ROOT/name).read_bytes() for name in [
        'frozen_engine.py','estimation.py','prepare_protocol.py','config-X6a-v1.json',
        'PROTOCOL_X6a_v1.md','remote_ops.py','accounting.py','analyze_saved.py',
        'plot_saved.py','verify_saved.py']}
    if a.stage=='REPORT':
        assert a.formal_manifest is not None
        formal=json.loads(a.formal_manifest.read_text(encoding='utf-8-sig'))
        assert formal['plan']['stage']=='FORMAL'
        for name in ['analyze_saved.py','estimation.py','config-X6a-v1.json','frozen_engine.py']:
            assert formal['hashes'][name]==sha(contents[name]),'Analysis/source changed since FORMAL.'
    protocol=(ROOT/'SHA256SUMS').read_bytes()
    for line in protocol.decode().splitlines():
        digest,name=line.split('  ',1)
        assert sha(contents[name])==digest
    contents['PROTOCOL_SHA256SUMS']=protocol
    contents['CLAUDE_TASK_approved.md']=review
    contents['resource_plan.json']=a.resource_plan.read_bytes()
    approval=dict(experiment='X6a',accepted_stage='PILOT' if a.stage=='FORMAL' else 'FORMAL',
        exact_quote=a.exact_accepted_quote,protocol_exact_quote=a.exact_protocol_accepted_quote,
        task_sha256=sha(review),protocol_manifest_sha256=sha(protocol))
    contents['approval.json']=(json.dumps(approval,indent=2)+'\n').encode()
    tasks=40 if a.stage=='FORMAL' else 1
    plan=dict(id=a.name,experiment='X6a',stage=a.stage,tasks=tasks,concurrency=min(32,tasks),
              cpus=1,memory_MiB=2048,wall_minutes=minutes,requested_bound_SU=tasks*minutes/60)
    contents['job_plan.json']=(json.dumps(plan,indent=2)+'\n').encode()
    invocation=('estimation.py formal --config config-X6a-v1.json --out '
                '"$base/results/x6-20261101/X6a" --index "$SLURM_ARRAY_TASK_ID"')
    if a.stage=='REPORT':
        invocation=('analyze_saved.py --config config-X6a-v1.json --raw '
                    '"$base/results/x6-20261101/X6a" --out '
                    '"$base/results/x6-20261101/X6a/reports/'+a.report_version+'"')
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
"$python" -B __INVOCATION__
'''.replace('__NAME__',a.name).replace('__INVOCATION__',invocation).encode()
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
