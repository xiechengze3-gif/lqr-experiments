#!/usr/bin/env bash
#SBATCH --job-name=lqr-rank-review
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
result="$base/results/npg-rank-ea112fabeef4eb4a"
out="$result/recovery-review-20261008"
mkdir -p "$out/runtime/tmp" "$out/runtime/cache"
export TMPDIR="$out/runtime/tmp" TEMP="$out/runtime/tmp" TMP="$out/runtime/tmp"
export XDG_CACHE_HOME="$out/runtime/cache" MPLCONFIGDIR="$out/runtime/cache/matplotlib"
export PYTHONPATH="$base/releases/7f5c6de07fb244ab" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B \
  "$result/source/npg_rank_recovery_review.py" --root "$result" \
  --manifest "$result/source/manifest.json" --destination "$out"
sha256sum "$out/recovery_audit.json" "$out/review_endpoint.png" "$out/review_endpoint.pdf" > "$out/SHA256SUMS"
