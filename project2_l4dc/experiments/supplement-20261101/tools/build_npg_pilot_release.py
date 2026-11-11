"""Freeze bounded dense-only NPG pilot arrays before submitting."""
import argparse,hashlib,io,json,tarfile
from control import ROOT,review,sha

p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--name',required=True);p.add_argument('--minutes',required=True,type=int);a=p.parse_args()
review();cfg=json.loads((ROOT/a.config).read_text());assert cfg['phase']=='PILOT' and 1<=a.minutes<=60
plan=dict(id=a.name,stage='PILOT',scope='DENSE_ONLY_NPG_QUALIFICATION',experiment=cfg['experiment'],config=a.config,
          bundles=len(cfg['pilot_systems'])*len(cfg['pilot_trials']),wall_minutes=a.minutes,resource_proof='budget/NPG_resource_pilot_v1.json')
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
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B npg_pilot_suite.py --config __CONFIG__ --bundle "$SLURM_ARRAY_TASK_ID"
'''.replace('__NAME__',a.name).replace('__CONFIG__',a.config).encode()
names=['engine.py','npg_multi.py','npg_pilot_suite.py',a.config,'tools/submit_pilot_remote.py','tools/submit_npg_pilot_v15.py']
contents={name:(ROOT/name).read_bytes() for name in names}
contents.update({'job_plan.json':(json.dumps(plan,indent=2)+'\n').encode(),'slurm/run.sbatch':shell})
hashes={name:hashlib.sha256(payload).hexdigest() for name,payload in contents.items()}
contents['SHA256SUMS']=''.join(h+'  '+name+'\n' for name,h in hashes.items()).encode()
archive=ROOT/'packages'/(a.name+'.tar.gz');assert not archive.exists()
with tarfile.open(archive,'w:gz') as tf:
    for name,payload in contents.items():
        info=tarfile.TarInfo(name);info.size=len(payload);tf.addfile(info,io.BytesIO(payload))
manifest=dict(name=a.name,archive=str(archive),archive_sha256=sha(archive),plan=plan,source_hashes=hashes)
(ROOT/'packages'/(a.name+'.manifest.json')).write_bytes((json.dumps(manifest,indent=2)+'\n').encode());print(json.dumps(manifest,indent=2))
