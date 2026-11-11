#!/usr/bin/env bash
#SBATCH --ntasks=1
set -euo pipefail
engine=$1
release=$2
result=$3
profile=$4
shards=$5
count=$6
shard=${SLURM_ARRAY_TASK_ID:?}
case "$(realpath -m "$result")" in /scratch/user/changze/lqr_experiments/results/approx-tail-* ) ;; *) exit 2 ;; esac
for ((task=shard; task<count; task+=shards)); do
  label=$(printf '%03d' "$task")
  final="$result/$profile/raw/task-$label.json"
  if [[ -s "$final" ]]; then
    printf 'Reuse complete output %s\n' "$final"
    continue
  fi
  before="$result/$profile/raw/progress-$label.json"
  if [[ -s "$before" ]]; then
    mkdir -p "$result/recovery/$profile"
    cp -p "$before" "$result/recovery/$profile/task-$label-before-retry.json"
  fi
  printf 'Retry missing completed configuration %s task %s from its declared initial state\n' "$profile" "$task"
  SLURM_ARRAY_TASK_ID=$task bash "$release/slurm/approx_tail_suite.sbatch" "$engine" "$release" "$result" run "$profile"
done
