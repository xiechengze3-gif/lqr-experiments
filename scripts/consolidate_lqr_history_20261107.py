"""Archive selected retired LQR outputs and verify each file before unlinking it."""
import collections
import concurrent.futures
import errno
import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path, PurePosixPath


SCRATCH = Path('/scratch/user/changze')
BASE = SCRATCH / 'lqr_experiments'
DEST = BASE / 'archives/inode-consolidation-20261105/20261107'
TARGET = 100000
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
HISTORY = [
    ('x9-formal', 'results/x9-20261106/formal-v1'),
    ('x10b-formal', 'results/x10-20261106/X10b/formal-v1'),
    ('x12-failed-formal', 'results/x12-20261106/formal-v1'),
    ('x6a-formal', 'results/x6-20261101/X6a/formal'),
    ('x6a-ce', 'results/x6-20261101/X6a/CE-addition-v1'),
    ('x6b-formal', 'results/x6-20261101/X6b/formal-v1'),
    ('x7-formal', 'results/x7-20261102/formal-v1'),
    ('supplement-x1', 'results/supplement-20261101/X1/formal'),
    ('supplement-x2', 'results/supplement-20261101/X2/formal'),
    ('supplement-x3', 'results/supplement-20261101/X3/formal'),
    ('oct25-results-snapshot', 'local-archives/20261025/snapshot/results'),
    ('ce-npg-arguments-raw', 'results/ce-npg-arguments-20261028/raw'),
    ('ce-equal-modes-policies', 'results/ce500-equal-modes-20261020/policies'),
    ('ce-matched-gap-policies', 'results/ce500-matched-gap-20261019/policies'),
    ('ce-common-rank-policies', 'results/ce500-common-rank-extension-20261023-v2/policies'),
    ('aligned-tasks', 'results/aligned-b41df7278218861f/tasks'),
    ('x9-resource', 'results/x9-20261106/resource-v1'),
    ('x9-logs', 'results/x9-20261106/logs'),
    ('x6-logs', 'results/x6-20261101/logs'),
    ('x10b-resource', 'results/x10-20261106/X10b/resource-v2'),
    ('x10b-logs', 'results/x10-20261106/X10b/logs'),
    ('x7-resource', 'results/x7-20261102/resource-v1'),
    ('ce-common-constants-policies', 'results/ce500-common-constants-20261022/policies'),
    ('ce-random-a-policies', 'results/ce500-random-a-20261020/policies'),
    ('ce-independent-policies', 'results/ce500-independent-stabilizer-20261022/policies'),
    ('ce-rank4-policies', 'results/ce500-rank4-extension-20261020/policies'),
    ('oct25-project-snapshot', 'local-archives/20261025/snapshot/project'),
]
SEALED = {
    'x9-formal': (BASE / 'tmp/x9-20261106/x9-report-v1.tar.gz',
                  'e21ca284e00214c84559282497f276e764c947fe3c2a40aec997b1fb122765b2', 'formal-v1/'),
    'x10b-formal': (BASE / 'tmp/x10-20261106/x10b-report-v1.tar.gz',
                    'ca40b9bc7466d8bfb14a8caaf05094d1944d1c0b8ce93b5708ea69de4d30a77a', 'formal-v1/'),
    'x12-failed-formal': (Path('/home/changze/lqr-x12-failure-transit-20261107-v1/x12-failed-formal-v1.tar.gz'),
                          '051d016a353fc4c743e9f7aee5ae6f8ddb0d3a17212d13c1fcd8081f65f9b4f2', 'results/formal-v1/'),
    'x6b-formal': (BASE / 'archives/inode-consolidation-20261105/x6b-formal-v1.tar.gz',
                   'ef73e5871033bae2a1065ae047ad7e49bde5b9f6eed72738765c61df94c7a5e2', 'X6b/formal-v1/'),
}
for name, original, prefix in [('x9-resource', 'x9-formal', 'resource-v1/'),
                               ('x9-logs', 'x9-formal', 'logs/'),
                               ('x10b-resource', 'x10b-formal', 'resource-v2/'),
                               ('x10b-logs', 'x10b-formal', 'logs/')]:
    source, digest, _ = SEALED[original]
    SEALED[name] = (source, digest, prefix)
HEALTHCARE_RUN = SCRATCH / 'healthcare_project1_2/prostate-task29-a20-20261107-fd9637e7'
UNRELATED_JOBS = {
    '20430528': (0, '5aa9d4ffdeaf5b1a627404483b17c5b2987b7114f8ff73745275f3ed61ff87bf'),
    '20430531': (1, '6420f27a7373a9cc3bc07b0995ab72a46f57411a8e482c372fe70135cc62404c'),
    '20430532': (2, '9549bd89a33192332772bf8a273b1f1d76d1d7ca8b7e88fb41ea8e8f20087a72'),
}


def sha(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()


class HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, count):
        block = self.stream.read(count)
        self.digest.update(block)
        return block


def check_archive(path, expected_names=None):
    entries = {}
    with path.open('rb') as raw:
        reader = HashingReader(raw)
        mode = 'r|gz' if path.name.endswith('.gz') else 'r|'
        with tarfile.open(fileobj=reader, mode=mode, bufsize=1024 * 1024) as archive:
            for member in archive:
                if member.isdir():
                    continue
                name = member.name
                relative = PurePosixPath(name)
                if (not member.isfile() or name in entries or relative.is_absolute() or
                        '..' in relative.parts or str(relative) != name):
                    raise RuntimeError('Unexpected archive member: ' + name)
                with archive.extractfile(member) as content:
                    entries[name] = {'member': name, 'bytes': member.size, 'sha256': sha(content)}
        while reader.read(1024 * 1024):
            pass
    if expected_names is not None and entries.keys() != expected_names:
        raise RuntimeError('Archive member names disagree with inventory')
    return entries, reader.digest.hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.part')
    with temporary.open('w') as stream:
        json.dump(value, stream)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def idle():
    result = subprocess.check_output(['squeue', '-h', '-u', 'changze', '-o', '%A'], universal_newlines=True)
    own_job = os.environ['SLURM_JOB_ID']
    for job in set(result.split()) - {own_job}:
        if job not in UNRELATED_JOBS:
            raise RuntimeError('An unreviewed user job is active: ' + job)
        shard, digest = UNRELATED_JOBS[job]
        command = HEALTHCARE_RUN / 'release/jobs/shard{}.sbatch'.format(shard)
        detail = subprocess.check_output(['scontrol', 'show', 'job', '-o', job], universal_newlines=True)
        if ('Command=' + str(command) + ' ' not in detail or
                'WorkDir=' + str(HEALTHCARE_RUN / 'release') + ' ' not in detail or str(BASE) in detail):
            raise RuntimeError('Job paths no longer match the reviewed healthcare run: ' + job)
        with command.open('rb') as stream:
            if sha(stream) != digest:
                raise RuntimeError('Reviewed healthcare job script changed: ' + job)


def inventory(root, keep_root_files):
    if root.resolve() != root or not root.is_dir():
        raise RuntimeError('Unexpected source directory: ' + str(root))
    files = []
    directories = []
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(str(directory)) as entries:
            for entry in entries:
                path = directory / entry.name
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                    directories.append(path)
                elif entry.is_file(follow_symlinks=False) and (directory != root or not keep_root_files):
                    files.append(path.relative_to(root).as_posix())
    return sorted(files), directories


def identity(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_size, info.st_mtime_ns)


def consolidate(root, selected, archive, digest, name):
    write_json(DEST / (name + '.plan.json'), dict(archive=str(archive), archive_sha256=digest,
               source_root=str(root), files=selected))
    idle()
    grouped = collections.defaultdict(list)
    for relative, entry in selected.items():
        path = PurePosixPath(relative)
        grouped[path.parts[:-1]].append((path.name, entry, relative))

    def process(group):
        parent, entries = group
        directory = os.open(str(root), DIR_FLAGS)
        results = []
        try:
            for part in parent:
                child = os.open(part, DIR_FLAGS, dir_fd=directory)
                os.close(directory)
                directory = child
            for basename, entry, relative in entries:
                try:
                    descriptor = os.open(basename, FILE_FLAGS, dir_fd=directory)
                    with os.fdopen(descriptor, 'rb') as source:
                        before = os.fstat(source.fileno())
                        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or
                                before.st_size != entry['bytes'] or sha(source) != entry['sha256']):
                            results.append((relative, 'kept'))
                            continue
                        current = os.stat(basename, dir_fd=directory, follow_symlinks=False)
                        if identity(before) != identity(current) or identity(before) != identity(os.fstat(source.fileno())):
                            results.append((relative, 'kept'))
                            continue
                        os.unlink(basename, dir_fd=directory)
                        results.append((relative, 'deleted'))
                except FileNotFoundError:
                    results.append((relative, 'absent'))
            return results
        finally:
            os.close(directory)

    tally = collections.Counter()
    with (DEST / (name + '.removed.jsonl')).open('x', buffering=1) as log:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for batch in pool.map(process, sorted(grouped.items())):
                for relative, status in batch:
                    log.write(json.dumps({'file': relative, 'status': status}) + '\n')
                    tally[status] += 1
                if sum(tally.values()) // 5000 > (sum(tally.values()) - len(batch)) // 5000:
                    print(name, dict(tally), flush=True)
        os.fsync(log.fileno())
    return tally


def reused_archive(name, root, files):
    source, expected_hash, prefix = SEALED[name]
    archive = DEST / (name + '.delivery.tar.gz')
    try:
        os.link(str(source), str(archive))
    except OSError as error:
        if error.errno not in (errno.EXDEV, errno.EPERM, errno.EDQUOT):
            raise
        shutil.copyfile(str(source), str(archive))
    entries, digest = check_archive(archive)
    if digest != expected_hash:
        raise RuntimeError('Existing delivery SHA256 mismatch: ' + name)
    selected = {file: entries[prefix + file] for file in files if prefix + file in entries}
    print(name, 'verified delivery members', len(entries), 'covering', len(selected), flush=True)
    if not selected:
        raise RuntimeError('Existing delivery does not map to source paths: ' + name)
    return consolidate(root, selected, archive, digest, name + '.delivery')


def pack_remaining(name, root, files):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        sizes = pool.map(lambda file: (root / file).stat().st_size, files)
        required = sum(sizes) + 4096 * len(files)
    free = int(subprocess.check_output(['df', '-B1', '--output=avail', str(DEST)]).split()[-1])
    if required + 10 * 1024**3 > free:
        raise RuntimeError('Insufficient scratch space for verified archive: ' + name)
    list_path = DEST / (name + '.members.nul')
    with list_path.open('xb') as stream:
        for file in files:
            stream.write(os.fsencode(file) + b'\0')
    archive = DEST / (name + '.tar')
    partial = archive.with_suffix('.building')
    if archive.exists() or partial.exists():
        raise RuntimeError('Inspect earlier archive before retry')
    subprocess.check_call(['tar', '--format=pax', '--no-recursion', '--hard-dereference', '--sparse',
                           '-C', str(root), '--null', '--verbatim-files-from', '-T', str(list_path),
                           '-cf', str(partial)])
    entries, digest = check_archive(partial, set(files))
    partial.rename(archive)
    print(name, 'verified newly packed members', len(entries), flush=True)
    tally = consolidate(root, entries, archive, digest, name)
    list_path.unlink()
    if tally['kept'] or tally['absent']:
        raise RuntimeError('A source changed after packing: ' + name)
    return tally


def resume_verified_pack(name, root, files):
    plan_path = DEST / (name + '.plan.json')
    archive = DEST / (name + '.tar')
    if (DEST / (name + '.removed.jsonl')).exists():
        raise RuntimeError('A previous unlink attempt needs reconciliation: ' + name)
    plan = json.loads(plan_path.read_text())
    if plan['archive'] != str(archive) or plan['source_root'] != str(root) or archive.resolve() != archive:
        raise RuntimeError('Resume plan paths changed: ' + name)
    entries, digest = check_archive(archive, set(files))
    if digest != plan['archive_sha256'] or entries != plan['files']:
        raise RuntimeError('Resume archive failed verification: ' + name)
    print(name, 'reverified previous archive', len(entries), flush=True)
    tally = consolidate(root, entries, archive, digest, name)
    (DEST / (name + '.members.nul')).unlink()
    if tally['kept'] or tally['absent']:
        raise RuntimeError('A source changed after resuming: ' + name)
    return tally


def count_scratch():
    def fail(error):
        raise error
    files = directories = 0
    for _, subdirs, names in os.walk(str(SCRATCH), onerror=fail, followlinks=False):
        files += len(names)
        directories += len(subdirs)
    return {'files_or_links': files, 'directories': directories, 'entries': files + directories}


def quota_counts():
    counts = {}
    for key, flag, owner in [('user', '-u', 'changze'), ('project', '-p', '231181')]:
        output = subprocess.check_output(['lfs', 'quota', flag, owner, str(SCRATCH)], universal_newlines=True)
        # The filesystem column can wrap onto the preceding line on compute nodes.
        counts[key] = int(output.strip().splitlines()[-1].split()[-4].rstrip('*'))
    return counts


def main():
    if 'SLURM_JOB_ID' not in os.environ or DEST.resolve() != DEST or BASE.resolve() != BASE:
        raise RuntimeError('Run in the prepared Slurm maintenance allocation')
    lock = (DEST / 'maintenance.lock').open('a')
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    idle()
    report_path = DEST / 'summary.json'
    resume = os.environ.get('LQR_RESUME_JOB_ID')
    quota_followup = os.environ.get('LQR_QUOTA_FOLLOWUP') == '1'
    if resume:
        report = json.loads(report_path.read_text())
        expected_status = 'PASS' if quota_followup else 'RUNNING'
        if report['status'] != expected_status or report['job_id'] != resume:
            raise RuntimeError('Prior execution does not match the reviewed receipt')
        if quota_followup:
            report['quota_followup_before'] = quota_counts()
            report['status'] = 'RUNNING'
        report.setdefault('prior_jobs', []).append(resume)
        report['job_id'] = os.environ['SLURM_JOB_ID']
    else:
        if report_path.exists():
            raise RuntimeError('Inspect previous execution before resuming')
        report = dict(status='RUNNING', job_id=os.environ['SLURM_JOB_ID'], target=TARGET,
                      before=count_scratch(), groups=[])
    write_json(report_path, report)
    completed = {group['name'] for group in report['groups']}
    removed = sum(group['files'] + group['directories'] for group in report['groups'])
    for name, relative in HISTORY:
        if name in completed:
            continue
        if quota_followup and max(quota_counts().values()) <= TARGET:
            report['after'] = count_scratch()
            if report['after']['entries'] <= TARGET:
                break
        idle()
        root = BASE / relative
        keep_root_files = root.name in ('formal-v1', 'formal', 'CE-addition-v1')
        files, directories = inventory(root, keep_root_files)
        if not files:
            continue
        print(name, 'loose files', len(files), flush=True)
        tally = collections.Counter()
        if name in SEALED:
            tally.update(reused_archive(name, root, files))
            files, _ = inventory(root, keep_root_files)
        if files and (DEST / (name + '.plan.json')).exists():
            if not resume or name != 'supplement-x3':
                raise RuntimeError('Unexpected previously verified plan: ' + name)
            tally.update(resume_verified_pack(name, root, files))
        elif files:
            tally.update(pack_remaining(name, root, files))
        empty = 0
        for path in sorted(directories, key=lambda path: len(path.parts), reverse=True):
            try:
                path.rmdir()
                empty += 1
            except OSError as error:
                if error.errno not in (errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST):
                    raise
        removed += tally['deleted'] + empty
        report['groups'].append(dict(name=name, source=str(root), files=tally['deleted'], directories=empty))
        write_json(report_path, report)
        print(name, 'finished', report['groups'][-1], flush=True)
        # Leave room for the archive names, indexes, logs, and Slurm receipt.
        if not quota_followup and report['before']['entries'] - removed <= TARGET - 500:
            report['after'] = count_scratch()
            if report['after']['entries'] <= TARGET:
                break
    else:
        report['after'] = count_scratch()
    report['quota_after'] = quota_counts()
    met = report['after']['entries'] <= TARGET
    if quota_followup:
        met = met and max(report['quota_after'].values()) <= TARGET
    report['status'] = 'PASS' if met else 'TARGET_NOT_MET'
    write_json(report_path, report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
