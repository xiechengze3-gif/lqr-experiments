#!/usr/bin/env bash
#SBATCH --job-name=lqr-rank
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=02:00:00
set -euo pipefail
: "${SLURM_JOB_ID:?Submit via Slurm}"
if [[ $# -ne 5 ]]; then
  echo 'Usage: experiment.sbatch PYTHON RELEASE MANIFEST RESULT_ROOT verify|run|report' >&2
  exit 2
fi
python_bin=$1
release=$2
manifest=$3
result_root=$4
mode=$5
for task_path in "$python_bin" "$release" "$manifest" "$result_root"; do
  [[ "$task_path" == /* ]] || { echo 'Require absolute paths.' >&2; exit 2; }
done
case "$(realpath -m "$result_root")" in
  /scratch/user/changze/lqr_experiments/results/*) ;;
  *) echo 'Results must be inside the LQR scratch project.' >&2; exit 2 ;;
esac
runtime="$result_root/runtime/${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-single}"
mkdir -p "$runtime/tmp" "$runtime/cache/matplotlib" "$result_root/raw" "$result_root/report"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export PIP_CACHE_DIR="$runtime/cache/pip" MPLBACKEND=Agg
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS
scontrol show job "$SLURM_JOB_ID" > "$runtime/slurm_request.txt"
printf 'RELEASE=%s\nOUTPUT=%s\nTMPDIR=%s\nPYTHON=%s\n' "$release" "$result_root" "$TMPDIR" "$python_bin"
case "$mode" in
  verify) "$python_bin" -B lqr_experiments.py verify ;;
  run) "$python_bin" -B lqr_experiments.py run --manifest "$manifest" --task-id "${SLURM_ARRAY_TASK_ID:?}" --output "$result_root/raw" ;;
  report) "$python_bin" -B summarize.py --manifest "$manifest" --raw "$result_root/raw" --output "$result_root/report" ;;
  *) exit 2 ;;
esac
