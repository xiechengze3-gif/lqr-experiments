#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
set -euo pipefail
name=matched-gap-npg-pi-20261019
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
sha256sum --quiet -c SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest="$release/configs/matched_gap_npg_pi_20261019.json"
if [[ "$1" == npg-preflight ]]; then
  "$python_bin" -B scripts/matched_gap_npg_pi.py prepare --manifest "$manifest"
  "$python_bin" -B scripts/matched_gap_npg_pi.py npg-preflight --manifest "$manifest"
elif [[ "$1" == bundle ]]; then
  for offset in 0 1 2 3 4; do
    task_id=$((SLURM_ARRAY_TASK_ID*5+offset))
    "$python_bin" -B scripts/matched_gap_npg_pi.py task --manifest "$manifest" --route "$2" --phase confirm --task-id "$task_id"
  done
elif [[ "$1" == task ]]; then
  "$python_bin" -B scripts/matched_gap_npg_pi.py task --manifest "$manifest" --route "$2" --phase "$3" --task-id "$SLURM_ARRAY_TASK_ID"
else
  "$python_bin" -B scripts/matched_gap_npg_pi.py "$1" --manifest "$manifest" --phase "${2:-pilot}"
fi
