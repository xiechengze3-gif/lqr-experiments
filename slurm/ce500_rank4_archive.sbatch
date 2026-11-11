#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=ce500-rank4-extension-20261020
release=$base/releases/$name
export TMPDIR="$base/tmp/$name" TEMP="$base/tmp/$name" TMP="$base/tmp/$name"
export XDG_CACHE_HOME="$base/cache/$name"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
cd "$release"
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/archive_ce500_rank4.py
