#!/usr/bin/env bash
#SBATCH --job-name=lqr-npg-300-feasibility
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=02:00:00
set -euo pipefail
release=$1
result=$2
root=/scratch/user/changze/lqr_experiments
case "$(realpath -m "$result")" in "$root/results/npg-300-feasibility-"*) ;; *) exit 2 ;; esac
engine="$root/releases/7f5c6de07fb244ab"
frozen="$root/releases/npg-budget-e93b7ffa7fca793e"
runtime="$result/runtime/$SLURM_JOB_ID"
mkdir -p "$runtime/tmp" "$runtime/cache" "$result/numba-cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$frozen/scripts:$engine" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 NUMBA_NUM_THREADS=1
cd "$engine"
sha256sum -c DENSE_SHA256SUMS
cd "$frozen"
sha256sum -c NPG_BUDGET_SHA256SUMS
cd "$release"
sha256sum -c FEASIBILITY_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python_bin" -B scripts/npg_300_feasibility.py --output "$result" \
    --reference-cache "$root/results/npg-300-feasibility-640891a313f0aac9/feasibility.json" \
    --cache-sha256 fcf7e7d10cc49ad587a42185c674a1041b6dc746171af6cdd351a61c4b1f063d
sha256sum "$result/feasibility.json" > "$result/feasibility.json.sha256"
