"""Freeze accepted CE suites; building alone does not submit anything."""
import argparse,hashlib,io,json,tarfile
from pathlib import Path
from control import ROOT,review,sha

p=argparse.ArgumentParser();p.add_argument('--experiment',choices=['X2','X3'],required=True);a=p.parse_args();exp=a.experiment
checked=review();slug=f'supplement-20261101-{exp.lower()}-ce-formal-v13'
config=f'configs/{exp}_CE_resolved_v2.json';approval=json.loads((ROOT/exp/'ACCEPTED_CE.json').read_text())
assert approval['task_sha256']==checked['task_sha256'] and approval['decision']=='ACCEPTED'
plan=dict(id=slug,experiment=exp,stage='FORMAL',scope='CE_ONLY',bundles=32,wall_minutes=2,config=config)
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
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B ce_suite.py --config __CONFIG__ --phase formal --bundle "$SLURM_ARRAY_TASK_ID"
'''.replace('__NAME__',slug).replace('__CONFIG__',config).encode()
files=['engine.py','formal_driver.py','ce_suite.py',config,exp+'/ACCEPTED_CE.json','tools/submit_pilot_remote.py','tools/submit_ce_suite_formal.py']
contents={name:(ROOT/name).read_bytes() for name in files}
contents.update({'job_plan.json':(json.dumps(plan,indent=2)+'\n').encode(),'slurm/run.sbatch':shell})
hashes={name:hashlib.sha256(payload).hexdigest() for name,payload in contents.items()}
contents['SHA256SUMS']=''.join(h+'  '+name+'\n' for name,h in hashes.items()).encode()
archive=ROOT/'packages'/(slug+'.tar.gz');assert not archive.exists()
with tarfile.open(archive,'w:gz') as tf:
    for name,payload in contents.items():
        info=tarfile.TarInfo(name);info.size=len(payload);tf.addfile(info,io.BytesIO(payload))
manifest=dict(name=slug,archive=str(archive),archive_sha256=sha(archive),source_hashes=hashes,plan=plan)
(ROOT/'packages'/(slug+'.manifest.json')).write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
print(json.dumps(manifest,indent=2))
