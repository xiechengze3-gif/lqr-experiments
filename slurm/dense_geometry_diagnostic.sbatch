#!/usr/bin/env bash
#SBATCH --job-name=lqr-geometry-diagnostic
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=02:00:00
set -euo pipefail
release=$1
supplement=$2
manifest=$3
result=$4
mode=$5
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/dense-* ) ;; *) exit 2 ;; esac
mkdir -p "$result/raw" "$result/report" "$result/runtime/$SLURM_JOB_ID/tmp" "$result/runtime/$SLURM_JOB_ID/cache"
export TMPDIR="$result/runtime/$SLURM_JOB_ID/tmp" TEMP="$result/runtime/$SLURM_JOB_ID/tmp" TMP="$result/runtime/$SLURM_JOB_ID/tmp"
export XDG_CACHE_HOME="$result/runtime/$SLURM_JOB_ID/cache" NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c DENSE_SHA256SUMS
cd "$supplement"
sha256sum -c GEOMETRY_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
if [[ "$mode" == projector ]]; then
  "$python_bin" -B scripts/projector_diagnostic.py --manifest "$manifest" --task-id "${SLURM_ARRAY_TASK_ID:?}" --output "$result/raw"
elif [[ "$mode" == reference ]]; then
  "$python_bin" -B scripts/actor_optimization_reference.py --manifest "$manifest" --output "$result/report/actor_optimization_reference.csv"
else
  exit 2
fi
