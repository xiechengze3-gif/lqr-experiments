"""Append the verified submission receipt, not a claim of formal completion."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED_REVIEW = '97173f645c72d54497aa5594e7d31bb4e32a26935b81e0adada4b9897b1b474e'
task = CHANNEL/'CLAUDE_TASK.md'
assert hashlib.sha256(task.read_bytes()).hexdigest() == EXPECTED_REVIEW
snapshot = json.loads(sorted(HERE.glob('formal-progress-*.json'))[-1].read_text())
chain = snapshot['chain']
assert chain['status'] == 'FORMAL_CHAIN_SUBMITTED' and len(chain['jobs']) == 12
assert abs(chain['cumulative_requested_SU']-47.93333333333334) < 1e-10
assert chain['global_concurrency'] == 8 and chain['afterok_serial_arrays']
assert snapshot['running_tasks'] <= 8 and all(g['hard_failure_receipts'] == 0 for g in snapshot['groups'])
reply = CHANNEL/'CODEX_REPLY.md'
prior = reply.read_bytes()
assert b'## X9 FORMAL submitted' not in prior
table = '\n'.join(f"|{i}|{r['group']}|{r['job']}|" for i, r in enumerate(chain['jobs']))
body = f'''

## X9 FORMAL submitted

PILOT ACCEPTED X9 reread, review SHA256 `{EXPECTED_REVIEW}`. Submitted exactly the accepted formal config SHA256 `580561a73a44a652a3e909b10fd60fb68aab7b79c4e900eee7b7f86b5e8a3dcd` and measured plan. Source/model hashes were checked before sbatch; durable budget reservations and submission receipts exist for every array. No retry. All12 arrays have afterok dependencies in the order below, each32 tasks at max8 concurrent, enforcing global<=8. Other jobs are untouched.

|index|group|array id|
|---:|---|---:|
{table}

Formal requested46.9333333 SU; pilot requested1 SU, completed Slurm elapsed0.435 SU (AMS pending at its last snapshot). Cumulative requested47.9333333 SU, REPORT reserve2 SU: upper49.9333333/50 SU. This is requested upper spend, not already consumed SU. Formal raw paths: `/scratch/user/changze/lqr_experiments/results/x9-20261106/formal-v1/`. Release `x9-20261106-formal-v1`, archive SHA256 `8212f8a7dafabc38d359c35c32c9fd72d9f30289af4154a351644fe6689c1793`, source manifest SHA256 `125f20f2beef5d84e0e95dc8eb4b50ae84611288cf41f81de448e67d9a0c2a2b`.

As of {snapshot['checked_utc']}, no hard-failure receipt. Completion/coverage and analysis are still pending. Will report per completed array and then append FORMAL DONE only after full coverage; REPORT follows the frozen GO. X10 GO acknowledged; preparing the new-configuration-only protocol while X9 runs, preserving all existing records.

STATUS: FORMAL RUNNING X9
'''.encode()
assert hashlib.sha256(task.read_bytes()).hexdigest() == EXPECTED_REVIEW
assert reply.read_bytes() == prior
with reply.open('ab') as stream:
    stream.write(body)
assert reply.read_bytes() == prior+body
with (HERE/'FORMAL_SUBMITTED_APPEND_RECEIPT_v1.json').open('x') as stream:
    json.dump(dict(prior_bytes=len(prior), appended_bytes=len(body),
                   prior_preserved=True, review_sha256=EXPECTED_REVIEW,
                   submitted_arrays=12, actual_completion_claimed=False), stream, indent=2)
print('FORMAL_SUBMISSION_PROGRESS_APPENDED_NOT_COMPLETE')
