"""Copy the sealed report release into its new output provenance directory."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
out = Path('/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b/report-v1')
assert json.loads((out/'RENDER_COMPLETE_v1.json').read_text())['status'] == 'SAVED_CSV_FIGURES_TABLES_RENDERED'
target = out/'provenance'
assert not target.exists()
target.mkdir()
items = []
for line in (root/'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert not Path(name).is_absolute() and '..' not in Path(name).parts
    payload = (root/name).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == digest
    path = target/name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(payload)
    items.append(dict(path=name, sha256=digest))
with (target/'SHA256SUMS').open('xb') as stream:
    stream.write((root/'SHA256SUMS').read_bytes())
print(json.dumps(dict(status='SOURCE_PROVENANCE_COPIED_NEW_ONLY', files=len(items))), flush=True)
