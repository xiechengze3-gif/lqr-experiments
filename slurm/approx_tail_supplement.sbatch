#!/usr/bin/env bash
#SBATCH --ntasks=1
set -euo pipefail
engine=$1
result=$2
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/approx-tail-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/supplement-${SLURM_JOB_ID}"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$engine" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$result/scheduling"
sha256sum -c SUPPLEMENT_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B approx_tail_supplement.py --output "$result"
