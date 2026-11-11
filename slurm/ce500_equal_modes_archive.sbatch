#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=ce500-equal-modes-20261020
release=$base/releases/$name
export TMPDIR="$base/tmp/$name" TEMP="$base/tmp/$name" TMP="$base/tmp/$name"
export XDG_CACHE_HOME="$base/cache/$name" PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS_REPORT
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/archive_ce500_equal_modes.py --manifest configs/ce500_equal_modes_20261020.json
