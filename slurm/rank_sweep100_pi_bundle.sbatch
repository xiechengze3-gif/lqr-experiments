#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=7G
#SBATCH --time=03:48:00
#SBATCH --partition=medium
#SBATCH --job-name=lqr100-pi-seed
set -euo pipefail
root=/scratch/user/changze/lqr_experiments
name=rank-sweep100-pi-v2-20261017
release="$root/releases/$name"
result="$root/results/$name"
cache="$root/cache/$name"
temp="$root/tmp/$name"
mkdir -p "$result/logs" "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS
sha256sum -c "$result/formal_sources.sha256"
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest="$release/configs/rank_sweep100_pi_20261017.json"
[[ "$SLURM_ARRAY_TASK_ID" =~ ^[0-9]+$ ]]
[[ "$SLURM_ARRAY_TASK_ID" -ge 0 && "$SLURM_ARRAY_TASK_ID" -lt 30 ]]
# Each child has exactly the original pair task, seed, innovations and identity.
# A completed pair exits without new samples on any permitted bundle recovery.
for rank_offset in 0 1 2 3 4; do
  task_id=$((SLURM_ARRAY_TASK_ID*5+rank_offset))
  "$python_bin" -B scripts/rank_sweep100_pi.py task --manifest "$manifest" --phase confirm --task-id "$task_id"
done
