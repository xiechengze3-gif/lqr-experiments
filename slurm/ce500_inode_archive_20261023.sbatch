#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=512M
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
exec /scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -u /scratch/user/changze/lqr_experiments/releases/ce500-inode-archive-20261023.py
