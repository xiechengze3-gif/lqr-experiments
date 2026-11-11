#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/matched-gap-review-v2-20261019
name=matched-gap-npg-pi-v2-20261019
cache=$base/cache/$name
temp=$base/tmp/$name
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum --quiet -c SHA256SUMS
py=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest=configs/matched_gap_npg_pi_20261019.json
if [[ "$1" == pilot ]]; then
  "$py" -B scripts/matched_gap_npg_pi.py report --manifest "$manifest" --phase pilot
elif [[ "$1" == confirm ]]; then
  "$py" -B scripts/matched_gap_npg_pi.py report --manifest "$manifest" --phase confirm
  if [[ ! -s "$base/results/$name/supplement/optimization_diagnostics.json" ]]; then
    "$py" -B scripts/matched_gap_supplement.py --manifest "$manifest"
  fi
else
  exit 2
fi
