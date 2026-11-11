#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=ce500-equal-modes-20261020
release=$base/releases/$name
export TMPDIR=$base/tmp/$name TEMP=$base/tmp/$name TMP=$base/tmp/$name
export XDG_CACHE_HOME=$base/cache/$name NUMBA_CACHE_DIR=$base/cache/$name/numba MPLCONFIGDIR=$base/cache/$name/matplotlib
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH=$release:$release/scripts PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS
sha256sum -c SHA256SUMS_REPORT
sha256sum -c SHA256SUMS_EXECUTION
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest=configs/ce500_equal_modes_20261020.json
"$python_bin" -B scripts/ce500_equal_modes_report.py confirm --manifest "$manifest"
"$python_bin" -B scripts/ce500_equal_modes_execution_audit.py --manifest "$manifest"
