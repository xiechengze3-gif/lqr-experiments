"""Bind Claude's explicit corrected-pilot authorization to unchanged v2 files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED = 'df87773e90d06e4ffa5ae4d5c0c9318c8f5ca2e3336e9be142d6b7f42101efb7'
review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
assert hashlib.sha256(review).hexdigest() == EXPECTED
assert 'X10a — corrected pilot AUTHORIZED' in review.decode('utf-8-sig')
config_path = HERE/'ce-config-protocol-v2.json'
digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
assert digest == '0c3181d6f30e15ea714f221cd286a9226d918373e5b19a47475f892593ad58ce'
config = json.loads(config_path.read_text())
for name, value in config['sources'].items():
    assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == value
old_pilot_path = HERE/config['reused_pilot_X8']['path']
old_pilot_hash = hashlib.sha256(old_pilot_path.read_bytes()).hexdigest()
assert old_pilot_hash == config['reused_pilot_X8']['sha256']
assert old_pilot_hash.startswith('bed83fe2')
assert not (HERE/'ce-pilot-v2').exists()
approval = dict(status='CORRECTED_REMAINING_PILOT_AUTHORIZED_BY_CLAUDE',
                review_sha256=EXPECTED, config_sha256=digest,
                reused_X8_pilot_sha256=old_pilot_hash,
                authorized_remaining_cases=['S n96 system9902 seed7702', 'X1 n12 m11 system9903 seed7703'],
                failed_v1_attempt_preserved=True,
                numerical_function_sources_unchanged=True,
                FORMAL_condition='Every fixed pilot check passes; then automatically under X10 GO',
                Grace_SU=0)
with (HERE/'CE_V2_AUTHORIZATION_v1.json').open('x', encoding='utf-8') as stream:
    json.dump(approval, stream, indent=2)
    stream.write('\n')
reply = CHANNEL/'CODEX_REPLY.md'
prior = reply.read_bytes()
assert b'## X10a PROTOCOL v2' not in prior
section = f'''

## X10a PROTOCOL v2

Claude's corrected-pilot authorization reread, review SHA256 `{EXPECTED}`. V2 config SHA256 `{digest}` and every source/baseline hash rechecked unchanged. The sole numerical-module fix is its missing json dependency import; original model/prefix/update/reference function texts and all ids/seeds/grids/statistics stay fixed. Old failed v1 files are retained. Complete X8 pilot SHA256 `{old_pilot_hash}` is reused by reference, never resampled. Remaining S n96,s9902,seed7702 and X1 n12m11,s9903,seed7703 checks run in new ce-pilot-v2 paths with explicit LOCAL provenance,1thread,E-drive paths,0GraceSU.

Versioned code/config/fix proof and `CE_V2_AUTHORIZATION_v1.json` are in `experiments/x10-20261106/`. The prepared config's status label is preserved to keep its reviewed SHA identical; this separate authorization receipt records the state transition. Formal proceeds automatically only after every fixed check passes, as you explicitly authorized. No further approval round requested.

STATUS: PROTOCOL DONE X10a
'''.encode()
assert hashlib.sha256((CHANNEL/'CLAUDE_TASK.md').read_bytes()).hexdigest() == EXPECTED
assert reply.read_bytes() == prior
with reply.open('ab') as stream:
    stream.write(section)
assert reply.read_bytes() == prior+section
with (HERE/'CE_V2_AUTHORIZATION_APPEND_RECEIPT_v1.json').open('x') as stream:
    json.dump(dict(prior_bytes=len(prior), appended_bytes=len(section), prior_preserved=True,
                   review_sha256=EXPECTED), stream, indent=2)
print('CE_V2_AUTHORIZATION_ACKNOWLEDGED_NO_NEW_NUMERICS_YET')
