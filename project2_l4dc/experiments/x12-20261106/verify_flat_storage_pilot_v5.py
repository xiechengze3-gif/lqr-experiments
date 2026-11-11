"""Verify all downloaded pilot files, and every encoded archive member."""
import json
from pathlib import Path

from prepare_recovery_v5 import pilot_limits
from virtual_task_store_v2 import file_sha, verify_archive


def main():
    root = Path(__file__).resolve().parent
    folder = root / 'delivery-storage-flat-v5'
    remote = json.loads((folder / 'REMOTE_SEAL.json').read_bytes())
    m = json.loads((root / 'STORAGE_FLAT_MANIFEST_v5.json').read_bytes())
    assert all((folder / n).stat().st_size == meta['bytes'] and file_sha(folder / n) == meta['sha256']
               for n, meta in remote['files'].items())
    job, state, elapsed, tres, exitcode = remote['slurm']
    proof = dict(job=job, allocation_state=state, elapsed_seconds=int(elapsed), zero_observations=True,
                 allocation_billing=1, actual_SU=int(elapsed)/3600, files=remote['files'])
    assert {'cpu=1','billing=1'} <= set(tres.split(','))
    if state != 'COMPLETED' or exitcode != '0:0':
        proof['status'] = 'FAILED_IO_ATTEMPT_FILES_VERIFIED_ON_E'
    else:
        p = json.loads((folder / 'pilot-DONE.json').read_bytes())
        assert p['job'] == job and p['source_sha256'] == m['files']['pilot_virtual_store_v5.py']
        assert p['store_source_sha256'] == m['files']['virtual_task_store_v2.py']
        proof['limits'] = pilot_limits(p)
        assert len(p['results']) == 2
        for result in p['results']:
            name = 'pilot-' + result['algorithm']
            assert result['archive_sha256'] == remote['files'][name + '.tar']['sha256']
            assert result['journal_sha256'] == remote['files'][name + '.jsonl']['sha256']
            assert verify_archive(folder / (name+'.tar'), result['members']) == len(result['members'])
        proof.update(status='ACTIVE_IO_PILOT_ARCHIVES_VERIFIED_ON_E',
                     pilot_done_sha256=remote['files']['pilot-DONE.json']['sha256'])
    with (root / 'STORAGE_FLAT_IO_VERIFIED_v5.json').open('x', encoding='utf-8') as f:
        json.dump(proof, f, indent=2)
    print(json.dumps({k:v for k,v in proof.items() if k != 'files'}))


if __name__ == '__main__':
    main()
