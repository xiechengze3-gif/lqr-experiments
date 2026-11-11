#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
name=ce500-equal-modes-20261020
base=/scratch/user/changze/lqr_experiments
release=$base/releases/$name
result=$base/results/$name
cache=$base/cache/$name
temp=$base/tmp/$name
mkdir -p "$result/logs" "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest="$release/configs/ce500_equal_modes_20261020.json"
if [[ "$1" == prepare ]]; then
  "$python_bin" -B scripts/ce500_equal_modes.py prepare --manifest "$manifest"
elif [[ "$1" == task ]]; then
  "$python_bin" -B scripts/ce500_equal_modes.py task --manifest "$manifest" --phase "$2" --task-id "$SLURM_ARRAY_TASK_ID"
else
  sha256sum -c SHA256SUMS_REPORT
  "$python_bin" -B scripts/ce500_equal_modes_report.py "$@" --manifest "$manifest"
fi
