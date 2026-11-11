"""Build immutable per-component resource packages after accepted R2 resolution."""
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
    p.add_argument('--component',required=True);p.add_argument('--exact-accepted-quote',required=True)
    a=p.parse_args();assert re.fullmatch(r'x6-20261101-b-resource-[a-z0-9-]+-v\d+',a.name)
    task=next(parent/'CLAUDE_TASK.md' for parent in ROOT.parents if (parent/'CLAUDE_TASK.md').exists())
    review=task.read_bytes();quote=a.exact_accepted_quote
    assert 'ACCEPTED' in quote and 'X6b' in quote and quote in review.decode('utf-8-sig')
    files={};protocol=(ROOT/'SHA256SUMS').read_bytes()
    for line in protocol.decode().splitlines():
        digest,name=line.split('  ',1);payload=(ROOT/name).read_bytes()
        assert sha(payload)==digest;files[name]=payload
    resource=json.loads((ROOT/'resolved-v1/resource-plan.json').read_text())
    assert resource['status']=='WITHIN_PROPOSED_RESOURCE_CAP' and resource['requested_bound_SU']<=4
    component=next(j for j in resource['jobs'] if j['component']==a.component)
    resolved=(ROOT/'resolved-v1/resolved-config.json').read_bytes()
    assert sha(resolved)==resource['resolved_config_sha256']
    config=json.loads(resolved);population=(ROOT/'population.json').read_bytes()
    assert sha(population)==config['population_result_sha256']
    for name in ['submit_resource.py','build_resource_release.py','resolve_population.py']:
        files[name]=(ROOT/name).read_bytes()
    files.update({'PROTOCOL_SHA256SUMS':protocol,'CLAUDE_TASK_approved.md':review,
                  'resolved-config.json':resolved,'population.json':population,
                  'resource-plan.json':(ROOT/'resolved-v1/resource-plan.json').read_bytes()})
    approval=dict(experiment='X6b',accepted_stage='PROTOCOL',exact_quote=quote,
                  task_sha256=sha(review),protocol_manifest_sha256=sha(protocol))
    files['approval.json']=(json.dumps(approval,indent=2)+'\n').encode()
    plan=dict(id=a.name,experiment='X6b',stage='PILOT',tasks=1,**component)
    files['job_plan.json']=(json.dumps(plan,indent=2)+'\n').encode()
    nflag='' if component['n'] is None else ' --n '+str(component['n'])
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
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B resource_actor.py --config resolved-config.json --out "$base/results/x6-20261101/X6b/resource-v1/__COMPONENT__"__NFLAG__
'''.replace('__NAME__',a.name).replace('__COMPONENT__',a.component).replace('__NFLAG__',nflag).encode()
    assert b'\r' not in shell;files['run.sbatch']=shell
    hashes={name:sha(payload) for name,payload in files.items()}
    files['SHA256SUMS']=''.join(f'{v}  {k}\n' for k,v in hashes.items()).encode()
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
