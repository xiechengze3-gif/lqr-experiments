"""Prepare the same zero-observation pilot for a fresh Scratch MDT1 namespace."""
import argparse
import ast
import hashlib
import io
import json
import tarfile
from pathlib import Path


R = Path(__file__).resolve().parent
REVIEW = R.parents[1] / 'CLAUDE_TASK.md'
ROOT = '/scratch/user/changze/lqr_experiments/tmp/x12-storage-recovery-20261107-v6'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def replace(text, old, new, times=1):
    assert text.count(old) == times, old
    return text.replace(old, new)


def main(a):
    review = REVIEW.read_bytes()
    assert sha(review) == a.expected_review_sha256
    assert b'X12 storage: USER AUTHORIZED scratch cleanup' in review
    old = json.loads((R/'STORAGE_FLAT_MANIFEST_v5.json').read_bytes())
    raw = Path(old['archive']).read_bytes()
    assert sha(raw) == old['archive_sha256']
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tf:
        files = {n:tf.extractfile(n).read() for n in old['files']}
    assert {n:sha(b) for n,b in files.items()} == old['files']
    files['CLAUDE_TASK_authorized.md'] = review

    code = files.pop('pilot_virtual_store_v5.py').decode()
    code = replace(code, ".strip()=='0'", ".strip()=='1'", times=2)
    code = replace(code, 'output_MDT=0,', 'output_MDT=1,')
    files['pilot_virtual_store_v6.py'] = code.encode()
    sub = files.pop('submit_flat_storage_pilot_v5.py').decode()
    sub = replace(sub, old['remote_root'], ROOT)
    sub = replace(sub, 'submit_flat_storage_pilot_v5.py', 'submit_scratch_storage_pilot_v6.py')
    sub = replace(sub, 'storage-io-v5', 'storage-io-v6', times=3)
    sub = replace(sub, ".strip()=='0'", ".strip()=='1'", times=2)
    sub = replace(sub, "'31181','/home/changze'", "'231181','/scratch/user/changze'")
    sub = replace(sub, 'fs01-MDT0000', 'fs01-MDT0001')
    sub = replace(sub, "    assert int(mdt[7])-int(mdt[5])>=32", "    assert int(mdt[7])-int(mdt[5])>=128")
    sub = replace(sub, "    home=next(s for s in quota.splitlines() if s.startswith('/home/changze')).split()\n    assert 10000-int(home[-2])>=100 and home[1].endswith('G') and float(home[1][:-1])<8",
                  "    scratch=next(s for s in rawquota.splitlines() if s.strip().startswith('/scratch/user/changze ')).split()\n"
                  "    assert int(scratch[7])-int(scratch[5])>=128 and int(scratch[3])-int(scratch[1])>=512*1024")
    files['submit_scratch_storage_pilot_v6.py'] = sub.encode()
    sbatch = files['pilot.sbatch'].decode()
    sbatch = replace(sbatch, old['remote_root'], ROOT)
    sbatch = replace(sbatch, '/tmp/changze-x12-storage-v5-', '/tmp/changze-x12-storage-v6-')
    sbatch = replace(sbatch, 'pilot_virtual_store_v5.py', 'pilot_virtual_store_v6.py')
    files['pilot.sbatch'] = sbatch.encode()
    plan = json.loads(files['pilot-plan-v4.json'])
    plan.pop('home_project')
    plan.update(output_MDT=1, scratch_project=231181, previous_placement_v5_jobs=0)
    if not a.validate_only:
        cleanup = R/'scratch-cleanup-proposal-20261107-v1/CLEANUP_AUDITED_v1.json'
        evidence = json.loads(cleanup.read_bytes())
        assert evidence['status'] == 'EXACT_MANIFEST_CLEANUP_AUDITED_ON_E'
        assert evidence['new_slots_MDT1'] >= 512 and evidence['new_slots_total'] >= 512
        plan['cleanup_evidence_sha256'] = sha(cleanup.read_bytes())
    files['pilot-plan-v4.json'] = (json.dumps(plan, indent=2)+'\n').encode()
    for n,b in files.items():
        if n.endswith('.py'):
            ast.parse(b.decode(), filename=n)
    hashes = {n:sha(b) for n,b in files.items()}
    if a.validate_only:
        print(json.dumps(dict(status='V6_SCRATCH_TRANSFORM_CHECK_PASS', hashes=hashes)))
        return
    assert REVIEW.read_bytes() == review
    files['SHA256SUMS'] = ''.join(f'{h}  {n}\n' for n,h in hashes.items()).encode()
    archive = R/'x12-storage-scratch-v6.tar.gz'
    manifest = R/'STORAGE_SCRATCH_MANIFEST_v6.json'
    assert not manifest.exists() and not archive.exists()
    with tarfile.open(archive, 'x:gz') as tf:
        for n,b in files.items():
            t = tarfile.TarInfo(n)
            t.size = len(b)
            tf.addfile(t, io.BytesIO(b))
    result = dict(status='SCRATCH_IO_V6_FROZEN_NOT_SUBMITTED', remote_root=ROOT, mdt=1, project=231181,
                  archive=str(archive), archive_sha256=sha(archive.read_bytes()), files=hashes,
                  manifest_sha256=sha(files['SHA256SUMS']), review_sha256=sha(review), requested_SU=5/60,
                  new_training_transitions=0)
    with manifest.open('x',encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--expected-review-sha256', required=True)
    p.add_argument('--validate-only', action='store_true')
    main(p.parse_args())
