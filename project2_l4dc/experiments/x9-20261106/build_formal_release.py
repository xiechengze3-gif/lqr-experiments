"""Build only after the live X9 PILOT ACCEPTED; never submits."""
import argparse
import ast
import hashlib
import io
import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
NAME = 'x9-20261106-formal-v1'


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--expected-review-sha256', required=True)
    p.add_argument('--exact-accepted-quote', required=True)
    a = p.parse_args()
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review) == a.expected_review_sha256
    quote = a.exact_accepted_quote
    assert all(word in quote for word in ['X9', 'PILOT', 'ACCEPTED'])
    assert quote in review.decode('utf-8-sig')
    config_payload = (HERE/'prepared-formal-v1/formal-config.json').read_bytes()
    config = json.loads(config_payload)
    plan_payload = (HERE/'prepared-formal-v1/formal-plan.json').read_bytes()
    plan = json.loads(plan_payload)
    assert plan['formal_config_sha256'] == sha(config_payload)
    assert plan['cumulative_requested_upper_SU'] <= 50 and plan['memory_headroom_fraction'] >= .2
    files = {}
    for line in (HERE/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        payload = (HERE/name).read_bytes()
        assert sha(payload) == digest
        if name not in ['approval.json', 'run.sbatch']:
            files[name] = payload
    for name in ['submit_formal_x9.py', 'build_formal_release.py']:
        ast.parse((HERE/name).read_text(encoding='utf-8'))
        files[name] = (HERE/name).read_bytes()
    files.update({'formal-config.json': config_payload, 'formal-plan.json': plan_payload,
                  'CLAUDE_TASK_FORMAL_accepted.md': review,
                  'PROTOCOL_SHA256SUMS': (HERE/'SHA256SUMS').read_bytes(),
                  'PILOT_MANIFEST_v1.json': (HERE/'PILOT_MANIFEST_v1.json').read_bytes(),
                  'PILOT_REPORT_v1.md': (HERE/'PILOT_REPORT_v1.md').read_bytes()})
    approval = dict(experiment='X9', accepted_stage='PILOT', exact_accepted_quote=quote,
                    review_sha256=sha(review), formal_config_sha256=sha(config_payload),
                    pilot_manifest_sha256=sha(files['PILOT_MANIFEST_v1.json']))
    files['formal-approval.json'] = (json.dumps(approval, indent=2)+'\n').encode()
    shell = (HERE/'run.sbatch').read_text()
    assert shell.count('release=$base/releases/x9-20261106-resource-v1') == 1
    shell = shell.replace('release=$base/releases/x9-20261106-resource-v1', 'release=$base/releases/'+NAME)
    old_call = 'x9_core.py resource --config config-protocol-v1.json --index "$SLURM_ARRAY_TASK_ID"'
    assert shell.count(old_call) == 1
    for index, group in enumerate(plan['groups']):
        assert group['wall_guard_pass'] and group['id'] == config['formal_groups'][index]['id']
        call = 'x9_core.py formal --config formal-config.json --group '+group['id']+' --index "$SLURM_ARRAY_TASK_ID"'
        files[f'formal-g{index:02d}.sbatch'] = shell.replace(old_call, call).encode()
    hashes = {name: sha(payload) for name, payload in files.items()}
    files['SHA256SUMS'] = ''.join(f'{digest}  {name}\n' for name, digest in hashes.items()).encode()
    target = HERE/'packages'/(NAME+'.tar.gz')
    assert not target.exists()
    assert sha((CHANNEL/'CLAUDE_TASK.md').read_bytes()) == a.expected_review_sha256
    with tarfile.open(target, 'x:gz') as tf:
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    manifest = dict(status='FORMAL_RELEASE_BUILT_NOT_SUBMITTED', name=NAME,
                    archive=str(target), archive_sha256=sha(target.read_bytes()),
                    approval=approval, files=hashes, manifest_sha256=sha(files['SHA256SUMS']))
    with target.with_suffix('.manifest.json').open('x') as stream:
        json.dump(manifest, stream, indent=2)
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}))


if __name__ == '__main__':
    main()
