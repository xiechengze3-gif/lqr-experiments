"""Append audited FORMAL completion; numerical/report checks remain separate."""
import datetime
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHANNEL=ROOT.parents[2]
REVIEW_SHA='d5747708372e246b7bfd394c9c33ed915f4c7a20e6370aa1718032ba6b605e2e'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    task=CHANNEL/'CLAUDE_TASK.md'
    assert sha(task)==REVIEW_SHA
    config_path=ROOT/'prepared-formal-v1/formal-config.json'
    config=json.loads(config_path.read_text())
    assert all(sha(ROOT/name)==value for name,value in config['scientific_sources'].items())
    proof_path=ROOT/'FORMAL_COMPLETE_v1.json'
    proof=json.loads(proof_path.read_text())
    assert proof['status']=='COMPLETE_COVERAGE_COUNTS_SOURCES'
    assert proof['config_sha256']==sha(config_path)
    assert proof['counts']==dict(tasks=384,paired_paths=1024,raw_stage_artifacts=24576,
        checkpoint_pairs=12288,primitive_transitions=483160776704)
    assert len(proof['jobs'])==12 and len(proof['paired_path_receipts'])==1024
    accounting=json.loads((ROOT/'formal-progress/accounting-20261102T140655.json').read_text())
    assert accounting['cumulative_requested_SU']+6.5<=400
    destination=CHANNEL/'CODEX_REPLY.md'
    heading='## X6b FORMAL — COMPLETE'
    assert heading not in destination.read_text(encoding='utf-8-sig')
    body=f"""

{heading}

Completed coverage/count/source audit at {proof['checked_utc']}; all12 arrays,
384/384 tasks,1024 paired paths/2048 arms,24576 raw stage artifacts and12288
checkpoint pairs are present. Exact training transition total:
483160776704. Paired primitive budgets,including absorbing-failure padding,
match the frozen schedule. No retry,resubmission,cancellation or retuning.

Proof:experiments/x6-20261101/X6b-protocol-v2/FORMAL_COMPLETE_v1.json,
SHA256 {sha(proof_path)}. Config SHA256 {sha(config_path)}; all five accepted
science source hashes unchanged. The frozen v14 validator SHA is
{proof['validator_sha256']}. Audit zero-new-transitions.

Aggregate path failures across all n,rungs and algorithms:
dense {proof['failure_counts']['dense']}/1024; truncated
{proof['failure_counts']['truncated']}/1024. These are combined path counts,
not per-cell rates or Slurm failures; full per-rung reporting follows.

Raw/checkpoint matrix hashes,update equivalence,cost identities and diagnostics
are explicitly PENDING the already conditionally authorized compute-node REPORT.
Formal raw archive is not yet transferred or sealed; no final numerical claim
is based on this coverage receipt.

X6 cumulative requested336.866666667/400SU; REPORT upper6.5SU,projected
343.366666667/400SU. Completed-task Slurm elapsed
{accounting['slurm_elapsed_billing_SU']:.9f}SU; AMS settled
{accounting['ams_settled_walltime_slots_SU']:.9f}SU at
{accounting['checked_utc']} (overlap,never add). Account balance is not study cost.
Latest review reread {datetime.datetime.now(datetime.timezone.utc).isoformat()},
SHA {REVIEW_SHA};00:30 explicitly authorizes frozen REPORT after all arrays.
Proceeding with four diagnostics jobs,then summary,without further approval.
No old result/release or paper TeX edited.

STATUS: FORMAL DONE X6b
"""
    assert sha(task)==REVIEW_SHA
    with destination.open('a',encoding='utf-8',newline='') as stream:stream.write(body)
    print(json.dumps(dict(status='FORMAL_DONE_APPENDED',proof_sha256=sha(proof_path))))

if __name__=='__main__':main()
