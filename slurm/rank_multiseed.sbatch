#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --requeue
set -euo pipefail
engine=$1
release=$2
result=$3
mode=$4
profile=${5:-none}
shards=${6:-1}
count=${7:-0}
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/rank-multiseed-* ) ;; *) exit 2 ;; esac
runtime="$result/runtime/${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-single}-${SLURM_RESTART_COUNT:-0}"
mkdir -p "$runtime/tmp" "$runtime/cache" "$result/numba-cache"
export TMPDIR="$runtime/tmp" TEMP="$runtime/tmp" TMP="$runtime/tmp"
export XDG_CACHE_HOME="$runtime/cache" MPLCONFIGDIR="$runtime/cache/matplotlib"
export NUMBA_CACHE_DIR="$result/numba-cache" LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export LQR_TAIL_SYSTEM_CACHE="$result/systems"
export LQR_TAIL_BUILD_CACHE=0
export PYTHONPATH="$release/scripts:$engine" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1} MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1} OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1} NUMBA_NUM_THREADS=1
cd "$engine"
sha256sum -c DENSE_SHA256SUMS
cd "$release"
sha256sum -c RANK_MULTISEED_SHA256SUMS
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
manifest="$release/configs/rank_multiseed.json"
if [[ "$mode" == verify ]]; then
  export LQR_TAIL_BUILD_CACHE=1
  "$python_bin" -B scripts/rank_multiseed_run.py verify --manifest "$manifest" --output "$result"
  export LQR_TAIL_BUILD_CACHE=0
  "$python_bin" -B scripts/rank_multiseed_run.py resume-audit --manifest "$manifest" --output "$result"
  "$python_bin" -B scripts/rank_multiseed_report_audit.py --manifest "$manifest" --output "$result"
elif [[ "$mode" == requeue-audit ]]; then
  if ((${SLURM_RESTART_COUNT:-0} == 0)); then
    scontrol requeue "$SLURM_JOB_ID"
  else
    printf '{"status":"PASS","restart_count":%s,"job_id":"%s"}\n' "$SLURM_RESTART_COUNT" "$SLURM_JOB_ID" > "$result/requeue_audit.json"
  fi
elif [[ "$mode" == report || "$mode" == algorithm-report ]]; then
  args=(--manifest "$manifest" --output "$result")
  if [[ "$mode" == algorithm-report ]]; then args+=(--algorithm "$profile"); fi
  "$python_bin" -B scripts/rank_multiseed_report.py "${args[@]}"
elif [[ "$mode" == shard || "$mode" == reference ]]; then
  shard=${SLURM_ARRAY_TASK_ID:?}
  started=$SECONDS
  # Stop between completed stages with three hours left for a large stage.
  soft_seconds=72000
  requeue=0
  for ((task=shard; task<count; task+=shards)); do
    if [[ "$mode" == reference ]]; then
      final="$result/reference/$(printf 'task-%03d.json' "$task")"
      if [[ -s "$final" ]]; then continue; fi
      if ((SECONDS-started >= soft_seconds)); then requeue=1; break; fi
      "$python_bin" -B scripts/rank_multiseed_run.py reference --manifest "$manifest" --output "$result" --task-id "$task"
    else
      final="$result/$profile/raw/$(printf 'task-%03d.json' "$task")"
      if [[ -s "$final" ]]; then continue; fi
      remaining=$((soft_seconds-SECONDS+started))
      if ((remaining <= 0)); then requeue=1; break; fi
      minutes=$((remaining/60))
      set +e
      "$python_bin" -B scripts/rank_multiseed_run.py run --manifest "$manifest" --output "$result" --task-id "$task" --profile "$profile" --minutes "$minutes"
      code=$?
      set -e
      if ((code == 85)); then requeue=1; break; fi
      if ((code != 0)); then exit "$code"; fi
    fi
  done
  if ((requeue)); then
    restarts=${SLURM_RESTART_COUNT:-0}
    if ((restarts >= 16)); then
      printf 'Bounded requeue limit reached; coverage remains incomplete.\n' >&2
      exit 86
    fi
    job="${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
    printf 'Checkpoint saved, requesting own shard requeue: %s, restart %s\n' "$job" "$restarts"
    scontrol requeue "$job"
    exit 0
  fi
else
  exit 2
fi
