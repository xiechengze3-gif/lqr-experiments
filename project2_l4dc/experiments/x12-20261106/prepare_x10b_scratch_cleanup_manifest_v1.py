"""Create an exact, read-only cleanup proposal; no Grace mutation."""
import collections
import csv
import hashlib
import json
import re
from pathlib import Path, PurePosixPath


R = Path(__file__).resolve().parent
X10 = R.parent / 'x10-20261106'
OUT = R / 'scratch-cleanup-proposal-20261107-v1'
GRACE = PurePosixPath('/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b/formal-v1')
TARGET = {0: 0, 1: 20_000}
REVIEW_SHA = '1694ef429c005cc6677f68a934d5a878c2e097ef0d01f96b7f11a2c411694f08'
ARCHIVE_SHA = 'ca40b9bc7466d8bfb14a8caaf05094d1944d1c0b8ce93b5708ea69de4d30a77a'
FORMAT = re.compile(r'n(24|36|48|72)-new-five-(NPG|PI)/task-(?:[0-9]|[12][0-9]|3[01])/\2-r[0-9]+/'
                    r'(?:stage-\d{3}-(?:dense|truncated)|checkpoint-\d{3})\.npz')


def file_sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def main():
    review = R.parents[1] / 'CLAUDE_TASK.md'
    assert file_sha(review) == REVIEW_SHA, 'Review changed; reread before selecting any files.'
    local_root = (X10 / 'delivery-actor-report-v1' / 'formal-v1').resolve(strict=True)
    assert str(local_root).startswith('E:\\')
    seal = X10 / 'downloads-actor-report-v1/x10b-report-v1.tar.json'
    receipt = X10 / 'delivery-actor-report-v1.verified.json'
    coverage = X10 / 'ACTOR_FULL_RAW_E_COVERAGE_v1.json'
    old_proof, cov, sealed = load(receipt), load(coverage), load(seal)
    assert old_proof['status'] == 'VERIFIED_EXTRACTED_X10B_DELIVERY' and old_proof['files'] == 64314
    assert cov['status'] == 'ALL256_FORMAL_RAW_TASKS_VERIFIED_ON_E' and cov['bundles'] == 256
    assert file_sha(seal) == cov['archive_manifest_sha256'] == '9fb381a0a93b4eb74f1f39c2ccfedf2b892b1172c35133b3a38edfe90274fe4a'
    assert old_proof['archive_sha256'] == cov['archive_sha256'] == sealed['archive_sha256'] == ARCHIVE_SHA
    verify = dict(e_receipt=str(receipt), e_receipt_sha256=file_sha(receipt),
                  e_coverage=str(coverage), e_coverage_sha256=file_sha(coverage),
                  sealed_archive_sha256=ARCHIVE_SHA, sealed_member_manifest=str(seal),
                  sealed_member_manifest_sha256=file_sha(seal))
    entries = {x['path']: x for x in sealed['files']}
    assert len(entries) == len(sealed['files']) == old_proof['files']
    inv = OUT / 'REMOTE_RAW_NPZ_INVENTORY.tsv'
    present = {}
    excluded = []
    for line in inv.read_text(encoding='utf-8-sig').splitlines():
        mdt, path = line.split('\t', 1)
        assert mdt in ('0','1') and FORMAT.fullmatch(path) and path not in present, (mdt, path)
        present[path] = int(mdt)
    n = collections.Counter()
    groups = collections.Counter()
    chosen = []
    for name, mdt in sorted(present.items()):
        if n[mdt] == TARGET[mdt]:
            continue
        archive_name = 'formal-v1/' + name
        local = local_root.joinpath(*PurePosixPath(name).parts)
        meta = entries.get(archive_name)
        try:
            if not meta or local.is_symlink() or not local.resolve(strict=True).is_relative_to(local_root) or not local.is_file():
                excluded.append(dict(path=name, mdt=mdt, reason='missing or out-of-scope E copy/verification'))
                continue
            if local.stat().st_size != meta['bytes'] or file_sha(local) != meta['sha256']:
                excluded.append(dict(path=name, mdt=mdt, reason='E file differs from original seal'))
                continue
        except OSError as ex:
            excluded.append(dict(path=name, mdt=mdt, reason=str(ex)))
            continue
        n[mdt] += 1
        groups[name.split('/')[0]] += 1
        chosen.append(dict(grace_path=str(GRACE / name), mdt=mdt, bytes=meta['bytes'], sha256=meta['sha256'],
                           e_path=str(local), e_seal_member=archive_name, e_verification_record=str(receipt)))
    assert len(chosen) == 20_000 and n == collections.Counter(TARGET), (n, len(present), len(excluded))
    assert file_sha(review) == REVIEW_SHA
    manifest = OUT / 'DELETE_CANDIDATES_v1.tsv'
    fields = ['grace_path','mdt','bytes','sha256','e_path','e_seal_member','e_verification_record']
    with manifest.open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, dialect='excel-tab', lineterminator='\n')
        w.writeheader()
        w.writerows(chosen)
    proposal = dict(status='REVIEWABLE_DUPLICATE_CLEANUP_PROPOSAL_NO_DELETION', selected_files=len(chosen),
        selected_bytes=sum(x['bytes'] for x in chosen), selected_MDT=dict(n), groups=dict(groups),
        remote_inventory_files=len(present), remote_inventory_sha256=file_sha(inv), exclusions=excluded,
        exact_remote_root=str(GRACE), included_file_types='original stage arrays and checkpoint NPZ only',
        original_backup_proof=verify, manifest=str(manifest), manifest_sha256=file_sha(manifest), review_sha256=REVIEW_SHA,
        local_backup_files_rehashed=len(chosen), before_scratch_files=250000, before_scratch_file_limit=250000,
        proposed_new_X12_parent='/scratch/user/changze/lqr_experiments/tmp (observed MDT1; actual new placement must be verified)',
        deleted_files=0, remote_writes=0, required_immediate_remote_rehash_before_any_unlink=True)
    with (OUT / 'CLEANUP_PROPOSAL_v1.json').open('x', encoding='utf-8') as f:
        json.dump(proposal, f, indent=2)
    print(json.dumps({k:v for k,v in proposal.items() if k not in ('original_backup_proof','exclusions')}))


if __name__ == '__main__':
    main()
