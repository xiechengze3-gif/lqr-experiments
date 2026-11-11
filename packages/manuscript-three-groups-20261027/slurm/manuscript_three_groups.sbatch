#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=manuscript-three-groups-20261027
release=$base/releases/$name
cache=$base/cache/$name
temp=$base/tmp/$name
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
py=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
mode=$1
if [[ "$mode" == report ]]; then
  "$py" -B scripts/manuscript_three_groups_report.py
elif [[ "$mode" == formal ]]; then
  "$py" -B scripts/manuscript_three_groups.py formal --bundle "${SLURM_ARRAY_TASK_ID:?}"
else
  "$py" -B scripts/manuscript_three_groups.py "$mode"
fi
