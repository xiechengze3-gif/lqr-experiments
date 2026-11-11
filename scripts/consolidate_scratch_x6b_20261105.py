"""Consolidate archived intermediate X6b files while retaining final checkpoints."""
import concurrent.futures
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tarfile
import time
from pathlib import Path, PurePosixPath


SCRATCH = Path('/scratch/user/changze')
BASE = SCRATCH / 'lqr_experiments'
RESULT = BASE / 'results/x6-20261101'
OPS = BASE / 'ops/scratch-file-count-20261105'
PRESERVED = BASE / 'archives/inode-consolidation-20261105'
ARCHIVE_NAME = 'x6b-formal-v1.tar.gz'
MANIFEST_NAME = 'x6b-formal-v1.tar.json'
EXPECTED_SHA256 = 'ef73e5871033bae2a1065ae047ad7e49bde5b9f6eed72738765c61df94c7a5e2'
CHECKPOINT = re.compile(r'checkpoint-([0-9]+)\.(json|npz)')
STAGE = re.compile(r'stage-([0-9]+)-(dense|truncated)\.npz')


def sha_stream(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()


def sha_file(path):
    with path.open('rb') as stream:
        return sha_stream(stream)


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def quiet_queue():
    jobs = subprocess.check_output(
        ['squeue', '-h', '-u', os.environ['USER'], '-o', '%A'],
        universal_newlines=True).split()
    if any(job != os.environ['SLURM_JOB_ID'] for job in jobs):
        raise RuntimeError('Another user job is queued or running')


def retain_link(name):
    source = BASE / 'tmp/x6-20261101' / name
    destination = PRESERVED / name
    if not destination.exists():
        if source.resolve() != source or not source.is_file():
            raise RuntimeError('Unexpected archive source')
        os.link(str(source), str(destination))
    info = destination.lstat()
    if destination.resolve() != destination or not stat.S_ISREG(info.st_mode):
        raise RuntimeError('Unexpected archive destination')
    return destination


def signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def main():
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Run inside the bounded maintenance allocation')
    if SCRATCH.resolve() != SCRATCH or RESULT.resolve() != RESULT:
        raise RuntimeError('Unexpected scratch or result path')
    lock = (OPS / 'maintenance.lock').open('a')
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    quiet_queue()
    complete = json.loads((RESULT / 'X6b/formal-v1/FORMAL_COMPLETE_v1.json').read_text())
    if complete['status'] != 'COMPLETE_COVERAGE_COUNTS_SOURCES':
        raise RuntimeError('Formal completion receipt failed')
    PRESERVED.mkdir(parents=True, exist_ok=True)
    archive = retain_link(ARCHIVE_NAME)
    manifest_path = retain_link(MANIFEST_NAME)
    manifest = json.loads(manifest_path.read_text())
    if manifest['status'] != 'SEALED' or manifest['archive_sha256'] != EXPECTED_SHA256:
        raise RuntimeError('Unexpected sealed archive manifest')
    archive_signature = signature(archive.stat())
    print('Verifying sealed archive SHA256', flush=True)
    if sha_file(archive) != EXPECTED_SHA256:
        raise RuntimeError('Archive SHA256 mismatch')

    entries = {}
    latest = {}
    for entry in manifest['files']:
        path = PurePosixPath(entry['path'])
        if path.is_absolute() or '..' in path.parts or str(path) != entry['path']:
            raise RuntimeError('Unsafe archive member')
        if entry['path'] in entries:
            raise RuntimeError('Duplicate manifest member')
        entries[entry['path']] = entry
        match = CHECKPOINT.fullmatch(path.name)
        if str(path).startswith('X6b/formal-v1/') and match:
            parent = str(path.parent)
            latest[parent] = max(latest.get(parent, -1), int(match.group(1)))

    selected = []
    for entry in manifest['files']:
        path = PurePosixPath(entry['path'])
        match = CHECKPOINT.fullmatch(path.name) or STAGE.fullmatch(path.name)
        parent = str(path.parent)
        if parent in latest and match and int(match.group(1)) < latest[parent]:
            selected.append(entry)
    if len(selected) != 45056:
        raise RuntimeError('Unexpected intermediate-file count')

    verified = set()
    print('Reading back every archived member', flush=True)
    with tarfile.open(str(archive), 'r|gz') as stream:
        for member in stream:
            if member.isdir():
                continue
            if not member.isfile() or member.name not in entries or member.name in verified:
                raise RuntimeError('Unexpected tar member')
            entry = entries[member.name]
            with stream.extractfile(member) as content:
                if member.size != entry['size'] or sha_stream(content) != entry['sha256']:
                    raise RuntimeError('Archived file checksum mismatch')
            verified.add(member.name)
            if len(verified) % 10000 == 0:
                print('Archived members verified {}'.format(len(verified)), flush=True)
    if verified != set(entries) or signature(archive.stat()) != archive_signature:
        raise RuntimeError('Incomplete or changed archive')
    quiet_queue()

    parents = sorted({str(PurePosixPath(entry['path']).parent) for entry in selected})
    def verify_parent(relative):
        path = RESULT / relative
        if path.resolve() != path or not path.is_dir():
            raise RuntimeError('Unexpected checkpoint parent')
        # Each task keeps its final checkpoint and both final-stage files in place.
        final = latest[relative]
        for name in ('checkpoint-{:03d}.json', 'checkpoint-{:03d}.npz',
                     'stage-{:03d}-dense.npz', 'stage-{:03d}-truncated.npz'):
            if not (path / name.format(final)).is_file():
                raise RuntimeError('Final task artifact is missing')
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(verify_parent, parents))

    plan = dict(archive=str(archive), archive_sha256=EXPECTED_SHA256,
                manifest=str(manifest_path), manifest_sha256=sha_file(manifest_path),
                extraction_root=str(RESULT), selected=selected)
    write_json(OPS / 'verified-plan.json', plan)
    receipt = dict(status='ARCHIVE_VERIFIED', job_id=os.environ['SLURM_JOB_ID'],
                   selected_files=len(selected), archive=str(archive),
                   archive_sha256=EXPECTED_SHA256, final_checkpoint_groups_kept=len(latest),
                   archive_members_verified=len(verified), deleted=0, already_absent=0)
    write_json(OPS / 'receipt.json', receipt)
    print('Archive verified. Consolidating {} intermediate files'.format(len(selected)), flush=True)
    cutoff = time.time() - 86400
    uid = os.getuid()

    def consolidate(entry):
        path = RESULT / entry['path']
        try:
            descriptor = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return dict(path=entry['path'], status='already_absent')
        with os.fdopen(descriptor, 'rb') as content:
            before = os.fstat(content.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != uid or
                    before.st_nlink != 1 or before.st_mtime >= cutoff or
                    before.st_size != entry['size']):
                raise RuntimeError('Source metadata changed: {}'.format(path))
            if sha_stream(content) != entry['sha256']:
                raise RuntimeError('Source checksum mismatch: {}'.format(path))
            if signature(os.fstat(content.fileno())) != signature(before):
                raise RuntimeError('Source changed during read')
            if signature(path.lstat()) != signature(before):
                raise RuntimeError('Source path changed before removal')
            path.unlink()
        return dict(path=entry['path'], status='deleted', bytes=entry['size'])

    with (OPS / 'deleted.jsonl').open('a') as log:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for number, result in enumerate(pool.map(consolidate, selected), 1):
                log.write(json.dumps(result) + '\n')
                receipt[result['status']] += 1
                if number % 1000 == 0:
                    log.flush()
                    os.fsync(log.fileno())
                    write_json(OPS / 'receipt.json', receipt)
                    print('Files consolidated {}'.format(number), flush=True)
        log.flush()
        os.fsync(log.fileno())
    if signature(archive.stat()) != archive_signature:
        raise RuntimeError('Preserved archive changed')
    receipt.update(status='PASS', completed_epoch=time.time())
    write_json(OPS / 'receipt.json', receipt)
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
