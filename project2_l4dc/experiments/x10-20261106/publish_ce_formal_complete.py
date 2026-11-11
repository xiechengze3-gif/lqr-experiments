"""Hash/count/coverage audit and append-only X10a formal completion."""
import argparse
import datetime
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--expected-review-sha256', required=True)
    args = p.parse_args()
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert hashlib.sha256(review).hexdigest() == args.expected_review_sha256
    append_receipt = HERE/'CE_FORMAL_DONE_APPEND_RECEIPT_v1.json'
    assert not append_receipt.exists() and not (HERE/'CE_FORMAL_COVERAGE_v1.json').exists()
    config_path = HERE/'ce-config-protocol-v2.json'
    config = json.loads(config_path.read_text())
    for name, digest in config['sources'].items():
        assert sha(HERE/name) == digest, name
    formal = HERE/'ce-formal-v2'
    whole_path = formal/'FORMAL_DONE.json'
    whole = json.loads(whole_path.read_text())
    assert whole['status'] == 'COMPLETE_FORMAL_NEW_CONFIGURATIONS_ONLY'
    assert whole['config_sha256'] == sha(config_path)
    assert whole['source_sha256'] == sha(HERE/'ce-src-v2/ce_driver.py')
    assert whole['Grace_SU'] == 0 and whole['Slurm_job_id'] is None
    expected = {}
    for case in config['x8_cases']:
        for system in range(8):
            for seed in range(4):
                expected[f'x8/{case["config"]}/s{system}-t{seed}'] = ('x8', system, seed, 262656, 480)
    for n in config['dimension_n']:
        prefixes = config['dimension_N_large'] if n >= 60 else config['dimension_N']
        for system in range(301,309):
            for seed in range(1601,1605):
                expected[f'dimension/n{n}/s{system}-t{seed}'] = ('dimension', system, seed, max(prefixes)+512, 2*len(prefixes))
    for extra in config['redundant_inputs']:
        for system in range(101,109):
            for seed in range(1001,1005):
                expected[f'redundancy/m{extra+2}/s{system}-t{seed}'] = ('redundancy', system, seed, 8704, 4)
    assert len(expected) == len(whole['paths']) == 672
    assert len({r['path'] for r in whole['paths']}) == 672
    counts, records, physical, artifacts = Counter(), Counter(), 0, 0
    provenance, models = set(), []
    for ref in whole['paths']:
        relative = Path(ref['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        key = relative.as_posix()
        part, system, seed, transitions, rowcount = expected.pop(key)
        folder = formal/relative
        path = folder/'DONE.json'
        assert sha(path) == ref['done_sha256']
        item = json.loads(path.read_text())
        assert item['status'] == 'COMPLETE'
        assert item['spec']['system'] == system and item['spec']['seed'] == seed
        assert item['primitive_transitions'] == ref['physical_transitions'] == transitions
        assert len(item['records']) == rowcount
        assert item['execution'] == 'LOCAL_AUTHOR_APPROVED_X10a' and item['Slurm_job_id'] is None
        assert item['host'] and item['process'] > 0
        provenance.add((item['host'], item['process']))
        if part == 'x8':
            assert item['wrapper_sha256'] == whole['source_sha256']
            assert item['original_source_sha256'] == sha(HERE/'ce-src-v2/x8_original.py')
        else:
            assert item['source_sha256'] == whole['source_sha256']
            assert item['engine_sha256'] == sha(HERE/'ce-src-v2/frozen_engine.py')
            for artifact in item['artifacts']:
                assert Path(artifact['path']).name == artifact['path']
                assert sha(folder/artifact['path']) == artifact['sha256']
                prefix = json.loads((folder/f'prefix-{artifact["N"]}.json').read_text())
                assert prefix['status'] == 'COMPLETE_PREFIX'
                assert prefix['fit_sha256'] == artifact['sha256']
                assert prefix['primitive_transitions'] == artifact['N']+512
                artifacts += 1
        models.append(dict(path=(relative/'model.npz').as_posix(), sha256=sha(folder/'model.npz')))
        counts[part] += 1
        records[part] += rowcount
        physical += transitions
    assert not expected
    assert dict(counts) == dict(x8=256,dimension=224,redundancy=192)
    assert dict(records) == dict(x8=122880,dimension=2432,redundancy=768)
    assert physical == whole['physical_transitions'] == 236797952
    assert len(provenance) == 1, 'Expected one local formal process.'
    proof = dict(status='PASS_LOCAL_FORMAL_COVERAGE_SOURCES_COUNTS_ARTIFACTS',
                 checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 paths=672, paths_by_part=counts, output_records_by_part=records,
                 primitive_transitions=physical, fit_artifacts_verified=artifacts,
                 models=models, local_process_provenance=list(provenance),
                 config_sha256=sha(config_path), formal_done_sha256=sha(whole_path),
                 Grace_requested_SU=0, Grace_elapsed_SU=0, Slurm_job_id=None,
                 validation_only_no_new_training=True, failed_pilot_v1_preserved=True)
    prior = (CHANNEL/'CODEX_REPLY.md').read_bytes()
    assert b'## X10a FORMAL\n' not in prior
    section = f'''

## X10a FORMAL

All registered new configurations completed locally: 672 physical CE paths (256 X8, 224 family S dimensions, 192 X1 redundancies), 236797952 primitive transitions including burn-in, one worker/thread. Output records 122880 / 2432 / 768 respectively. Whole-stage source/config/DONE/count coverage, every stored CE fit/gain artifact and model hash PASS. True local host/PID provenance retained; Grace requested/elapsed 0/0 SU, no Slurm id. All outcomes, instability and failed pilot-v1 partial files retained; no old configuration rerun or paper edit.

Proof `experiments/x10-20261106/CE_FORMAL_COVERAGE_v1.json`; whole receipt `ce-formal-v2/FORMAL_DONE.json` SHA256 `{proof['formal_done_sha256']}`. Config SHA256 `{proof['config_sha256']}`. Proceeding to saved-record REPORT under X10 GO after a fresh review read, with the frozen analysis and old CSV bytes preserved.

STATUS: FORMAL DONE X10a
'''.encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes() == review
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior
    with (HERE/'CE_FORMAL_COVERAGE_v1.json').open('x') as stream:
        json.dump(proof,stream,indent=2)
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:
        stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior+section
    with append_receipt.open('x') as stream:
        json.dump(dict(prior_bytes=len(prior), appended_bytes=len(section), prior_preserved=True,
                       review_sha256=args.expected_review_sha256),stream,indent=2)
    print(json.dumps({k:v for k,v in proof.items() if k != 'models'}))


if __name__ == '__main__':
    main()
