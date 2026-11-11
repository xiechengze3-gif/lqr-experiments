"""Freeze dense-qualified NPG plans; all methods have identical per-arm schedules."""
import argparse,hashlib,io,json,tarfile
from control import ROOT,review,sha

p=argparse.ArgumentParser();p.add_argument('--experiment',choices=['X2','X3'],required=True);p.add_argument('--minutes',type=int,required=True)
p.add_argument('--partition',choices=['short','medium'],required=True);p.add_argument('--concurrency',type=int,default=16);a=p.parse_args()
checked=review();exp=a.experiment;slug=f'supplement-20261101-{exp.lower()}-npg-formal-v18';config=f'configs/{exp}_NPG_formal_v1.json'
approval=json.loads((ROOT/exp/'ACCEPTED_NPG.json').read_text())
assert approval['task_sha256']==checked['task_sha256'] and approval['decision']=='ACCEPTED_CONDITIONS_SATISFIED'
assert 1<=a.concurrency<=32 and 1<=a.minutes<=360 and (a.partition!='short' or a.minutes<=120)
plan=dict(id=slug,experiment=exp,stage='FORMAL',scope='NPG',config=config,bundles=32,wall_minutes=a.minutes,partition=a.partition,concurrency=a.concurrency)
shell='''#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
release=/scratch/user/changze/lqr_experiments/releases/__NAME__
base=/scratch/user/changze/lqr_experiments
cache=$base/cache/supplement-20261101
temp=$base/tmp/supplement-20261101/job-${SLURM_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B npg_formal_suite.py --config __CONFIG__ --bundle "$SLURM_ARRAY_TASK_ID"
'''.replace('__NAME__',slug).replace('__CONFIG__',config).encode()
names=['engine.py','npg_multi.py','npg_formal_suite.py',config,exp+'/ACCEPTED_NPG.json','tools/submit_pilot_remote.py','tools/submit_npg_formal.py']
contents={name:(ROOT/name).read_bytes() for name in names}
contents.update({'job_plan.json':(json.dumps(plan,indent=2)+'\n').encode(),'slurm/run.sbatch':shell})
hashes={name:hashlib.sha256(payload).hexdigest() for name,payload in contents.items()}
contents['SHA256SUMS']=''.join(h+'  '+name+'\n' for name,h in hashes.items()).encode()
archive=ROOT/'packages'/(slug+'.tar.gz');assert not archive.exists()
with tarfile.open(archive,'w:gz') as tf:
    for name,payload in contents.items():
        info=tarfile.TarInfo(name);info.size=len(payload);tf.addfile(info,io.BytesIO(payload))
manifest=dict(name=slug,archive=str(archive),archive_sha256=sha(archive),source_hashes=hashes,plan=plan)
(ROOT/'packages'/(slug+'.manifest.json')).write_bytes((json.dumps(manifest,indent=2)+'\n').encode());print(json.dumps(manifest,indent=2))
