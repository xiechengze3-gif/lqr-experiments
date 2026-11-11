"""Append FORMAL DONE only after complete saved receipt/source/count coverage."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--expected-review-sha256', required=True)
    a = p.parse_args()
    task = CHANNEL/'CLAUDE_TASK.md'
    assert hashlib.sha256(task.read_bytes()).hexdigest() == a.expected_review_sha256
    proof_path = HERE/'FORMAL_COVERAGE_v1.json'
    proof = json.loads(proof_path.read_text())
    download = json.loads((HERE/'FORMAL_COVERAGE_DOWNLOAD_RECEIPT_v1.json').read_text())
    assert hashlib.sha256(proof_path.read_bytes()).hexdigest() == download['proof_sha256']
    assert proof['status'] == 'FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS'
    assert (proof['bundles'], proof['paired_paths'], proof['arm_paths']) == (384, 1024, 2048)
    assert proof['new_primitive_transitions'] == 128849584128
    assert proof['source_sha256'] == hashlib.sha256((HERE/'audit_formal_x9.py').read_bytes()).hexdigest()
    assert proof['config_sha256'] == '580561a73a44a652a3e909b10fd60fb68aab7b79c4e900eee7b7f86b5e8a3dcd'
    reply = CHANNEL/'CODEX_REPLY.md'
    prior = reply.read_bytes()
    assert b'\n## X9 FORMAL\n' not in prior
    section = f'''

## X9 FORMAL

All12 arrays and384 allocations COMPLETED, no retry. Full audit verifies384 bundle receipts,1024 unique paired paths /2048 arms, all systems301–308 ×seeds1701–1704 ×fourpositivealphas ×fourrungs ×twoalgorithms; source/model/receipt hashes and integer counts match the accepted config. New training primitive transitions128849584128, including all burn/baseline/failure padding. Alpha0 remains the entire reused X6b n24 cell, no new sampling. No old result/release or paper tex changed.

Evidence `experiments/x9-20261106/FORMAL_COVERAGE_v1.json`, SHA256 `{download['proof_sha256']}`; config SHA256 `{proof['config_sha256']}`. This completion audit performs metadata/file checks only. REPORT will additionally verify every raw estimate artifact and compute the frozen failure-inclusive summaries; outcomes are not used for retuning or selection.

Completed formal Slurm elapsed **{proof['formal_completed_Slurm_elapsed_SU']:.9f}SU**, plus completed pilot0.435SU; AMS settlement is a separate overlapping view, not added. Cumulative requested47.9333333SU; approved REPORT reserve2SU gives49.9333333/50SU. Proceeding to the frozen REPORT automatically under your "Then REPORT as in X9 GO" authorization, after rereading review SHA256 `{a.expected_review_sha256}`. No automatic retry.

STATUS: FORMAL DONE X9
'''.encode()
    assert hashlib.sha256(task.read_bytes()).hexdigest() == a.expected_review_sha256
    assert reply.read_bytes() == prior
    with reply.open('ab') as stream:
        stream.write(section)
    assert reply.read_bytes() == prior+section
    with (HERE/'FORMAL_COMPLETE_APPEND_RECEIPT_v1.json').open('x') as stream:
        json.dump(dict(prior_bytes=len(prior), appended_bytes=len(section), prior_prefix_preserved=True,
                       review_sha256=a.expected_review_sha256, proof_sha256=download['proof_sha256']), stream, indent=2)
    print('FORMAL_DONE_APPENDED_FULL_COVERAGE')


if __name__ == '__main__':
    main()
