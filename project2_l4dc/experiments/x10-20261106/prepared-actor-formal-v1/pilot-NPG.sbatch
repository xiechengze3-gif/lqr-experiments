#!/usr/bin/env bash
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/x10-20261106-b-pilot-v2
cache=$base/cache/x10-20261106
temp=$base/tmp/x10-20261106/job-${SLURM_ARRAY_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B actor_pilot_v2.py --config actor-config-protocol-v2.json --role NPG
