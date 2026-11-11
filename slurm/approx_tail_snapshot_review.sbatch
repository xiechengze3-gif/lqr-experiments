#!/usr/bin/env bash
#SBATCH --ntasks=1
set -euo pipefail
engine=$1
release=$2
snapshot=$3
review_source=$4
runtime="${snapshot}-review-runtime"
mkdir -p "$runtime/tmp" "$runtime/cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release/scripts:$engine" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c APPROX_TAIL_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B "$review_source" report --manifest "$release/configs/approx_tail_suite.json" --output "$snapshot"
cp "$review_source" "$snapshot/review/"
cp "$snapshot/snapshot_scope.json" "$snapshot/review/"
archive="/scratch/user/changze/lqr_experiments/packages/$(basename "$snapshot")-review.tar.gz"
tar -czf "$archive" -C "$snapshot" review
sha256sum "$archive" > "$archive.sha256"
