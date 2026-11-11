#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
set -euo pipefail
name=ce-matched-initial-gap-20261018
release=/scratch/user/changze/lqr_experiments/releases/$name
result=/scratch/user/changze/lqr_experiments/results/$name
cache=/scratch/user/changze/lqr_experiments/cache/$name
temp=/scratch/user/changze/lqr_experiments/tmp/$name
mkdir -p "$result/logs" "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest="$release/configs/ce_matched_initial_gap_20261018.json"
mode=$1
if [[ "$mode" == task ]]; then
  "$python_bin" -B scripts/ce_matched_initial_gap.py task --manifest "$manifest" --phase "$2" --task-id "$SLURM_ARRAY_TASK_ID"
else
  "$python_bin" -B scripts/ce_matched_initial_gap.py "$mode" --manifest "$manifest" --phase "${2:-pilot}"
fi
