#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --job-name=lqr100-pi-archive
set -euo pipefail
root=/scratch/user/changze/lqr_experiments
name=rank-sweep100-pi-v2-20261017
result="$root/results/$name"
release="$root/releases/$name"
cache="$root/cache/$name"
temp="$root/tmp/$name"
mkdir -p "$root/archives" "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export PYTHONPATH="$release:$release/scripts" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
python_bin=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python_bin" -B - "$result" <<'PY'
import json,sys
from pathlib import Path
out=Path(sys.argv[1]);cfg=json.loads((out/'resolved_config.json').read_text())
tasks=[json.loads(p.read_text()) for p in (out/'raw').glob('pi-*.json')]
planned={(r,s) for r in cfg['ranks'] for s in cfg['pilot_seeds']+cfg['confirm_seeds']}
assert len(tasks)==len(planned) and {(d['rank'],d['seed']) for d in tasks}==planned
assert all(len(d['records'])==2*(len(cfg['batch_schedule'])+1) for d in tasks)
assert all(d['identity']==cfg['identity'] for d in tasks)
assert json.loads((out/'verification.json').read_text())['status']=='PASS'
assert json.loads((out/'maximum_memory_verification.json').read_text())['status']=='PASS'
(out/'archive_coverage.json').write_text(json.dumps(dict(status='complete',paired_groups=len(tasks),
    pilot_groups=25,confirmation_groups=150,full_planned_coverage=True),indent=2)+'\n')
PY
myproject > "$result/account_balance_at_archive.txt"
own_jobs="$1,$SLURM_JOB_ID"
sacct -j "$own_jobs" -n -P --format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU,NodeList,TimelimitRaw,MaxRSS > "$result/slurm_accounting_before_archive.psv"
tar -czf "$root/archives/$name.tar.gz" -C "$root" \
 --transform='s,^results/,,' --transform='s,^releases/,source/,' \
 "results/$name" "releases/$name" \
 results/rank-sweep100-pi-20261017 releases/rank-sweep100-pi-20261017 \
 results/rank-sweep100-pi-preflight-20261017 releases/rank-sweep100-pi-preflight-20261017 \
 results/rank-sweep100-pi-maxbench-20261017 releases/rank-sweep100-pi-maxbench-20261017
sha256sum "$root/archives/$name.tar.gz" > "$root/archives/$name.tar.gz.sha256"
cat "$root/archives/$name.tar.gz.sha256"
stat -c '%s bytes' "$root/archives/$name.tar.gz"
