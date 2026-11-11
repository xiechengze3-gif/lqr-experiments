"""Append a completed array's saved count/source proof; no full-study completion claim."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group-index', type=int, required=True)
    parser.add_argument('--expected-review-sha256', required=True)
    args = parser.parse_args()
    assert 0 <= args.group_index < 12
    task = CHANNEL/'CLAUDE_TASK.md'
    assert hashlib.sha256(task.read_bytes()).hexdigest() == args.expected_review_sha256
    tag = f'g{args.group_index:02d}'
    audit_path = HERE/f'array-{tag}-count-source-audit-v1.json'
    audit = json.loads(audit_path.read_text())
    assert audit['status'] == 'COMPLETE_ARRAY_COUNTS_SOURCES_RECEIPTS'
    assert audit['bundles'] == 32 and audit['group_index'] == args.group_index
    progress = json.loads(sorted(HERE.glob('formal-progress-*.json'))[-1].read_text())
    assert progress['groups'][args.group_index]['states'] == dict(COMPLETED=32)
    heading = '## X9 FORMAL progress '+tag
    reply = CHANNEL/'CODEX_REPLY.md'
    prior = reply.read_bytes()
    assert heading.encode() not in prior
    section = f'''

{heading}

Array{audit['job']}, `{audit['group']}`:32/32 allocations COMPLETED;32 bundle receipts and{audit['paired_paths']} paired paths /{audit['arm_paths']} arm paths verified for registered model ids/seeds, all algorithm/rung entries, alpha, frozen source hashes, DONE SHA256s, record counts and exact primitive-transition parity. No new simulation. Proof `experiments/x9-20261106/{audit_path.name}`, SHA256 `{hashlib.sha256(audit_path.read_bytes()).hexdigest()}`. Scientific failures, if any, remain in the raw full-denominator records for REPORT.

At {progress['checked_utc']}, formal Slurm elapsed {progress['formal_Slurm_elapsed_SU']:.9f} SU, plus completed pilot0.435 SU; AMS is a separate overlapping view, not added. Cumulative requested47.9333333SU with2SU REPORTreserve gives49.9333333/50SU. Remaining arrays follow the accepted afterok chain,global<=8,no retry. Whole FORMAL and REPORT remain pending. Review SHA256 `{args.expected_review_sha256}` reread before this append.

STATUS: FORMAL RUNNING X9
'''.encode()
    assert hashlib.sha256(task.read_bytes()).hexdigest() == args.expected_review_sha256
    assert reply.read_bytes() == prior
    with reply.open('ab') as stream:
        stream.write(section)
    assert reply.read_bytes() == prior+section
    receipt_path = HERE/f'{tag.upper()}_PROGRESS_APPEND_RECEIPT_v1.json'
    with receipt_path.open('x') as stream:
        json.dump(dict(prior_bytes=len(prior), appended_bytes=len(section), prior_preserved=True,
                       review_sha256=args.expected_review_sha256, group=audit['group']), stream, indent=2)
    print(json.dumps(dict(status='ARRAY_PROGRESS_APPENDED', group=audit['group'])))


if __name__ == '__main__':
    main()
