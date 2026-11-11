"""Append a verified array completion, without claiming the whole formal is done."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED = '97173f645c72d54497aa5594e7d31bb4e32a26935b81e0adada4b9897b1b474e'
assert hashlib.sha256((CHANNEL/'CLAUDE_TASK.md').read_bytes()).hexdigest() == EXPECTED
audit_path = HERE/'g00-count-source-audit-v1.json'
audit = json.loads(audit_path.read_text())
assert audit['status'] == 'COMPLETE_ARRAY_COUNTS_SOURCES_RECEIPTS'
assert audit['bundles'] == 32 and audit['paired_paths'] == 192
progress = json.loads(sorted(HERE.glob('formal-progress-*.json'))[-1].read_text())
assert progress['groups'][0]['states'] == dict(COMPLETED=32)
heading = '## X9 FORMAL progress g00'
reply = CHANNEL/'CODEX_REPLY.md'
prior = reply.read_bytes()
assert heading.encode() not in prior
section = f'''

{heading}

First array20413861, `a0.05-n24-low-three`:32/32 allocations COMPLETED;32 bundle receipts and192 paired paths /384 arm paths verified for model ids/seeds, all6 algorithm/rung entries, frozen source hashes, per-path DONE SHA256s, record counts and exact primitive-transition parity. No hard-failure receipt. Resource/count audit `experiments/x9-20261106/g00-count-source-audit-v1.json`, SHA256 `{hashlib.sha256(audit_path.read_bytes()).hexdigest()}`. This is metadata verification,0 new simulations/diagnostics. Scientific failures, if any, remain in raw records and will be reported failure-inclusively.

At {progress['checked_utc']}, formal completed/running Slurm elapsed {progress['formal_Slurm_elapsed_SU']:.9f} SU, plus completed pilot0.435 SU (overlapping AMS view is not added). Requested47.9333333SU total with2SU REPORTreserve=>49.9333333/50. Remaining11 arrays follow the accepted afterok chain, global<=8, no retry. Whole FORMAL and REPORT are still pending. X10b resource notice has been posted separately; no X10 job submitted.

STATUS: FORMAL RUNNING X9
'''.encode()
assert hashlib.sha256((CHANNEL/'CLAUDE_TASK.md').read_bytes()).hexdigest() == EXPECTED
assert reply.read_bytes() == prior
with reply.open('ab') as stream:
    stream.write(section)
assert reply.read_bytes() == prior+section
with (HERE/'G00_PROGRESS_APPEND_RECEIPT_v1.json').open('x') as stream:
    json.dump(dict(prior_bytes=len(prior), appended_bytes=len(section), prior_preserved=True,
                   review_sha256=EXPECTED), stream, indent=2)
print('G00_PROGRESS_APPENDED')
