"""Verify complete actor arrays, archives and receipts on E."""
import hashlib
import json
import sys
import tarfile
from pathlib import Path


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main(folder):
    seal = json.loads((folder/'SEAL.json').read_bytes())
    assert not seal['failures'] and seal['counts'] == {'COMPLETED': seal['tasks']}
    assert {p.name for p in folder.iterdir()} == set(seal['files']) | {'SEAL.json'}
    for name, info in seal['files'].items():
        p = folder/name
        assert p.stat().st_size == info['bytes'] and sha(p) == info['sha256'], name
    finals = []
    for p in sorted(folder.glob('x14*.tar')):
        journal = p.with_suffix('.jsonl')
        final = json.loads(journal.read_bytes().splitlines()[-1])
        assert final['archive_sha256'] == seal['files'][p.name]['sha256']
        manifest = {x['path']:x for x in final['members']}
        with tarfile.open(p, 'r:') as tf:
            entries = tf.getmembers()
            assert len(entries) == len(manifest) and {m.name for m in entries} == set(manifest)
            for member in entries:
                assert member.isfile() and member.size == manifest[member.name]['bytes']
                assert hashlib.sha256(tf.extractfile(member).read()).hexdigest() == manifest[member.name]['sha256']
        finals.append({k:v for k,v in final.items() if k!='members'})
    assert len(finals)==seal['tasks']
    result = dict(status='ARRAY_ARCHIVES_VERIFIED_ON_E', job=seal['job'], tasks=seal['tasks'],
                  seals_sha256=sha(folder/'SEAL.json'), actual_SU=sum(x['elapsed_seconds']/3600 for x in seal['allocations']),
                  accounting=seal['accounting'], finals=finals)
    with (folder/'VERIFIED.json').open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('finals','accounting')}))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
