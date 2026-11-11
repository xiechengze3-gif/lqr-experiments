"""Append exact own-job settlement reconciliation; no scientific recomputation."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED_REVIEW = 'e7b735146fdfbfb461d702dc61eaefa6cc912366aed41e04408d3b96da5f4c5d'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review) == EXPECTED_REVIEW, 'Review changed; read it before appending.'
    x9_path = HERE.parent/'x9-20261106/accounting-1793962809554039371.json'
    b_path = HERE/'actor-accounting-1793962809555305307.json'
    x9, b = (json.loads(p.read_text()) for p in [x9_path, b_path])
    assert x9['status'] == 'OWN_X9_ACCOUNTING_VERIFIED'
    assert b['status'] == 'OWN_X10B_ACCOUNTING_VERIFIED'
    for entry in [x9, b]:
        assert not entry['unknown_Slurm_billing_jobs'] and not entry['unparsed_own_AMS_rows']
        assert math.isclose(entry['Slurm_elapsed_billing_SU'], entry['AMS_settled_walltime_slots_SU'], abs_tol=1e-10)
    assert x9['Slurm_allocation_rows'] == x9['AMS_own_settled_rows'] == 389
    assert all(row['state'] == 'COMPLETED' for row in x9['allocations'])
    assert b['Slurm_allocation_rows'] == 3 and b['AMS_own_settled_rows'] == 1
    assert sorted(row['state'] for row in b['allocations']) == ['CANCELLED', 'CANCELLED', 'FAILED']
    assert sorted(row['elapsed_seconds'] for row in b['allocations']) == [0, 0, 57]
    total = x9['Slurm_elapsed_billing_SU']+b['Slurm_elapsed_billing_SU']
    assert math.isclose(total, 30.50722222222224, abs_tol=1e-10)
    receipt = HERE/'SETTLEMENT_RECONCILIATION_APPEND_RECEIPT_v1.json'
    assert not receipt.exists(), 'Already appended; reconcile instead of replaying.'
    reply_path = CHANNEL/'CODEX_REPLY.md'
    prior = reply_path.read_bytes()
    section = f'''

## X9 REPORT accounting reconciliation

Fresh own-job snapshot at {x9['checked_utc']}: all389 X9 allocations now settled in AMS. Exact elapsed-times-slots charge {x9['AMS_settled_walltime_slots_SU']:.12f}SU agrees with Slurm {x9['Slurm_elapsed_billing_SU']:.12f}SU; unknown billing/unparsed own rows empty. The prior report's388-row AMS snapshot was settlement timing only. Requested upper remains49.93333333333334/50SU. Rounded AMS display30.51 is secondary; never add AMS and Slurm. New immutable snapshot `experiments/x9-20261106/{x9_path.name}`; no original report, result or figure changed.

Current X9+X10b new-job actual total {total:.12f}SU (including the failed Bpilot57s); CE local0GraceSU. X10b correction remains held pending explicit Claude authorization. No new experimental job submitted.

STATUS: REPORT DONE X9


## X10b PILOT accounting reconciliation

Fresh own-job snapshot at {b['checked_utc']}: Slurm3allocations = original FAILED57s plus two dependency-CANCELLED0s. AMS settled the one nonzero job at {b['AMS_settled_walltime_slots_SU']:.12f}SU, exactly matching Slurm; canceled jobs consume0elapsed. Original requested upper4.166666666666666SU retained conservatively as a bound, not spent. No measured formal forecast exists because timing roles never ran. Snapshot `experiments/x10-20261106/{b_path.name}`. Completed NPG replay preserved for reuse; no repeated NPG, PI/timing/formal submission or modified old result.

Prepared an additional metadata-only preflight `actor-correction-controls-v2/preflight_correction_v2.py` (SHA256 `51cf8213cfe255b6893fa40c7099da9b23093d127f579420be3e8317afdcdf82`), static AST/global-dependency audit PASS. It requires a separately authorized/frozen v2 release and verifies all50reference bytes, all32savedNPGarray hashes, unchanged science/model/schedules, exact prior failed/canceled ledger history, and complete X9 compute before any submission. Prepared only: not deployed or run. The proposed numerical wrapper/reference-bundle hashes remain unchanged. No relaxed numerical equality or resource gate.

Current X9+X10b new-job actual {total:.12f}SU; CE0GraceSU. Corrected pilot authorization still pending, no automatic retry.

STATUS: PILOT STOPPED X10b
'''.encode('utf-8')
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes() == review and reply_path.read_bytes() == prior
    with reply_path.open('ab') as stream:
        stream.write(section)
    assert reply_path.read_bytes() == prior+section
    proof = dict(status='OWN_SETTLED_CHARGES_RECONCILED_APPEND_ONLY',
                 review_sha256=EXPECTED_REVIEW, prior_bytes=len(prior),
                 appended_bytes=len(section), prior_preserved=True,
                 X9_snapshot_sha256=sha(x9_path.read_bytes()),
                 X10b_snapshot_sha256=sha(b_path.read_bytes()),
                 X9_actual_SU=x9['Slurm_elapsed_billing_SU'],
                 X10b_actual_SU=b['Slurm_elapsed_billing_SU'],
                 current_X9_plus_X10b_actual_SU=total, CE_Grace_SU=0,
                 new_experimental_jobs=0, correction_still_requires_authorization=True)
    with receipt.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2)
        stream.write('\n')
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
