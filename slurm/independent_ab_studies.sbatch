#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/independent-ab-studies-20261022-v1
study=$1
mode=$2
phase=$3
if [[ "$study" == ce ]]; then
  name=ce500-independent-stabilizer-20261022
  script=ce500_independent_stabilizer
else
  name=stein-independent-stabilizer-20261022
  script=stein_independent_stabilizer
fi
result=$base/results/$name
cache=$base/cache/$name
temp=$base/tmp/$name
mkdir -p "$result/logs" "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$release:$release/scripts" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$release"
sha256sum -c SHA256SUMS
py=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest=$release/configs/${script}_20261022.json
args=("$mode" --phase "$phase" --manifest "$manifest")
if [[ "$mode" == task ]]; then args+=(--task-id "${SLURM_ARRAY_TASK_ID:?}"); fi
if [[ "$mode" == audit ]]; then args+=(--shard "${SLURM_ARRAY_TASK_ID:?}"); fi
"$py" -B scripts/${script}.py "${args[@]}"
if [[ "$mode" == prepare ]]; then
  "$py" -B scripts/independent_ab_operations.py "$study" pilot --release "$release"
elif [[ "$mode" == report && "$phase" == pilot ]]; then
  "$py" -B scripts/independent_ab_operations.py "$study" formal --release "$release"
fi
