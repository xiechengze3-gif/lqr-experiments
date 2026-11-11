#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2048M
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=common-constant-spectrum-preflight-20261022-v1
release=$base/releases/$name
out=$base/results/$name
cache=$base/cache/$name
temp=$base/tmp/$name
mkdir -p "$out/logs" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache" MPLCONFIGDIR="$cache/matplotlib"
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
cd "$release"
sha256sum -c SHA256SUMS
py=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$py" -B scripts/common_constant_spectrum_preflight.py "$base/results/independent-ab-stabilizer-20261022-v4" "$out"
