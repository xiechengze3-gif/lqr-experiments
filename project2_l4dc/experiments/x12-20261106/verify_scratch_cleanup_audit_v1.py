"""Verify the actual exact-manifest outcome and the new scratch quota on E."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load(p):
    return json.loads(p.read_bytes())


def quota(d):
    q = d['raw_project_quota']
    total = next(s.split() for s in q.splitlines() if s.strip().startswith('/scratch/user/changze '))
    rows = [next(s.split() for s in q.splitlines() if f'fs01-MDT000{i}' in s) for i in (0,1)]
    result = dict(files_used=int(total[5]), file_limit=int(total[7]), free_files=int(total[7])-int(total[5]),
                  bytes_used=int(total[1])*1024, byte_limit=int(total[3])*1024,
                  quota_aware_df_bytes=int(d['df_bytes'].splitlines()[-1].split()[-1]))
    for i, mdt in enumerate(rows):
        result[f'MDT{i}_files_used'] = int(mdt[5])
        result[f'MDT{i}_file_limit'] = int(mdt[7])
        result[f'MDT{i}_free_files'] = int(mdt[7])-int(mdt[5])
    return result


def main():
    r = Path(__file__).resolve().parent/'scratch-cleanup-proposal-20261107-v1'
    manifest = r/'DELETE_CANDIDATES_v1.tsv'
    h = sha(manifest)
    p = load(r/'CLEANUP_PROPOSAL_v1.json')
    assert p['manifest_sha256'] == h
    a = r/'grace-audit-v1'
    seal = load(a/'REMOTE_SEAL.json')
    assert seal['complete'] and set(seal['files']) == {'BEGIN.json','FILE_LOG.jsonl','AFTER.json','DONE.json'}
    for n, f in seal['files'].items():
        assert (a/n).stat().st_size == f['bytes'] and sha(a/n) == f['sha256']
    begin, done = load(a/'BEGIN.json'), load(a/'DONE.json')
    assert done['status'] == 'EXACT_MANIFEST_CLEANUP_FINISHED'
    assert begin['approved_manifest_sha256'] == done['approval_manifest'] == h
    assert done['log_sha256'] == sha(a/'FILE_LOG.jsonl')
    assert done['no_directories_deleted'] and done['no_new_allocations']
    n, kept = Counter(), []
    size, blocks = 0, 0
    with manifest.open(encoding='utf-8', newline='') as mf, (a/'FILE_LOG.jsonl').open(encoding='utf-8') as lf:
        for i, (row, line) in enumerate(zip(csv.DictReader(mf, dialect='excel-tab'), lf, strict=True),1):
            log = json.loads(line)
            assert log['index'] == i and log['grace_path'] == row['grace_path'] and log['approved_sha256'] == row['sha256']
            assert log['mdt'] == row['mdt'] == '1'
            n[log['status']] += 1
            if log['status']=='DELETED':
                assert log['matched_sha256'] == row['sha256'] and log['logical_bytes'] == int(row['bytes'])
                size += log['logical_bytes']
                blocks += log['allocated_bytes_at_unlink']
            else:
                assert log['status']=='KEPT'
                kept.append(log)
    assert i == p['selected_files'] == 20_000
    assert (size, blocks, n['DELETED'], n['KEPT']) == (done['logical_bytes_unlinked'], done['allocated_bytes_unlinked'],
                                                     done['deleted_files'], done['kept_files'])
    before, after = quota(begin['before']), quota(load(a/'AFTER.json'))
    result = dict(status='EXACT_MANIFEST_CLEANUP_AUDITED_ON_E', approved_manifest_sha256=h, count_deleted=n['DELETED'],
                  count_kept=n['KEPT'], kept_files=kept, bytes_unlinked=size, allocated_bytes_unlinked=blocks,
                  new_slots_MDT1=after['MDT1_free_files'], new_slots_total=after['free_files'],
                  quota_aware_df_byte_change=after['quota_aware_df_bytes']-before['quota_aware_df_bytes'],
                  before=before, after=after, per_file_log_sha256=done['log_sha256'], no_additional_deletion=True)
    with (r/'CLEANUP_AUDITED_v1.json').open('x',encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k != 'kept_files'}))


if __name__ == '__main__':
    main()
