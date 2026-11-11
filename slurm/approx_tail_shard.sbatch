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
  final="$result/$profile/raw/$(printf 'task-%03d.json' "$task")"
  if [[ -s "$final" ]]; then
    printf 'Existing completed output: %s\n' "$final"
    continue
  fi
  printf 'Profile %s, shard %s, task %s\n' "$profile" "$shard" "$task"
  SLURM_ARRAY_TASK_ID=$task bash "$release/slurm/approx_tail_suite.sbatch" "$engine" "$release" "$result" run "$profile"
done
