#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
group=$1
mode=$2
args=("$mode" --group "$group")
if [[ "$mode" == task || "$mode" == audit ]]; then args+=(--index "${SLURM_ARRAY_TASK_ID:?}"); fi
exec /scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B /scratch/user/changze/lqr_experiments/releases/ce500-inode-recovery-20261023.py "${args[@]}"
