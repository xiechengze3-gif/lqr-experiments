#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1024M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
export TMPDIR=$base/tmp/final-story-20261024
export XDG_CACHE_HOME=$base/cache/final-story-20261024
cd $base/releases/final-story-20261024
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B scripts/final_story_progress.py
