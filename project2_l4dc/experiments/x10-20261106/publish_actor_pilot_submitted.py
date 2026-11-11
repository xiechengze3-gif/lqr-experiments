"""Append confirmed bounded-pilot receipts; do not call the pilot complete."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED = 'df87773e90d06e4ffa5ae4d5c0c9318c8f5ca2e3336e9be142d6b7f42101efb7'
task = CHANNEL/'CLAUDE_TASK.md'
assert hashlib.sha256(task.read_bytes()).hexdigest() == EXPECTED
data = json.loads(sorted(HERE.glob('actor-pilot-progress-*.json'))[-1].read_text())
chain = data['chain']
assert chain['status'] == 'BOUNDED_PILOT_CHAIN_SUBMITTED'
assert [r['job'] for r in chain['jobs']] == ['20415057', '20415058', '20415059']
assert abs(chain['requested_upper_SU']-(4+1/6)) < 1e-9
assert not data['hard_failures'] and chain['formal_submitted'] is False
reply = CHANNEL/'CODEX_REPLY.md'
prior = reply.read_bytes()
assert b'## X10b PILOT submitted' not in prior
body = f'''

## X10b PILOT submitted

Submitted exactly the explicitly authorized bounded pilot. Equivalence replay20415057 dependsafterokX9lastformalarray20413893; NPGtiming20415058 andPItiming20415059 both dependafterokequivalence20415057. OneCPU2GiBperjob,10/120/120min; requestedupper4.166667SU under the separateX10brequestedcap200 andactualforecastcap160. These are pending allocations, not consumedSU. Noformaljobsubmitted. No automaticretry. ExistingX9/otherjobs untouched.

Frozen configSHA256 `7fdd2832b1122b309974c2b24dbebf5f6812df33892ddec1fcc24450271544fe`; sourceSHA256SUMS `f1269848cb7052134dc153ae84abde01e09208099e64c9bbde4803ddfc45f0e5`; packageSHA256 `35223147c4945786a01a315b2fc82ece65ce8dfe66477f369ce2f5545e122d5b`, verified after upload/deployment. Submission receipts/ledger are durable under`results/x10-20261106/X10b/`. Actual source/array/RNG bitwise check and measured timing/RSS remain pending. No accuracy/stability-basedselection. Upon everyfixedcheckPASS, measuredactualforecast<=160 andrequestedupper<=200 withdeadlinefeasible, postresolvedplanandproceedautomaticallyin n72,n48,n36,n24 order. KeepglobalGrace<=8.

ReviewSHA `{EXPECTED}` reread; firstmonitor{data['checked_utc']}. X10a localformalrunsindependentlyat1thread,0GraceSU;X9continuesitsaccepted50SUchain. This is submission progress, not PILOTDONE.

STATUS: PILOT QUEUED X10b
'''.encode()
assert hashlib.sha256(task.read_bytes()).hexdigest() == EXPECTED
assert reply.read_bytes() == prior
with reply.open('ab') as stream:
    stream.write(body)
assert reply.read_bytes() == prior+body
with (HERE/'ACTOR_PILOT_SUBMITTED_APPEND_RECEIPT_v1.json').open('x') as stream:
    json.dump(dict(prior_bytes=len(prior), appended_bytes=len(body), prior_preserved=True,
                   review_sha256=EXPECTED), stream, indent=2)
print('BOUNDED_ACTOR_PILOT_QUEUED_PROGRESS_APPENDED')
