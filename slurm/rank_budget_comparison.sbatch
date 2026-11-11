#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:10:00
set -euo pipefail
engine=$1
result=$2
runtime="$result/runtime/direct-comparison-$SLURM_JOB_ID"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$engine" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$result/source"
sha256sum -c DIRECT_COMPARISON_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B rank_budget_comparison.py --output "$result"
archive="/scratch/user/changze/lqr_experiments/packages/$(basename "$result")-direct-comparison-v3.tar.gz"
tar -czf "$archive" -C "$result" direct-comparison-v3
sha256sum "$archive" > "$archive.sha256"
