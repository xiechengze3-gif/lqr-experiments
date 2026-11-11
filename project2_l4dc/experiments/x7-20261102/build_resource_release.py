"""Build only after explicit X7 protocol ACCEPTED;stdlib-only."""
import argparse,hashlib,io,json,re,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CHANNEL=ROOT.parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name',required=True)
    parser.add_argument('--exact-accepted-quote',required=True);args=parser.parse_args()
    assert re.fullmatch(r'x7-20261102-resource-v\d+',args.name)
    manifest=json.loads((ROOT/'PROTOCOL_MANIFEST.json').read_text())
    assert manifest['status']=='PROTOCOL_FROZEN_WAITING_ACCEPTED'
    for name,digest in manifest['files'].items():assert sha((ROOT/name).read_bytes())==digest,name
    task=(CHANNEL/'CLAUDE_TASK.md').read_bytes();quote=args.exact_accepted_quote
    assert quote in task.decode('utf-8-sig') and all(word in quote for word in ['X7','PROTOCOL','ACCEPTED'])
    config=(ROOT/'config-protocol-v1.json').read_bytes()
    approval=dict(experiment='X7',authorized_action='X7_RESOURCE_PILOT',exact_quote=quote,
        task_sha256=sha(task),config_sha256=sha(config),
        protocol_manifest_sha256=sha((ROOT/'PROTOCOL_MANIFEST.json').read_bytes()))
    plan=dict(stage='PILOT',tasks=4,concurrency=4,cpus=1,memory_MiB=2048,
        wall_minutes=15,requested_bound_SU=1.,automatic_retries=0,resource_only=True)
    files={name:(ROOT/name).read_bytes() for name in manifest['files']}
    for name in ['PROTOCOL_MANIFEST.json','x7_resource_ops.py','build_resource_release.py',
                 'complete_resource.py','prepare_formal.py','accounting_x7.py']:
        files[name]=(ROOT/name).read_bytes()
    files['PROTOCOL_SHA256SUMS']=(ROOT/'SHA256SUMS').read_bytes()
    files['CLAUDE_TASK_approved.md']=task
    files['approval.json']=(json.dumps(approval,indent=2)+'\n').encode()
    files['resource-plan.json']=(json.dumps(plan,indent=2)+'\n').encode()
    shell='''#!/usr/bin/env bash
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/__NAME__
cache=$base/cache/x7-20261102
temp=$base/tmp/x7-20261102/job-${SLURM_ARRAY_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B x7_driver.py resource --config config-protocol-v1.json --index "${SLURM_ARRAY_TASK_ID:?}"
'''.replace('__NAME__',args.name).encode()
    assert b'\r' not in shell;files['run-resource.sbatch']=shell
    hashes={name:sha(payload) for name,payload in files.items()}
    files['SHA256SUMS']=''.join(f'{value}  {name}\n' for name,value in hashes.items()).encode()
    folder=ROOT/'packages';folder.mkdir(exist_ok=True)
    archive=folder/(args.name+'.tar.gz');assert not archive.exists()
    with tarfile.open(archive,'w:gz') as tf:
        for name,payload in files.items():
            info=tarfile.TarInfo(name);info.size=len(payload);tf.addfile(info,io.BytesIO(payload))
    result=dict(status='BUILT_AFTER_PROTOCOL_ACCEPTED',name=args.name,archive=str(archive),
        archive_sha256=sha(archive.read_bytes()),hashes=hashes,approval=approval,plan=plan)
    (folder/(args.name+'.manifest.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
