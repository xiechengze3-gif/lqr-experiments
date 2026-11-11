#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
original=/scratch/user/changze/lqr_experiments/releases/ce500-random-a-20261020/slurm/ce500_random_a.sbatch
if [[ "$1" == task ]]; then
  exec bash "$original" "$@" --task-id "${SLURM_ARRAY_TASK_ID:?Missing Slurm array task id}"
else
  exec bash "$original" "$@"
fi
