#!/usr/bin/env bash
#SBATCH --ntasks=1
set -euo pipefail
engine=$1
release=$2
result=$3
algorithm=$4
report=${5:-$result/report-${algorithm,,}}
runtime="$result/runtime/same-budget-${SLURM_JOB_ID}"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib" NUMBA_CACHE_DIR="$result/numba-cache"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release/scripts:$engine" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$release"
sha256sum -c RANK_MULTISEED_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B "$result/scheduling/rank_multiseed_same_budget.py" --report "$report"
