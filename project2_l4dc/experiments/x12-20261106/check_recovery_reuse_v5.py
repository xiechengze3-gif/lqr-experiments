"""Local I/O smoke check using a real paired path and its sealed evidence."""
import ast
import io
import json
import tarfile
from pathlib import Path

from reconstruct_reuse_for_report_v5 import PREFIX, reproduce
from virtual_task_store_v2 import digest, file_sha


def main():
    root = Path(__file__).resolve().parent
    for n in ('recovery_driver_v5.py', 'recovery_archive_reader_v5.py', 'recovery_report_v5.py',
              'reconstruct_reuse_for_report_v5.py', 'prepare_flat_storage_pilot_v5.py'):
        ast.parse((root / n).read_text(encoding='utf-8'), filename=n)
    original = json.loads((root / 'REUSED_COMPLETE_PATHS_v2.json').read_bytes())
    row = original['reused_paths'][0]
    work = root / 'recovery-reuse-smoke-v5'
    work.mkdir()
    expected = work / 'canonical.tar'
    evidence = work / 'small-evidence.tar.gz'
    with tarfile.open(root / 'reused-complete-paths-v2.tar', 'r:') as old:
        payload = {f['path']: old.extractfile(f['path']).read() for f in row['files']}
        assert all(len(payload[f['path']]) == f['bytes'] and digest(payload[f['path']]) == f['sha256'] for f in row['files'])
        with tarfile.open(expected, 'x:', format=tarfile.USTAR_FORMAT) as want:
            for n, data in payload.items():
                want.addfile(old.getmember(n), io.BytesIO(data))
        with tarfile.open(evidence, 'x:gz') as src:
            for n, data in reversed(list(payload.items())):
                m = tarfile.TarInfo(PREFIX + n)
                m.size = len(data)
                src.addfile(m, io.BytesIO(data))
    expected_sha = file_sha(expected)
    result = reproduce(evidence, work / 'recreated.tar', dict(
        reused_paths=[row], archive_sha256=expected_sha, archive_bytes=expected.stat().st_size,
        old_failed_evidence_archive_sha256=file_sha(evidence)))
    assert result['archive_sha256'] == expected_sha
    assert result['members'] == len(payload)
    print(json.dumps(dict(status='SAVED_PAIRED_PATH_RECONSTRUCTED_BYTE_IDENTICAL',
                          new_training_transitions=0, **result)))


if __name__ == '__main__':
    main()
