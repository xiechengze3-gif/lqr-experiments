"""Disclose a report-only coverage assertion adaptation before new actor outcomes."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CHANNEL=HERE.parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-review-sha256',required=True)
    args=p.parse_args()
    review=(CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert hashlib.sha256(review).hexdigest()==args.expected_review_sha256
    proof=json.loads((HERE/'actor-report-src-v1/COVERAGE_SOURCE_PROOF_v1.json').read_text())
    assert proof['status']=='PASS_COVERAGE_ASSERTION_ONLY' and proof['literal_reversible_replacement']
    assert {'summarize','paired_ratio','q','metrics','processing','endpoint'} <= set(proof['statistics_and_other_functions_byte_identical'])
    checks=json.loads((HERE/'ACTOR_FORMAL_CONTROL_CHECKS_v1.json').read_text())
    assert checks['status']=='PASS_STATIC_AND_SYNTHETIC_CONTROL_GATES'
    receipt=HERE/'ACTOR_REPORT_COVERAGE_APPEND_RECEIPT_v1.json'
    assert not receipt.exists()
    prior=(CHANNEL/'CODEX_REPLY.md').read_bytes()
    title='## X10b PROTOCOL report coverage addendum'
    assert title.encode() not in prior
    section=f'''

{title}

Before any X10b numerical job starts, static report preparation found the original `inspect` coverage assertion hard-coded four rungs. The X10b new-only report has five registered rungs. Preserved the frozen analyzer and created `actor-report-src-v1/analyze_actor_five_rungs.py`; the sole reversible change is the final assertion's two factors `4` -> `len(config['rungs'])`, yielding 640 endpoints and 8320 stage rows per dimension. No estimator, update, truth diagnostic, filtering, quantile, bootstrap, attainment or interpolation calculation changes. All other functions, including the entire `summarize`, are literal source-text identical. No new pilot/formal run or additional SU was needed for this source check.

Original analyzer SHA256 `{proof['original_sha256']}` retained in the protocol; new report-only analyzer SHA256 `{proof['new_sha256']}`. `actor-report-src-v1/COVERAGE_SOURCE_PROOF_v1.json` contains the exact changed line and source identity proof. The upcoming REPORT package will bind both source versions; pilot/formal scientific files and config hashes remain unchanged. Captured the current paper `cross` function verbatim and its original four-rung CSV into a new read-only reference copy; the paper was never imported/executed/edited.

The metadata-only formal control scripts are prepared. AST/global dependency checks and synthetic cap-overshoot, X9-completion, stale-audit and deadline gates PASS (`ACTOR_FORMAL_CONTROL_CHECKS_v1.json`); these are control checks, not experimental results. Formal remains conditional on the authorized pilot's actual bitwise/count/RSS/Slurm checks, actual-spend forecast <=160 SU, requested upper <=200 SU and deadline, with X9 REPORT completed first. No automatic retry, grid cut or retuning.

STATUS: PROTOCOL DONE X10b
'''.encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes()==review and (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior+section
    with receipt.open('x') as stream:json.dump(dict(prior_bytes=len(prior),appended_bytes=len(section),prior_preserved=True,
          review_sha256=args.expected_review_sha256),stream,indent=2)
    print(json.dumps(dict(status='REPORT_COVERAGE_ADAPTATION_DISCLOSED',new_experiments=0,new_SU=0)))


if __name__=='__main__':main()
