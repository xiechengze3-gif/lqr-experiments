"""Build a new immutable LF-safe PILOT/REPORT release; no formal dispatch."""
import argparse,hashlib,io,json,re,tarfile
from pathlib import Path
from control import ROOT

p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--script',required=True)
p.add_argument('--stage',choices=['PILOT','REPORT'],required=True);p.add_argument('--experiment',required=True)
p.add_argument('--scope',required=True);p.add_argument('--minutes',type=int,required=True)
p.add_argument('--include',action='append',default=[]);p.add_argument('--bundles',type=int,default=1);a=p.parse_args()
assert re.fullmatch('[a-z0-9-]+',a.name) and re.fullmatch(r'[a-z0-9_]+\.py',a.script)
assert all(not Path(s).is_absolute() and '..' not in Path(s).parts for s in a.include)
assert 1<=a.minutes<=30 and 1<=a.bundles<=8
folder=ROOT/'packages';folder.mkdir(exist_ok=True);archive=folder/(a.name+'.tar.gz');assert not archive.exists()
plan=dict(id=a.name,stage=a.stage,experiment=a.experiment,scope=a.scope,wall_minutes=a.minutes,bundles=a.bundles)
plan_bytes=(json.dumps(plan,indent=2)+'\n').encode()
shell='''#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
release=/scratch/user/changze/lqr_experiments/releases/__NAME__
base=/scratch/user/changze/lqr_experiments
cache=$base/cache/supplement-20261101
temp=$base/tmp/supplement-20261101/job-${SLURM_JOB_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B __SCRIPT__
'''.replace('__NAME__',a.name).replace('__SCRIPT__',a.script).encode()
submit='tools/submit_aux_array_remote.py' if a.bundles>1 else 'tools/submit_aux_remote.py'
contents={s:(ROOT/s).read_bytes() for s in ['engine.py',a.script,'tools/submit_pilot_remote.py',submit]+a.include}
contents.update({'job_plan.json':plan_bytes,'slurm/run.sbatch':shell})
hashes={name:hashlib.sha256(payload).hexdigest() for name,payload in contents.items()}
contents['SHA256SUMS']=''.join(h+'  '+name+'\n' for name,h in hashes.items()).encode()
assert b'\r' not in contents['SHA256SUMS'] and b'\r' not in shell
with tarfile.open(archive,'w:gz') as tf:
    for name,payload in contents.items():
        info=tarfile.TarInfo(name);info.size=len(payload);tf.addfile(info,io.BytesIO(payload))
manifest=dict(name=a.name,archive=str(archive),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),plan=plan,source_hashes=hashes)
(folder/(a.name+'.manifest.json')).write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
print(json.dumps(manifest,indent=2))
