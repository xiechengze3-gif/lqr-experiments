#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
name=matched-gap-npg-pi-v2-20261019
out=$base/results/$name
meta_python=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$meta_python" -B - "$out" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
for phase in ('pilot','confirm'):
    s=json.loads((p/f'report-{phase}/summary.json').read_text())
    assert s['status']=='complete' and all(v['status']=='PASS' for v in s['audits'].values())
assert json.loads((p.parent/'matched-gap-npg-pi-20261019/ce-identification-audit/audit.json').read_text())['status']=='PASS'
joined=json.loads((p/'joined-report/all_algorithms_summary.json').read_text())
assert joined['status']=='complete' and len(joined['requirements'])==60
PY
myproject > "$out/balance-before-archive.txt"
"$meta_python" -B - "$base" "$name" <<'PY'
import hashlib,json,sys
from pathlib import Path
base=Path(sys.argv[1]);name=sys.argv[2];paths={}
for folder in (base/'results'/name,base/'results/matched-gap-npg-pi-20261019'):
    for p in sorted(folder.rglob('*')):
        if p.is_file() and p.name!='ARCHIVE_FILE_MANIFEST.json':
            with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
            paths[str(p.relative_to(base/'results'))]=dict(bytes=p.stat().st_size,sha256=sha)
(base/'results'/name/'ARCHIVE_FILE_MANIFEST.json').write_text(json.dumps(paths,indent=2)+'\n')
print(f'Hash manifest: {len(paths)} files',flush=True)
PY
mkdir -p "$base/archives"
tar -czf "$base/archives/$name.tar.gz" -C "$base/results" "$name" matched-gap-npg-pi-20261019
sha256sum "$base/archives/$name.tar.gz" > "$base/archives/$name.tar.gz.sha256"
stat -c '%s bytes' "$base/archives/$name.tar.gz"
cat "$base/archives/$name.tar.gz.sha256"
