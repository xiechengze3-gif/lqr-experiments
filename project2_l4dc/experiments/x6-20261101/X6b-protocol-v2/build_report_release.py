"""Prepare conditional REPORT release using the exact accepted science sources."""
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
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--prepared',type=Path,required=True)
    p.add_argument('--complete-proof',type=Path,required=True);p.add_argument('--exact-accepted-quote',required=True)
    a=p.parse_args();assert re.fullmatch(r'x6-20261101-b-report-v\d+',a.name)
    channel=ROOT.parents[2];review=(channel/'CLAUDE_TASK.md').read_bytes();text=review.decode('utf-8-sig')
    quote=a.exact_accepted_quote
    assert quote in text and 'X6b' in quote and 'ACCEPTED' in quote
    assert 'After all arrays complete, run' in text and 'the frozen REPORT' in text
    config_payload=(a.prepared/'formal-config.json').read_bytes();config=json.loads(config_payload)
    proof_payload=a.complete_proof.read_bytes();proof=json.loads(proof_payload)
    assert proof['status']=='COMPLETE_COVERAGE_COUNTS_SOURCES' and proof['config_sha256']==sha(config_payload)
    assert proof['counts']['tasks']==384 and proof['counts']['paired_paths']==1024
    jobs=[dict(component=f'diagnostics-n{n}',n=n,mode='inspect',cpus=1,memory_MiB=2048,tasks=1,
               wall_minutes=90,requested_bound_SU=1.5) for n in config['n_values']]
    jobs.append(dict(component='summary',n=None,mode='summarize',cpus=1,memory_MiB=2048,tasks=1,
                     wall_minutes=30,requested_bound_SU=.5))
    assert sum(j['requested_bound_SU'] for j in jobs)==6.5
    files={}
    for name,value in config['scientific_sources'].items():
        files[name]=(ROOT/name).read_bytes();assert sha(files[name])==value
    for model in config['model_registry'].values():
        files[model['path']]=(a.prepared/model['path']).read_bytes();assert sha(files[model['path']])==model['sha256']
    for name in ['remote_ops.py','submit_report.py','build_report_release.py','transfer_x6b.py','transfer_x6b_v2.py']:
        files[name]=(ROOT/name).read_bytes()
    files['formal-config.json']=config_payload;files['FORMAL_COMPLETE_v1.json']=proof_payload
    files['CLAUDE_TASK_approved.md']=review
    approved=dict(experiment='X6b',authorized_action='X6b REPORT_AFTER_COMPLETE',exact_quote=quote,
        task_sha256=sha(review),formal_config_sha256=sha(config_payload),formal_complete_sha256=sha(proof_payload))
    files['approval.json']=(json.dumps(approved,indent=2)+'\n').encode()
    files['report-plan.json']=(json.dumps(dict(experiment='X6b',stage='REPORT',jobs=jobs,
        zero_new_transitions=True,requested_bound_SU=6.5,automatic_retries=0),indent=2)+'\n').encode()
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
py=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
case "$1" in
  diagnostics-n24|diagnostics-n36|diagnostics-n48|diagnostics-n72)
    n=${1#diagnostics-n}
    "$py" -B analyze_actor.py inspect --config formal-config.json --raw "$base/results/x6-20261101/X6b/formal-v1" --out "$base/results/x6-20261101/X6b/report-v1/diagnostics-n$n" --n "$n"
    ;;
  summary)
    "$py" -B analyze_actor.py summarize --config formal-config.json --raw "$base/results/x6-20261101/X6b/report-v1" --out "$base/results/x6-20261101/X6b/report-v1/summary"
    "$py" -B transfer_x6b_v2.py pack --root "$base/results/x6-20261101" --scope formal --archive "$base/tmp/x6-20261101/x6b-formal-v1.tar.gz"
    "$py" -B transfer_x6b_v2.py pack --root "$base/results/x6-20261101" --scope report --archive "$base/tmp/x6-20261101/x6b-report-v1.tar.gz"
    ;;
  *) echo 'Unregistered report component' >&2; exit 2 ;;
esac
'''.replace('__NAME__',a.name).encode()
    assert b'\r' not in shell;files['run-report.sbatch']=shell
    hashes={name:sha(payload) for name,payload in files.items()}
    files['SHA256SUMS']=''.join(f'{value}  {name}\n' for name,value in hashes.items()).encode()
    directory=ROOT/'packages';archive=directory/(a.name+'.tar.gz');assert not archive.exists()
    with tarfile.open(archive,'w:gz') as tf:
        for name,payload in files.items():
            info=tarfile.TarInfo(name);info.size=len(payload);tf.addfile(info,io.BytesIO(payload))
    result=dict(status='BUILT_AFTER_FORMAL_COMPLETE',name=a.name,archive=str(archive),
                archive_sha256=sha(archive.read_bytes()),approval=approved,hashes=hashes)
    (directory/(a.name+'.manifest.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
