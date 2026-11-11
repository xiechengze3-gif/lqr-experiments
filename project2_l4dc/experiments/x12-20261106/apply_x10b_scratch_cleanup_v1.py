"""Unlink only a separately authorized exact manifest; rehash each file first."""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath


ROOT = Path('/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b/formal-v1')
SCRATCH = '/scratch/user/changze'
USER = 'changze'
FORMAT = re.compile(r'n(24|36|48|72)-new-five-(NPG|PI)/task-(?:[0-9]|[12][0-9]|3[01])/\2-r[0-9]+/'
                    r'(?:stage-\d{3}-(?:dense|truncated)|checkpoint-\d{3})\.npz')
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def call(*cmd):
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)


def quota():
    return dict(utc=utc(), raw_project_quota=call('lfs','quota','-v','-p','231181',SCRATCH),
                df_bytes=call('df','-B1','--output=size,used,avail',SCRATCH), df_files=call('df','-i',SCRATCH))


def exclusive_json(path, obj):
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def identity(s):
    return s.st_dev, s.st_ino, s.st_uid, s.st_nlink, s.st_size, s.st_ctime_ns, s.st_mtime_ns, s.st_mode


def checked_unlink(root_fd, row):
    relative = row['relative']
    segments = relative.parts
    fd = os.dup(root_fd)
    try:
        for component in segments[:-1]:
            child = os.open(component, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        name = segments[-1]
        # Check metadata before open to avoid special files; O_NOFOLLOW protects the open.
        b = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(b.st_mode) or b.st_uid != os.getuid() or b.st_nlink != 1 or b.st_size != row['bytes']:
            return dict(status='KEPT', reason='not an owned single-link regular file of the registered size')
        with os.fdopen(os.open(name, FILE_FLAGS, dir_fd=fd), 'rb') as f:
            first = os.fstat(f.fileno())
            if identity(first) != identity(b):
                return dict(status='KEPT', reason='changed before hash')
            actual = hashlib.file_digest(f, 'sha256').hexdigest()
            if actual != row['sha256']:
                return dict(status='KEPT', reason='SHA differs from E', observed_sha256=actual)
            last = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if identity(last) != identity(first) or identity(os.fstat(f.fileno())) != identity(first):
                return dict(status='KEPT', reason='changed during hash', observed_sha256=actual)
            os.unlink(name, dir_fd=fd)
            return dict(status='DELETED', matched_sha256=actual, logical_bytes=last.st_size,
                        allocated_bytes_at_unlink=last.st_blocks*512)
    except OSError as ex:
        return dict(status='KEPT', reason=repr(ex))
    finally:
        os.close(fd)


def main(a):
    assert re.fullmatch('[0-9a-f]{64}', a.approved_manifest_sha256)
    expected_work = Path('/tmp/changze-x12-scratch-cleanup-' + a.approved_manifest_sha256[:16])
    assert a.work == expected_work and a.work.resolve(strict=True) == expected_work
    assert a.work.stat().st_uid == os.getuid() and (a.work.stat().st_mode & 0o077) == 0
    assert ROOT.resolve(strict=True) == ROOT
    assert not call('squeue','-r','-h','-u',USER,'-o','%i').strip()
    manifest = a.work / 'DELETE_CANDIDATES_v1.tsv'
    payload = manifest.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == a.approved_manifest_sha256
    rows = []
    for row in csv.DictReader(payload.decode().splitlines(), dialect='excel-tab'):
        remote = PurePosixPath(row['grace_path'])
        relative = remote.relative_to(PurePosixPath(ROOT.as_posix()))
        assert remote.as_posix() == row['grace_path'] and FORMAT.fullmatch(relative.as_posix())
        assert row['e_path'].startswith('E:\\') and row['e_seal_member'] == 'formal-v1/' + relative.as_posix()
        assert row['e_verification_record'].endswith('delivery-actor-report-v1.verified.json')
        assert row['mdt'] in ('0','1') and re.fullmatch('[0-9a-f]{64}', row['sha256'])
        row['bytes'] = int(row['bytes'])
        assert 0 < row['bytes'] < 4*1024**2
        row['relative'] = relative
        rows.append(row)
    assert len(rows) == len({r['relative'] for r in rows}) == 20_000
    assert Counter(r['mdt'] for r in rows) == {'1':20_000}
    evidence = ['BEGIN.json','FILE_LOG.jsonl','AFTER.json','DONE.json']
    assert not any((a.work/n).exists() for n in evidence), 'Prior attempt; reconcile, never replay.'
    before = quota()
    exclusive_json(a.work/'BEGIN.json', dict(status='ATTEMPT_STARTED_NO_REPLAY', approved_manifest_sha256=a.approved_manifest_sha256,
                   selection_files=len(rows), max_logical_bytes=sum(r['bytes'] for r in rows), before=before))
    tally, bytes_deleted, blocks_deleted = Counter(), 0, 0
    root_fd = os.open(ROOT, DIR_FLAGS)
    try:
        with (a.work/'FILE_LOG.jsonl').open('x', encoding='utf-8', buffering=1) as log:
            for i, row in enumerate(rows, 1):
                result = checked_unlink(root_fd, row)
                tally[result['status']] += 1
                bytes_deleted += result.get('logical_bytes', 0)
                blocks_deleted += result.get('allocated_bytes_at_unlink', 0)
                log.write(json.dumps(dict(index=i, grace_path=row['grace_path'], mdt=row['mdt'],
                                           approved_sha256=row['sha256'], **result))+'\n')
                if i % 256 == 0:
                    os.fsync(log.fileno())
            os.fsync(log.fileno())
    finally:
        os.close(root_fd)
    exclusive_json(a.work/'AFTER.json', quota())
    with (a.work/'FILE_LOG.jsonl').open('rb') as f:
        log_hash = hashlib.file_digest(f, 'sha256').hexdigest()
    result = dict(status='EXACT_MANIFEST_CLEANUP_FINISHED', approval_manifest=a.approved_manifest_sha256,
                  deleted_files=tally['DELETED'], kept_files=tally['KEPT'], logical_bytes_unlinked=bytes_deleted,
                  allocated_bytes_unlinked=blocks_deleted, log_sha256=log_hash,
                  completed_utc=utc(), no_directories_deleted=True, no_new_allocations=True)
    exclusive_json(a.work/'DONE.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--approved-manifest-sha256', required=True)
    p.add_argument('--work', type=Path, required=True)
    main(p.parse_args())
