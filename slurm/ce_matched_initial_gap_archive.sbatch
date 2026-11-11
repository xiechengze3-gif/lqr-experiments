#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
set -euo pipefail
root=/scratch/user/changze/lqr_experiments
name=ce-matched-initial-gap-20261018
out=$root/results/$name
mkdir -p "$root/archives" "$out/frozen/release"
cp -a "$root/releases/$name/." "$out/frozen/release/"
myproject > "$out/account_at_archive.txt"
myproject -j 132685389143 | tail -n 4 > "$out/settled_account_summary_at_archive.txt"
python3 - "$out" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1])
for phase,n in [('pilot',25),('confirm',150)]:
 s=json.loads((p/f'report-{phase}/summary.json').read_text());assert s['status']=='complete' and s['audit']['paired_tasks']==n
assert len(list((p/'raw').glob('ce-r*.json')))==175
hashes={q.relative_to(p).as_posix():hashlib.sha256(q.read_bytes()).hexdigest() for q in p.rglob('*') if q.is_file() and not q.name.startswith('archive-') and q.name!='artifact_sha256.json'}
(p/'artifact_sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
print('Coverage and artifact manifest verified:',len(hashes),flush=True)
PY
archive=$root/archives/$name.tar.gz
test ! -e "$archive"
tar -czf "$archive.partial" -C "$root/results" "$name"
mv "$archive.partial" "$archive"
sha256sum "$archive" > "$archive.sha256"
stat -c 'Archive bytes: %s' "$archive"
cat "$archive.sha256"
