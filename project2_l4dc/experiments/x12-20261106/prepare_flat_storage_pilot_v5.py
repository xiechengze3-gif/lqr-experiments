"""Prepare a storage-only alternative that needs one ordinary directory."""
import argparse
import ast
import hashlib
import io
import json
import tarfile
from pathlib import Path


def main(expected_review, validate_only=False):
    root = Path(__file__).resolve().parent
    review = (root.parents[1] / 'CLAUDE_TASK.md').read_bytes()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    assert sha(review) == expected_review
    m = json.loads((root / 'STORAGE_CORRECTION_MANIFEST_v4r1.json').read_text())
    with tarfile.open(m['archive'], 'r:gz') as tf:
        files = {n: tf.extractfile(n).read() for n in m['files']}
    assert {n: sha(b) for n, b in files.items()} == m['files']
    files['CLAUDE_TASK_authorized.md'] = review
    remote = '/home/changze/lqr-x12-flat-20261107-v5'
    old_remote = m['remote_root']

    def change(s, a, b):
        assert s.count(a) == 1, a
        return s.replace(a, b)

    pilot = files.pop('pilot_virtual_store_v4.py').decode()
    begin = pilot.index("    assert not a.out.exists()")
    end = pilot.index('    stat=os.statvfs', begin)
    pilot = pilot[:begin] + '''    assert a.out.is_dir()
    names = ['pilot-' + alg + ext for alg in ('NPG','PI') for ext in ('.tar','.jsonl')]
    names.append('pilot-DONE.json')
    assert not any((a.out / n).exists() for n in names), 'Reconcile, do not replay.'
    if os.environ.get('SLURM_JOB_ID'):
        assert subprocess.check_output(['lfs','getdirstripe','-i',str(a.out)],text=True).strip()=='0'
        assert subprocess.check_output(['lfs','getstripe','-m',str(a.out/'placement-probe.txt')],text=True).strip()=='0'
''' + pilot[end:]
    pilot = change(pilot, "a.out/(alg+'.tar'),a.out/(alg+'.jsonl')",
                   "a.out/('pilot-'+alg+'.tar'),a.out/('pilot-'+alg+'.jsonl')")
    pilot = change(pilot, "(a.out/'DONE.json').open", "(a.out/'pilot-DONE.json').open")
    pilot = change(pilot, 'output_MDT=0,named_reference_files_created=0',
                   'output_MDT=0,flat_output_namespace=True,named_reference_files_created=0')
    ast.parse(pilot)
    files['pilot_virtual_store_v5.py'] = pilot.encode()

    sub = files.pop('submit_storage_correction_v4.py').decode().replace(old_remote, remote)
    sub = sub.replace('submit_storage_correction_v4.py', 'submit_flat_storage_pilot_v5.py').replace('storage-io-v4', 'storage-io-v5')
    sub = change(sub, "    dest=ROOT/'submissions/storage-io-v5';assert not dest.exists(),'Never replay an earlier submission attempt.'\n    assert not (ROOT/'pilot-out-v4').exists()",
                 "    assert not any(ROOT.glob('submit-*.json')) and not any(ROOT.glob('pilot-*.tar')) and not (ROOT/'pilot-DONE.json').exists(), 'Reconcile, do not replay.'")
    sub = change(sub, "    subprocess.check_call(['lfs','mkdir','-i','0','-c','1',str(dest)])",
                 "    assert call(['lfs','getstripe','-m',str(ROOT/'placement-probe.txt')]).strip()=='0'")
    for n in ('BEGIN','RESPONSE','DONE'):
        sub = change(sub, f"dest/'{n}.json'", f"ROOT/'submit-{n}.json'")
    ast.parse(sub)
    files['submit_flat_storage_pilot_v5.py'] = sub.encode()
    sbatch = files['pilot.sbatch'].decode().replace(old_remote, remote)
    sbatch = sbatch.replace('/tmp/changze-x12-storage-v4-', '/tmp/changze-x12-storage-v5-')
    sbatch = change(sbatch, 'pilot_virtual_store_v4.py', 'pilot_virtual_store_v5.py')
    sbatch = change(sbatch, '"$root/pilot-out-v4"', '"$root"')
    files['pilot.sbatch'] = sbatch.encode()
    plan = json.loads(files['pilot-plan-v4.json'])
    plan.update(flat_output_namespace=True, output_MDT=0, placement_requires_verified_ordinary_mkdir=True,
                prior_corrected_v4r1_jobs=0)
    files['pilot-plan-v4.json'] = (json.dumps(plan, indent=2) + '\n').encode()

    hashes = {n: sha(b) for n, b in files.items()}
    files['SHA256SUMS'] = ''.join(f'{h}  {n}\n' for n, h in hashes.items()).encode()
    if validate_only:
        print(json.dumps(dict(status='V5_TRANSFORM_AND_SYNTAX_CHECK_PASS', hashes=hashes)))
        return
    archive = root / 'x12-storage-flat-v5.tar.gz'
    receipt = root / 'STORAGE_FLAT_MANIFEST_v5.json'
    assert not archive.exists() and not receipt.exists()
    assert (root.parents[1] / 'CLAUDE_TASK.md').read_bytes() == review
    with tarfile.open(archive, 'x:gz') as tf:
        for n, b in files.items():
            item = tarfile.TarInfo(n)
            item.size = len(b)
            tf.addfile(item, io.BytesIO(b))
    m.update(status='STORAGE_FLAT_V5_FROZEN_NOT_SUBMITTED', archive=str(archive),
             archive_sha256=sha(archive.read_bytes()), manifest_sha256=sha(files['SHA256SUMS']),
             review_sha256=sha(review), remote_root=remote, files=hashes,
             changes=['ordinary directory with verified MDT0 placement', 'flat filenames, no physical subdirectories'])
    with receipt.open('x') as f:
        json.dump(m, f, indent=2)
    print(m['archive_sha256'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-review-sha256', required=True)
    parser.add_argument('--validate-only', action='store_true')
    a = parser.parse_args()
    main(a.expected_review_sha256, a.validate_only)
