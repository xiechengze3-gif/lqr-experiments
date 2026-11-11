#!/usr/bin/env bash
#SBATCH --ntasks=1
set -euo pipefail
release=$1
result=$2
runtime="$result/runtime/gate-${SLURM_JOB_ID}"
mkdir -p "$runtime/tmp"
export TMPDIR="$runtime/tmp" TMP="$runtime/tmp" TEMP="$runtime/tmp" PYTHONDONTWRITEBYTECODE=1
cd "$release"
sha256sum -c RANK_MULTISEED_SHA256SUMS
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B - "$release" "$result" <<'PY'
import hashlib, json, os, sys
from pathlib import Path
release,result=map(Path,sys.argv[1:])
manifest=release/'configs/rank_multiseed.json'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
for relative in ('verification.json','resume-audit/resume_audit.json','report_schema_audit.json','requeue_audit.json'):
    assert json.loads((result/relative).read_text())['status']=='PASS',relative
verification=json.loads((result/'verification.json').read_text())
assert verification['manifest_sha256']==sha(manifest)
assert json.loads((result/'resume-audit/resume_audit.json').read_text())['source_sha256']==sha(release/'scripts/rank_multiseed_run.py')
assert json.loads((result/'report_schema_audit.json').read_text())['source_sha256']==sha(release/'scripts/rank_multiseed_report_audit.py')
payload=dict(status='PASS',manifest_sha256=sha(manifest),slurm_job_id=os.environ['SLURM_JOB_ID'])
(result/'gate.json').write_text(json.dumps(payload,indent=2)+'\n')
print(json.dumps(payload),flush=True)
PY
