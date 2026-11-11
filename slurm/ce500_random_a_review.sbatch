#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=512M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/ce500-random-a-review-v2
export TMPDIR="$base/tmp/ce500-random-a-20261020" TEMP="$base/tmp/ce500-random-a-20261020" TMP="$base/tmp/ce500-random-a-20261020"
export XDG_CACHE_HOME="$base/cache/ce500-random-a-20261020" PYTHONDONTWRITEBYTECODE=1
cd "$release"
sha256sum -c SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/review_ce500_random_a_identity.py --manifest "$base/releases/ce500-random-a-20261020/configs/ce500_random_a_20261020.json"
