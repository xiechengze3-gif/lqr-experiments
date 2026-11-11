#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
#SBATCH --time=00:06:00
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=ce-npg-initial-gap-20261028
release=$base/releases/$name
cache=$base/cache/$name
temp=$base/tmp/$name
mkdir -p "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache" MPLCONFIGDIR="$cache/matplotlib"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/ce_npg_initial_gap_postprocess.py
