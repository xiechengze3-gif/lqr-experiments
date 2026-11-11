#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=7G
#SBATCH --time=00:40:00
#SBATCH --job-name=lqr100-lstd-pi
set -euo pipefail
release=/scratch/user/changze/lqr_experiments/releases/rank-sweep100-pi-v2-20261017
result=/scratch/user/changze/lqr_experiments/results/rank-sweep100-pi-v2-20261017
cache=/scratch/user/changze/lqr_experiments/cache/rank-sweep100-pi-v2-20261017
temp=/scratch/user/changze/lqr_experiments/tmp/rank-sweep100-pi-v2-20261017
mkdir -p "$result/logs" "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest="$release/configs/rank_sweep100_pi_20261017.json"
if [[ "$1" == verify ]]; then
  "$python_bin" -B scripts/rank_sweep100_pi.py verify --manifest "$manifest"
elif [[ "$1" == task ]]; then
  "$python_bin" -B scripts/rank_sweep100_pi.py task --manifest "$manifest" --phase "$2" --task-id "$SLURM_ARRAY_TASK_ID"
else
  exit 2
fi
