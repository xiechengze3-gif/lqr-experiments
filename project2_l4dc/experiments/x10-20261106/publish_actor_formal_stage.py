"""Append X10b formal submission or complete coverage, preserving reply prefix."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CHANNEL=HERE.parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['started','complete'])
    p.add_argument('--expected-review-sha256',required=True);args=p.parse_args()
    review=(CHANNEL/'CLAUDE_TASK.md').read_bytes();assert hashlib.sha256(review).hexdigest()==args.expected_review_sha256
    manifest=json.loads((HERE/'ACTOR_FORMAL_MANIFEST_v1.json').read_text())
    cfg=json.loads((HERE/'prepared-actor-formal-v1/formal-config.json').read_text())
    assert manifest['config_sha256']==hashlib.sha256((HERE/'prepared-actor-formal-v1/formal-config.json').read_bytes()).hexdigest()
    plan=manifest['plan'];assert plan['status']=='ALL_GATES_PASS_READY_TO_FREEZE'
    prior=(CHANNEL/'CODEX_REPLY.md').read_bytes()
    receipt=HERE/('ACTOR_FORMAL_'+args.stage.upper()+'_APPEND_RECEIPT_v1.json');assert not receipt.exists()
    if args.stage=='started':
        snapshot=sorted(HERE.glob('actor-formal-progress-*.json'))[-1]
        data=json.loads(snapshot.read_text());chain=data['chain']
        assert chain['status']=='FORMAL_CHAIN_SUBMITTED' and len(chain['jobs'])==8
        assert [r['group'] for r in chain['jobs']]==cfg['formal_order']
        assert not any(g['hard_failure_receipts'] for g in data['groups'])
        lines=['\n\n## X10b FORMAL running\n','All measured pilot checks and both clarified cost/deadline gates passed. All X9 compute including REPORT completed before submission. New-only formal chain submitted once; no old configuration rerun.\n',
               '|group|Slurm array|','|---|---|']
        for row in chain['jobs']:lines.append('|'+row['group']+'|'+row['job']+'|')
        lines += [f"\nOne CPU/2GiB per task, serial afterok arrays capped8. Requested formal upper {plan['formal_requested_upper_SU']:.6f} SU; pilot+formal+8SUreport requested upper {plan['cumulative_requested_upper_SU']:.6f}/200; actual-spend forecast {plan['cumulative_predicted_actual_SU']:.6f}/160 SU. Requested upper and elapsed spend overlap, not added. Frozen config SHA256 `{manifest['config_sha256']}`. Every registered rung/seed retained, failures/padding preserved, no automatic retries.\n",'STATUS: FORMAL RUNNING X10b\n']
    else:
        proofpath=HERE/'ACTOR_FORMAL_COVERAGE_v1.json';proof=json.loads(proofpath.read_text())
        assert proof['status']=='FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS'
        assert proof['config_sha256']==manifest['config_sha256']
        assert (proof['bundles'],proof['paired_paths'],proof['arm_paths'],proof['primitive_transitions'])==(256,1280,2560,243008280576)
        assert len(proof['slurm'])==256 and all(r[1]=='COMPLETED' for r in proof['slurm'])
        assert b'## X10b FORMAL\n' not in prior
        lines=['\n\n## X10b FORMAL\n',
            'All256 formal allocations COMPLETED, with1280new paired paths/2560arms/243008280576 primitive transitions. Whole-grid sources/models/DONE/checkpoint-list/ids/schedules/counts verified; true stage artifact/update diagnostics follow in REPORT. No automatic retry, tuning, grid cut or old-data rerun. Existing4rungs remain reused in full; new5rungs were fixed before the pilot.\n',
            f"Formal completed Slurm elapsed {proof['formal_Slurm_elapsed_SU']:.6f} SU; this excludes pilot/report and overlaps future AMS settlement. Requested book upper including8SUreport remains {plan['cumulative_requested_upper_SU']:.6f}/200, initial actual forecast {plan['cumulative_predicted_actual_SU']:.6f}/160. No claim that the request has already been consumed.\n",
            f"Frozen config SHA256 `{manifest['config_sha256']}`; full proof `experiments/x10-20261106/ACTOR_FORMAL_COVERAGE_v1.json`, SHA256 `{hashlib.sha256(proofpath.read_bytes()).hexdigest()}`. Proceeding to the registered saved-data REPORT (8SUreserve, zero training transitions) after a fresh review read. Report-only coverage assertion adaptation already disclosed; all statistical functions unchanged. No paper edits.\n",
            'STATUS: FORMAL DONE X10b\n']
    section='\n'.join(lines).encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes()==review and (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior+section
    with receipt.open('x') as stream:json.dump(dict(prior_bytes=len(prior),appended_bytes=len(section),prior_preserved=True,
        review_sha256=args.expected_review_sha256),stream,indent=2)
    print(json.dumps(dict(status='FORMAL_'+args.stage.upper()+'_APPENDED',experiment='X10b')))


if __name__=='__main__':main()
