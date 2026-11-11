#!/usr/bin/env bash
#SBATCH --account=132685389143
#SBATCH --partition=short
#SBATCH --job-name=lqr-lstd-original-verify
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
release=$(realpath "$1")
result=$(realpath -m "$2")
case "$release" in /scratch/user/changze/lqr_experiments/releases/lstd-original-* ) ;; *) exit 2 ;; esac
case "$result" in /scratch/user/changze/lqr_experiments/results/lstd-original-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/${SLURM_JOB_ID}"
mkdir -p "$runtime/tmp" "$runtime/cache" "$result"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
export PYTHONPATH="$release/scripts"
cd "$release"
sha256sum -c LSTD_ORIGINAL_COORDINATES_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python_bin" -B - "$result" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from full_lstd import solve, verify

assert os.environ.get('SLURM_JOB_ID'), 'Grace compute node required'
started = time.monotonic()
output = Path(sys.argv[1]) / 'verification.json'
payload = dict(status='RUNNING', slurm_job_id=os.environ['SLURM_JOB_ID'],
               lstd_sha256=hashlib.sha256(Path(solve.__code__.co_filename).read_bytes()).hexdigest(),
               scope='small independent equation and dense Bellman checks; not a production benchmark')
try:
    payload.update(checks=verify(), status='PASS')
except Exception as error:
    payload.update(status='FAIL', error=repr(error))
    raise
finally:
    payload['seconds'] = time.monotonic() - started
    output.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps(payload), flush=True)
PY
