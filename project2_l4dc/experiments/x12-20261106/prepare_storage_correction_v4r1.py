"""Freeze a submission-only correction to the never-deployed v4 pilot."""
import argparse, ast, hashlib, io, json, tarfile
from pathlib import Path

R = Path(__file__).resolve().parent
sha = lambda b: hashlib.sha256(b).hexdigest()
m = json.loads((R / 'STORAGE_CORRECTION_MANIFEST_v4.json').read_text())
review = (R.parents[1] / 'CLAUDE_TASK.md').read_bytes()
p = argparse.ArgumentParser()
p.add_argument('--expected-review-sha256', required=True)
assert sha(review) == p.parse_args().expected_review_sha256, 'Review changed; reread before preparing.'
assert b'X12 storage correction: no REVISE (02:40Z 11/07)' in review
source = R / 'storage-correction-release-v4'
files = {n: (source / n).read_bytes() for n in m['files']}
assert {n: sha(b) for n, b in files.items()} == m['files']
files['CLAUDE_TASK_authorized.md'] = review
n = 'submit_storage_correction_v4.py'
old = files[n].decode()
assert old.count("ROOT/'results/pilot-out-v4'") == 1
assert old.count("historical_summed_requests_SU=prior['cumulative_requested_SU']+5/60,prior_ledger") == 1
new = old.replace("ROOT/'results/pilot-out-v4'", "ROOT/'pilot-out-v4'")
new = new.replace("historical_summed_requests_SU=prior['cumulative_requested_SU']+5/60,prior_ledger",
                  "historical_summed_requests_SU=prior['cumulative_requested_SU']+5/60+5/60,prior_ledger")
ast.parse(new)
files[n] = new.encode()
hashes = {n: sha(b) for n, b in files.items()}
files['SHA256SUMS'] = ''.join(f'{h}  {n}\n' for n, h in hashes.items()).encode()
archive = R / 'x12-storage-correction-v4r1.tar.gz'
receipt = R / 'STORAGE_CORRECTION_MANIFEST_v4r1.json'
assert not archive.exists() and not receipt.exists()
with tarfile.open(archive, 'x:gz') as tf:
    for n, b in files.items():
        item = tarfile.TarInfo(n)
        item.size = len(b)
        tf.addfile(item, io.BytesIO(b))
m.update(status='STORAGE_CORRECTION_V4R1_FROZEN_NOT_SUBMITTED', archive=str(archive),
         archive_sha256=sha(archive.read_bytes()), manifest_sha256=sha(files['SHA256SUMS']),
         review_sha256=sha(review),
         files=hashes, changes=['guard actual output path', 'historical request book includes both I/O attempts'])
with receipt.open('x') as f:
    json.dump(m, f, indent=2)
print(m['archive_sha256'])
