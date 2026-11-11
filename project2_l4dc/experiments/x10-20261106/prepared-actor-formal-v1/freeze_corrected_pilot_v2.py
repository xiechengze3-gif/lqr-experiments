"""Freeze the explicitly authorized input-only correction; no submit/simulate."""
import ast
import datetime
import hashlib
import io
import json
import tarfile
from pathlib import Path

CONTROL = Path(__file__).resolve().parent
HERE = CONTROL.parent
CHANNEL = HERE.parents[1]
SOURCE = HERE/'actor-draft-v2'
EXPECTED_REVIEW = '2c35aad9dbee1abc9d1724991885850fde943062215914b1e49c02669cccd8ed'
QUOTE = '## X10b corrected pilot AUTHORIZED (06:10 CDT 11/06)'
NAME = 'x10-20261106-b-pilot-v2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(data):
    return (json.dumps(data, indent=2)+'\n').encode()


def new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def main():
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review) == EXPECTED_REVIEW and QUOTE in review.decode('utf-8-sig')
    assert 'AUTHORIZED as proposed in CORRECTION_PROPOSAL_v2' in review.decode('utf-8-sig')
    manifest_path = HERE/'ACTOR_PROTOCOL_MANIFEST_v2.json'
    target = HERE/'actor-pilot-release-v2'
    archive = HERE/'packages'/(NAME+'.tar.gz')
    assert not manifest_path.exists() and not target.exists() and not archive.exists()
    proposal_bytes = (HERE/'actor-pilot-correction-v2/CORRECTION_PROPOSAL_v2.json').read_bytes()
    proposal = json.loads(proposal_bytes)
    old_bytes = (SOURCE/'actor-config-protocol-v1.json').read_bytes()
    cfg = json.loads(old_bytes)
    assert cfg['scientific_sources'] == proposal['original_learning_sources']
    files = {}
    old_sums = dict((name, digest) for digest, name in (line.split('  ',1) for line in (SOURCE/'SHA256SUMS').read_text().splitlines()))
    for name in cfg['scientific_sources']:
        data = (SOURCE/name).read_bytes()
        assert sha(data) == cfg['scientific_sources'][name] == old_sums[name]
        files[name] = data
    for path in (SOURCE/'baseline').rglob('*'):
        if path.is_file():
            name = path.relative_to(SOURCE).as_posix()
            data = path.read_bytes()
            assert sha(data) == old_sums[name]
            files[name] = data
    wrapper = (HERE/'actor-pilot-correction-v2/actor_pilot_v2.py').read_bytes()
    assert sha(wrapper) == proposal['corrected_wrapper_sha256']
    files['actor_pilot_v2.py'] = wrapper
    baseline = HERE/'actor-replay-baseline-v2'
    baseline_manifest = (baseline/'MANIFEST_v2.json').read_bytes()
    assert sha(baseline_manifest) == proposal['reference_baseline_manifest_sha256']
    for name, meta in json.loads(baseline_manifest)['files'].items():
        data = (baseline/name).read_bytes()
        assert sha(data) == meta['sha256'] and len(data) == meta['bytes']
        files['replay-baseline/'+name] = data
    files['replay-baseline/MANIFEST_v2.json'] = baseline_manifest
    for name in ['remote_pilot_v2.py', 'preflight_correction_v2.py', 'freeze_corrected_pilot_v2.py']:
        files[name] = (CONTROL/name).read_bytes()
    files['CORRECTION_PROPOSAL_v2.json'] = proposal_bytes
    files['CLAUDE_TASK_CORRECTION_AUTHORIZED.md'] = review
    cfg.update(version=2, author_review_sha256=EXPECTED_REVIEW,
               original_protocol_config_sha256=sha(old_bytes),
               validation_wrapper_sha256=sha(wrapper),
               reference_baseline_manifest_sha256=sha(baseline_manifest),
               reuse_completed_v1_NPG_done_sha256=proposal['reuse_completed_v1_NPG_done_sha256'],
               correction_proposal_sha256=sha(proposal_bytes),
               prior_failed_pilot_actual_SU=57/3600,
               prior_pilot_requested_upper_SU=4+1/6,
               corrected_pilot_additional_requested_upper_SU=4+1/6,
               pilot_requested_upper_SU=8+1/3,
               resource_proposal_status='AUTHORIZED_CORRECTED_PILOT_V2_NOT_SUBMITTED',
               provisional_actual_forecast_SU=cfg['provisional_actual_forecast_SU']+57/3600,
               provisional_requested_upper_SU=cfg['provisional_requested_upper_SU']+4+1/6,
               additional_formal_gate='Formal and report must not depend on old remote X6b files; merge uses packaged local X6b-report-v1 records; copy all new raw outputs promptly to E.')
    files['actor-config-protocol-v2.json'] = encode(cfg)
    approval = dict(experiment='X10b', stage='PILOT', corrected_pilot_explicitly_authorized=True,
                    review_sha256=EXPECTED_REVIEW, exact_corrected_authorization_quote=QUOTE,
                    config_sha256=sha(files['actor-config-protocol-v2.json']),
                    original_config_sha256=sha(old_bytes), additional_requested_upper_SU=4+1/6,
                    cumulative_pilot_requested_upper_SU=8+1/3, no_NPG_resampling=True)
    files['approval-v2.json'] = encode(approval)
    shell = (SOURCE/'pilot-NPG.sbatch').read_text(encoding='utf-8')
    assert shell.count('releases/x10-20261106-b-pilot-v1') == 1
    shell = shell.replace('releases/x10-20261106-b-pilot-v1', 'releases/'+NAME)
    original = 'actor_pilot.py --config actor-config-protocol-v1.json --role NPG'
    assert shell.count(original) == 1
    for role in ['equivalence', 'NPG', 'PI']:
        files['pilot-'+role+'.sbatch'] = shell.replace(original,
            'actor_pilot_v2.py --config actor-config-protocol-v2.json --role '+role).encode()
    protocol = f'''# X10b authorized input-only correction v2

Authority: {QUOTE}, review SHA256 {EXPECTED_REVIEW}. Only the proposed reference input/output namespace correction is authorized. Scientific sources/models/ids/seeds/all schedules remain exact original bytes/values. Metadata preflight checks all50 original reference files and all32 saved completed NPG arrays BEFORE ANYSBATCH. Compare saved NPG with original np.array_equal/RNG/count checks without rerunning it; run only the uncompleted PI replay; then two original n72/9102/9801 five-rung timings after equivalence PASS. All outputs new resource-v2, old failed/canceled files/history retained.

Three additional 1CPU/2GiB jobs, requested walls10/120/120min: additional4.166666667SU, cumulativepilotrequested8.333333333SU; prior actual57s=.015833333SU remains counted. All bitwise/RSS/wall guard/cap/deadline/global8 gates unchanged. Formal only if every check PASS, measured actual forecast<=160 and requested upper<=200. Before formal, verify no old remote file dependencies in formal/report and package local X6b-report-v1 records for the nine-rung merge. Promptly copy all raw outputs to E. No automatic retry.

Config SHA256 {approval['config_sha256']}; wrapper SHA256 {sha(wrapper)}; baseline manifest SHA256 {sha(baseline_manifest)}; reuse saved NPG DONE SHA256 {cfg['reuse_completed_v1_NPG_done_sha256']}.
'''
    files['PROTOCOL_CORRECTION_v2.md'] = protocol.encode()
    for name, data in files.items():
        if name.endswith('.py'):
            ast.parse(data.decode('utf-8'), filename=name)
    hashes = {name:sha(data) for name,data in files.items()}
    files['SHA256SUMS'] = ''.join(f'{digest}  {name}\n' for name,digest in hashes.items()).encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes() == review
    for name, data in files.items():
        new(target/name, data)
    with tarfile.open(archive, 'x:gz') as tf:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tf.addfile(member, io.BytesIO(data))
    manifest = dict(status='AUTHORIZED_CORRECTED_PILOT_FROZEN_NOT_SUBMITTED',
                    created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    approval=approval, files=hashes, archive=str(archive), archive_sha256=sha(archive.read_bytes()),
                    SHA256SUMS_sha256=sha(files['SHA256SUMS']), new_jobs=0, new_SU=0)
    new(manifest_path, encode(manifest))
    prior = (CHANNEL/'CODEX_REPLY.md').read_bytes()
    section = ('\n\n## X10b PROTOCOL correction v2\n\n'+protocol.split('\n',1)[1].lstrip()
        +'\nExplicit authorization received; frozen new release/package, not yet submitted. Original failed attempt/ledger retained. '
        'Current X9+X10b actual30.507222222SU; CE0GraceSU. Proceeding to authorized metadata preflight then corrected pilot only.\n\n'
        'STATUS: PROTOCOL DONE X10b\n').encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes() == review and (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:
        stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior+section
    new(HERE/'ACTOR_PROTOCOL_APPEND_RECEIPT_v2.json', encode(dict(prior_bytes=len(prior), appended_bytes=len(section),
        prior_preserved=True, review_sha256=EXPECTED_REVIEW, config_sha256=approval['config_sha256'])))
    print(json.dumps({key:value for key,value in manifest.items() if key != 'files'}))


if __name__ == '__main__':
    main()
