#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1024M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=ce500-matched-gap-20261019
release=$base/releases/$name
export TMPDIR=$base/tmp/$name TEMP=$base/tmp/$name TMP=$base/tmp/$name
export XDG_CACHE_HOME=$base/cache/$name PYTHONDONTWRITEBYTECODE=1
cd "$release"
sha256sum -c FINISH_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/ce500_finish.py --manifest configs/ce500_matched_gap_20261019.json
