#!/usr/bin/env bash
#SBATCH --job-name=lqr-npg-complete-review
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
root=/scratch/user/changze/lqr_experiments
review="$root/results/npg-budget-review-e93b7ffa7fca793e"
mkdir -p "$review/runtime/tmp" "$review/runtime/cache"
export TMPDIR="$review/runtime/tmp" TEMP="$review/runtime/tmp" TMP="$review/runtime/tmp"
export XDG_CACHE_HOME="$review/runtime/cache" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$review"
sha256sum -c REVIEW_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python_bin" -B review_npg_budget_complete.py \
  --input "$root/results/npg-budget-e93b7ffa7fca793e/report" --output "$review"
sha256sum completion_review.json > completion_review.json.sha256
