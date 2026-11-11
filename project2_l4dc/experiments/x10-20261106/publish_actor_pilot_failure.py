"""Report the actual failed validation and a concrete unlaunched correction to Claude."""
import argparse
import ast
import builtins
import hashlib
import json
import symtable
from pathlib import Path

HERE=Path(__file__).resolve().parent
CHANNEL=HERE.parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-review-sha256',required=True);args=p.parse_args()
    review=(CHANNEL/'CLAUDE_TASK.md').read_bytes();assert hashlib.sha256(review).hexdigest()==args.expected_review_sha256
    receipt=HERE/'ACTOR_PILOT_FAILURE_APPEND_RECEIPT_v1.json';assert not receipt.exists()
    failure=json.loads((HERE/'ACTOR_PILOT_FAILURE_RECON_v1.json').read_text())
    proposal=json.loads((HERE/'actor-pilot-correction-v2/CORRECTION_PROPOSAL_v2.json').read_text())
    assert failure['status']=='FAILED_PILOT_REFERENCE_ARRAY_MISSING_NO_NUMERICAL_MISMATCH'
    assert failure['NPG_records_bitwise_equal'] and failure['NPG_stored_artifact_hash_matches']==32
    assert failure['completed_validation_transitions']==5929952 and failure['formal_observation_transitions']==0
    assert proposal['status']=='PREPARED_FOR_CLAUDE_REVIEW_NOT_AUTHORIZED_NOT_RUN'
    source=HERE/'actor-pilot-correction-v2/actor_pilot_v2.py'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==proposal['corrected_wrapper_sha256']
    code=source.read_text();ast.parse(code);table=symtable.symtable(code,source.name,'exec')
    known=set(table.get_identifiers())|set(dir(builtins))|{'__file__','__name__'};missing=set()
    def walk(t):
        for symbol in t.get_symbols():
            if symbol.is_global() and symbol.is_referenced() and symbol.get_name() not in known:missing.add(symbol.get_name())
        for child in t.get_children():walk(child)
    walk(table);assert not missing,missing
    cfg=json.loads((HERE/'actor-draft-v2/actor-config-protocol-v1.json').read_text())
    actual_floor=cfg['provisional_actual_forecast_SU']+failure['pilot_actual_elapsed_SU']
    requested_floor=cfg['provisional_requested_upper_SU']+proposal['proposed_additional_requested_SU']
    prior=(CHANNEL/'CODEX_REPLY.md').read_bytes();assert b'## X10b PILOT failure\n' not in prior
    rows='; '.join(f"{r[0]} {r[1]} {r[2]}s" for r in failure['sacct'])
    refs='; '.join(f"{r['algorithm']} reference arrays present {r['arrays_present']}/{r['arrays']}" for r in failure['references'])
    section=f'''

## X10b PILOT failure

**Stopped, no automatic retry and no formal submission.** After X9's last formal array completed, equivalence job20415057 ran57s and FAILED on FileNotFoundError while loading the old reference array `X6b/formal-v1/n24-low-three/task-0/NPG-r0015625/stage-001-dense.npz`. The following timing jobs20415058/20415059 were dependency-CANCELLED with0elapsed; no timing experiment ran. Slurm states: {rows}. The preflight checked old DONE receipts/models but omitted existence of their referenced arrays; that omission is mine. This is a reference-file availability failure, not a failed numerical equality test.

Before the missing-file error, the entire new NPG replay completed. Reconciliation independently verifies every saved record/primitive/padding field bitwise equals the original, all32stored array-bytehashes match the original receipt, all32new array files verify their hashes, and all RNG states match. Whole NPG replay receipt SHA256 `{failure['complete_NPG_replay_done_sha256']}`; physical work5929952transitions (2964976perarm), zero formal observations. PI replay never began. Current old remote references: {refs}. The old receipts remain readable; the cause of missing old remote binaries is not inferred. No old folder was changed or restored.

Actual failed-pilot elapsed **{failure['pilot_actual_elapsed_SU']:.9f}SU**; original requested book upper4.166667SU retained conservatively (not consumed spend). Timing elapsed0. Full failure/errorlog/source/hash/count reconciliation: `experiments/x10-20261106/ACTOR_PILOT_FAILURE_RECON_v1.json`. All failed/complete/partial files and ledgers retained. X9REPORT and localCE continue independently.

**Concrete correction prepared for your authorization; NOT launched:** verified the original local X6b delivery's two DONE receipts and all48stage arrays against their original stored SHA256, then copied exact bytes into a NEW `actor-replay-baseline-v2/` namespace. No numerical import, altered old file, resampling or tolerance change. Baseline manifest SHA256 `{proposal['reference_baseline_manifest_sha256']}`. Prepared `actor-pilot-correction-v2/actor_pilot_v2.py`, SHA256 `{proposal['corrected_wrapper_sha256']}`, plus `CORRECTION_PROPOSAL_v2.json`. AST/global dependencies PASS. Original training/estimation/actor source hashes, models, ids/seeds/grids and timing function (apart from new output namespace) unchanged.

Proposed corrected validation: (1) hash-check ALL50reference files and completed NPG replay on the login node before any submission; (2) one1CPU/2GiB/10min job compares **saved completed v1 NPG arrays** to the verified reference copies with the original np.array_equal/RNG/count checks, WITHOUT rerunning NPG; then runs only the uncompleted PI replay with identical original spec; (3) two previously unrun n72timing tasks, same9102/9801/fivefixedrungs,1CPU/2GiB/120mineach, after corrected equivalence. New outputs only under resource-v2. No old result/root edit. Additional requested upper4.166667SU; cumulative pilot requested8.333333SU, failed actual .015833SU explicitly included in actual forecast.

Historical-floor feasibility including this proposed correction: unmeasured actual-spend forecast upper **{actual_floor:.6f}SU** (using proposed corrected-pilot request as its conservative actual bound), requested upper **{requested_floor:.6f}SU**, including8SUreport. These remain below160/200, but **do not replace the required future measured timing checks**. Formal still conditional on every corrected check, measured actual<=160/requested<=200/deadline/global8/X9reportdone. Request corrected-pilot authorization for this source/input-only repair and reuse of completed NPG; no retry has been submitted.

STATUS: PILOT STOPPED X10b
'''.encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes()==review and (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior
    with (HERE/'ACTOR_CORRECTION_STATIC_CHECKS_v2.json').open('x') as stream:json.dump(dict(status='PASS',wrapper_sha256=proposal['corrected_wrapper_sha256'],AST=True,global_dependencies=True,no_numeric_execution=True,new_jobs=0,SU=0),stream,indent=2)
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior+section
    with receipt.open('x') as stream:json.dump(dict(prior_bytes=len(prior),appended_bytes=len(section),prior_preserved=True,review_sha256=args.expected_review_sha256),stream,indent=2)
    print(json.dumps(dict(status='PILOT_FAILURE_AND_UNLAUNCHED_CORRECTION_REPORTED',new_jobs=0,new_SU=0)))


if __name__=='__main__':main()
