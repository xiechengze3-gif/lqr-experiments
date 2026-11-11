"""Freeze the ruling and byte-checked numerical inputs before X14 compute."""
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPERIMENTS = ROOT.parent
X9 = EXPERIMENTS / 'x9-20261106'
X10 = EXPERIMENTS / 'x10-20261106'
X9_CONFIG_SHA = 'ff3f89cbae75e35c3f079e30d69f7bd1b4af63bf661528d65247563ee05c0196'
X9_SOURCES = {
    'frozen_engine.py': '9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989',
    'estimation.py': 'f587bd48993288dbf9160dd4cc1e62542f15ee5794bda37590ec48dc672c9c59',
    'actor_paths.py': '905ebe819c50c860249dc11836eb9f356b97b6ea8d4ebe22e34d5a0e4f7deb3b',
    'x9_core.py': 'e62b82f5617179791e362189ab5900b3c29dbf7ad2d2785813376fc02884c050',
    'analyze_x9.py': '7eafc31a73ab8e3f8924561d4892682e8bf73f57b06b5c321018494792a773bd',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    with path.open('xb') as f:
        f.write(data)


def main():
    raw = (EXPERIMENTS.parent / 'CLAUDE_TASK.md').read_bytes()
    marker = b'## X14 GO: fill-in experiments, new ruling (08:28Z 11/08)'
    assert raw.count(marker) == 1
    start = raw.index(marker)
    next_section = re.search(rb'\n## [^#]', raw[start + len(marker):])
    end = start + len(marker) + next_section.start() + 1 if next_section else len(raw)
    ruling = raw[start:end]
    assert b'alpha = 0.02' in ruling and b'### Deliverables' in ruling

    source = X9 / 'config-protocol-v1.json'
    base = source.read_bytes()
    assert digest(base) == X9_CONFIG_SHA
    config = json.loads(base)
    assert config['scientific_sources'] == X9_SOURCES
    assert config['pilot_systems'] == [9601, 9602]
    assert all(digest((X9 / n).read_bytes()) == h for n, h in X9_SOURCES.items())
    assert all(digest((X9 / n).read_bytes()) == h for n, h in config['baseline_sources'].items())
    for item in config['baseline_models'].values():
        assert digest((X9 / item['path']).read_bytes()) == item['sha256']

    extra_path = X10 / 'prepared-actor-formal-v1/formal-config.json'
    extra_config = extra_path.read_bytes()
    extra = {r['rung']: r for r in json.loads(extra_config)['all_schedules'] if r['n'] == 24}
    original = {r['rung']: r for r in config['all_schedules']}
    assert set(original) == {2.0**-i for i in (0, 2, 4, 6)}
    assert set(extra) == {2.0**-i for i in (1, 3, 5, 7, 8)}
    schedules = sorted([*original.values(), *extra.values()], key=lambda row: row['rung'])
    for row in schedules:
        for algo, stages in [('NPG', 16), ('PI', 8)]:
            values = row['batches'][algo]
            assert len(values) == stages
            assert 16 * (sum(values) + 17 * stages) == row['primitive_per_arm_per_algorithm']
    a = dict(config, alphas=[0.02], new_alphas=[0.02], rungs=sorted(original.keys() | extra.keys()),
             all_schedules=schedules)
    b = dict(config, rungs=sorted(extra), all_schedules=sorted(extra.values(), key=lambda row: row['rung']))
    encoded = {f'config-{tag}-v1.json': (json.dumps(obj, indent=2) + '\n').encode()
               for tag, obj in [('x14a', a), ('x14b', b)]}
    io = EXPERIMENTS / 'x12-20261106/virtual_task_store_v2.py'
    hashes = {'X14 ruling section': digest(ruling), 'CLAUDE_TASK.md snapshot': digest(raw),
              'X9 config-protocol-v1.json': X9_CONFIG_SHA, 'X10b schedule source': digest(extra_config),
              **X9_SOURCES, 'X12 virtual_task_store_v2.py': digest(io.read_bytes()),
              **{n: digest(data) for n, data in encoded.items()}}
    appendix = ['\n\n## Frozen input hashes (SHA-256)\n\n',
                *(f'- `{n}` `{h}`\n' for n, h in hashes.items()),
                '\nThe X14a/b JSON files inherit X9 numerical settings and replace the active alpha and/or rung lists. '
                'X9 scientific source files stay byte-identical. Job metadata and archive I/O are handled outside them.\n']
    assert (EXPERIMENTS.parent / 'CLAUDE_TASK.md').read_bytes() == raw
    write(ROOT / 'PROTOCOL_v1.md', ruling + ''.join(appendix).encode())
    for n, data in encoded.items():
        write(ROOT / n, data)
    print(json.dumps(hashes, indent=2))


if __name__ == '__main__':
    main()
