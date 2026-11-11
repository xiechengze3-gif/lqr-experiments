"""Strict read-only routing for old and new X12 raw archive members."""
import io
import json
import re
import tarfile
from pathlib import Path, PurePosixPath

from recovery_driver_v5 import NEW, OLD
from virtual_task_store_v2 import digest, file_sha


def raw_names(algorithm):
    stages = 16 if algorithm == 'NPG' else 8
    return {'DONE.json'} | {name for t in range(1, stages + 1) for name in (
        f'stage-{t:03d}-dense.npz', f'stage-{t:03d}-truncated.npz',
        f'checkpoint-{t:03d}.npz', f'checkpoint-{t:03d}.json')}


class VerifiedTar:
    def __init__(self, path, members, archive_sha, archive_bytes):
        self.path = path
        assert path.stat().st_size == archive_bytes and file_sha(path) == archive_sha
        self.manifest = {m['path']: m for m in members}
        assert len(self.manifest) == len(members)
        self.archive = tarfile.open(path, 'r:')
        raw = self.archive.getmembers()
        self.entries = {m.name: m for m in raw}
        assert len(raw) == len(self.entries) and set(self.entries) == set(self.manifest)
        for name, member in self.entries.items():
            parts = PurePosixPath(name)
            assert member.isfile() and not parts.is_absolute() and '..' not in parts.parts
            assert member.size == self.manifest[name]['bytes']

    def read(self, name):
        entry = self.entries[name]
        with self.archive.extractfile(entry) as stream:
            data = stream.read()
        assert len(data) == entry.size and digest(data) == self.manifest[name]['sha256'], (str(self.path), name)
        return data

    def verify_all(self):
        for name in self.entries:
            self.read(name)
        return len(self.entries)

    def close(self):
        self.archive.close()


class RawPath:
    def __init__(self, reader, path=PurePosixPath('.')):
        self.reader, self.path = reader, path

    def __truediv__(self, component):
        assert PurePosixPath(component).name == component and component not in ('.', '..')
        return type(self)(self.reader, self.path / component)

    def read_bytes(self):
        return self.reader.read(self.path)

    def read_text(self, encoding='utf-8'):
        return self.read_bytes().decode(encoding)


class ArchiveReader:
    def __init__(self, root, plan, reused, config_sha256, reused_archive=None):
        assert plan['reused_archive_sha256'] == reused['archive_sha256']
        assert reused['complete_reused_paired_paths'] == 296
        self.root = root
        self.tasks = {(t['group'], t['index']): t for t in plan['tasks']}
        assert len(self.tasks) == 64
        self.reused = {p['member_prefix']: p for p in reused['reused_paths']}
        assert len(self.reused) == 296
        assert set(self.reused) == {w['member_prefix'] for t in self.tasks.values() for w in t['runs'] if w['origin'] == OLD}
        old_members = []
        for p, row in self.reused.items():
            expected = {p + '/' + n for n in raw_names(row['algorithm'])}
            assert len(row['files']) == len(expected) and {m['path'] for m in row['files']} == expected
            old_members.extend(row['files'])
        old_path = reused_archive if reused_archive is not None else root / 'reused-complete-paths-v2.tar'
        self.old = VerifiedTar(old_path, old_members,
                               reused['archive_sha256'], reused['archive_bytes'])
        self.current, self.current_key = None, None
        self.config_sha256 = config_sha256
        self.raw = RawPath(self)

    def load_task(self, group, index):
        if self.current_key == (group, index):
            return self.current, self.proof
        if self.current:
            self.current.close()
        assert re.fullmatch(r'n60-nine-(NPG|PI)', group) and 0 <= index < 32
        key = f'{group}-task-{index:02d}'
        assert (self.root / f'{key}.jsonl').stat().st_size <= 320 * 1024
        lines = (self.root / f'{key}.jsonl').read_bytes().splitlines()
        records = [json.loads(line) for line in lines]
        p = records[-1]
        assert p['kind'] == 'TASK_FINAL' and p['status'] == 'COMPLETE'
        assert (p['group'], p['index'], p['config_sha256']) == (group, index, self.config_sha256)
        assert records[-2]['kind'] == 'END_OF_PROCESS' and records[-2]['members'] == len(p['members'])
        assert all(r['sequence'] == i for i, r in enumerate(records[:-1]))
        assert all(r.get('kind') != 'HARD_FAILURE.json' for r in records)
        expected = {'BEGIN.json', 'DONE.json'}
        t = self.tasks[group, index]
        assert len(p['paths']) == len(t['runs']) == 9
        accepted = {OLD: 0, NEW: 0}
        for run, work in zip(p['paths'], t['runs']):
            a, rung = work['algorithm'], work['rung']
            label = a + '-' + work['rung_label']
            assert (run['algorithm'], run['rung'], run['path'], run['origin'], run['primitive_per_arm']) == (
                a, rung, label, work['origin'], work['primitive_per_arm'])
            accepted[run['origin']] += 2 * run['primitive_per_arm']
            if run['origin'] == OLD:
                assert (run['done_sha256'], run['final_stable']) == (work['done_sha256'], work['final_stable'])
            else:
                assert run['origin'] == NEW
                expected.update(label + '/' + n for n in raw_names(a))
        assert accepted == p['accepted_transitions']
        assert len(expected) == len(p['members']) and expected == {m['path'] for m in p['members']}
        self.current = VerifiedTar(self.root / f'{key}.tar', p['members'], p['archive_sha256'], p['archive_bytes'])
        g = json.loads(self.current.read('DONE.json'))
        assert g['status'] == 'COMPLETE' and g['paths'] == p['paths'] and g['transitions_by_origin'] == accepted
        self.current_key, self.proof = (group, index), p
        return self.current, p

    def read(self, path):
        group, task, *suffix = path.parts
        match = re.fullmatch(r'task-(0|[1-9][0-9]*)', task)
        assert match is not None and len(suffix) in (1, 2)
        current, p = self.load_task(group, int(match.group(1)))
        if len(suffix) == 2:
            pair = next(r for r in p['paths'] if r['path'] == suffix[0])
            if pair['origin'] == OLD:
                return self.old.read(path.as_posix())
        return current.read('/'.join(suffix))

    def verify_all(self):
        old_count = self.old.verify_all()
        task_members, new_count = 0, 0
        accepted = {OLD: 0, NEW: 0}
        receipts = []
        for group, index in self.tasks:
            tar, p = self.load_task(group, index)
            task_members += tar.verify_all()
            new_count += sum(r['origin'] == NEW for r in p['paths'])
            for kind in accepted:
                accepted[kind] += p['accepted_transitions'][kind]
            receipts.append(dict(group=group, index=index, archive_sha256=p['archive_sha256'],
                                 archive_bytes=p['archive_bytes'], journal_sha256=file_sha(tar.path.with_suffix('.jsonl'))))
        assert new_count == 280 and accepted == {OLD: 9476201216, NEW: 184168537344}
        return dict(status='ALL_LOGICAL_RAW_ARCHIVE_MEMBERS_VERIFIED', old_members=old_count, new_task_members=task_members,
                    reused_paired_paths=296, new_paired_paths=new_count, task_receipts=receipts, accepted_transitions=accepted)

    def close(self):
        self.old.close()
        if self.current:
            self.current.close()


class NumpyReadProxy:
    """Redirect only NumPy's load of a RawPath; delegate all numerical methods."""
    def __init__(self, np):
        self.np = np

    def __getattr__(self, name):
        return getattr(self.np, name)

    def load(self, source, *args, **kwargs):
        if isinstance(source, RawPath):
            source = io.BytesIO(source.read_bytes())
        return self.np.load(source, *args, **kwargs)
