#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=ce500-random-a-20261020
release=$base/releases/$name
ops=$base/releases/ce500-random-a-recovery-v3
result=$base/results/$name
cache=$base/cache/$name
temp=$base/tmp/$name
mkdir -p "$temp" "$cache/numba" "$cache/matplotlib"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts:$ops/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS
cd "$ops"
sha256sum -c SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest="$release/configs/ce500_random_a_20261020.json"
if [[ "$1" == recover ]]; then
  "$python_bin" -B scripts/ce500_random_a_recover.py --manifest "$manifest" --plan "$2"
else
  "$python_bin" -B scripts/ce500_random_a_execution_audit.py --manifest "$manifest"
fi
