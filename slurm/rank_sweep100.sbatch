#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
set -euo pipefail
release=/scratch/user/changze/lqr_experiments/releases/rank-sweep100-20261016
result=/scratch/user/changze/lqr_experiments/results/rank-sweep100-20261016
cache=/scratch/user/changze/lqr_experiments/cache/rank-sweep100-20261016
temp=/scratch/user/changze/lqr_experiments/tmp/rank-sweep100-20261016
mkdir -p "$result/logs" "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest="$release/configs/rank_sweep100_20261016.json"
mode=$1
if [[ "$mode" == preflight ]]; then
  "$python_bin" -B scripts/rank_sweep100_remote.py verify --manifest "$manifest"
  "$python_bin" -B scripts/rank_sweep100_remote.py benchmark --manifest "$manifest"
elif [[ "$mode" == task ]]; then
  "$python_bin" -B scripts/rank_sweep100_remote.py task --manifest "$manifest" --phase "$2" --route "$3" --task-id "$SLURM_ARRAY_TASK_ID"
elif [[ "$mode" == report ]]; then
  "$python_bin" -B scripts/rank_sweep100_remote.py report --manifest "$manifest" --phase "$2"
else
  exit 2
fi
