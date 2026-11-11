"""Append only completed/observed X12 milestones; no submission side effects."""
import argparse,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;C=R.parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def append(a):
    review=(C/'CLAUDE_TASK.md').read_bytes();assert hashlib.sha256(review).hexdigest()==a.expected_review_sha256
    gate=load(R/'PILOT_COST_GATES_v1.json');assert gate['status']=='ALL_PILOT_COST_GATES_PASS' and all(gate['checks'].values())
    if a.stage=='pilot':
        audit=load(R/'PILOT_AUDIT_v1.json');assert len(audit['Slurm'])==11 and all(x['state']=='COMPLETED' for x in audit['Slurm'])
        header='## X12 PILOT\n';end='STATUS: PILOT DONE X12'
        lines=[header,'All registered calibration and both full-nine-rung timing pilots complete. Fixed source/hash, counts, paired RNG receipts, '
            'stage/checkpoint hashes, RSS<80%of2GiB, wallguard and billingoneCPU checks PASS. '
            'Every complete pilot raw bundle SHA-verified on E. N_cal60='+str(gate['N_cal'])+'; no formal outcome or truncated readout used for calibration. '
            'Kernel/estimator bytes and actor numerical source unchanged; hash/literal identity substitutes replay as authorized.\n',
            'All11pilot allocations COMPLETED, actualSlurm '+str(gate['pilot_actual_elapsed_SU'])+'SU/requested8.75SU. '
            'Forecast including allpilots+5minmodel-onlyprep+8SUreport '+str(gate['actual_forecast_SU'])+'/230SU; '
            'requestedupper '+str(gate['requested_upper_SU'])+'/300SU. Global64. Allcostgates PASS. '
            'Historicalfloor rule explicitly accepted in latestClaude23:45Zreview; proceed without another review, no outcome tuning/retry.\n']
        for g in gate['groups']:
            lines.append(g['algorithm']+': measured9rungbody '+str(g['measured_body_seconds'])+'s; historicalfloor '+str(g['historical_floor_seconds'])+
                's; effective '+str(g['body_seconds'])+'s; wall '+str(g['wall_minutes'])+'min/'+g['partition']+';32oneCPU/2GiBtasks.\n')
        lines+=['Proofs: PILOT_AUDIT_v1.json,PILOT_COST_GATES_v1.json,RESOURCE_HISTORY_FLOOR_v1.json,raw-deliveries-v1/. '
                'No formal data yet; next bounded model-only prep constructs the fixed8systems once,0observations.\n']
    elif a.stage=='formal_running':
        d=json.loads((R/'formal-submission-response-v1.json').read_text(encoding='utf-8-sig').strip().splitlines()[-1])
        assert d['status']=='X12_FORMAL_SUBMITTED_ONCE' and len(d['jobs'])==2
        header='## X12 FORMAL running\n';end='STATUS: FORMAL RUNNING X12'
        lines=[header,'Afterfreshreview, PASSfixedpilot/costgates and one-time8modelprep, submitted two independent32element arrays once: '+
            ', '.join(j['role']+'='+j['job'] for j in d['jobs'])+'. '
            'Eachntasks1/oneCPU/2GiB/no-requeue, throttle32+32/global64; prior own queue empty and allpilot/prep COMPLETED. '
            'Allformal arms/rungs/nodes load identical SHA-verified model bytes, systems301..308,seeds1701..1704, '
            'all9frozenrungs,NPG16/PI8,eta.2,H16,rank2. 64allocations/576pairedpaths/1152arms/193644738560transitions.\n',
            'Original measuredactualforecast '+str(gate['actual_forecast_SU'])+'/230SU, requestedupper '+str(gate['requested_upper_SU'])+
            '/300SU including8SUreportreserve. Copy completed rawtasks promptly toE. No tuning, failure deletion, automaticretry or oldpaper/data edit.\n']
    else:
        cov=load(R/'FORMAL_COVERAGE_v1.json');assert cov['status']=='FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS'
        assert cov['bundles']==64 and cov['paired_paths']==576 and cov['primitive_transitions']==193644738560
        header='## X12 FORMAL\n';end='STATUS: FORMAL DONE X12'
        lines=[header,'All64formal allocations COMPLETED; complete receipt/source/model/id/schedule/count coverage PASS, '
            '576pairedpaths/1152arms/193644738560primitive transitions. Every registered configuration and learningfailure retained. '
            'FormalSlurm elapsed '+str(cov['formal_Slurm_elapsed_SU'])+'SU, pilot/model/report additional accounted separately. '
            'Originalforecast '+str(gate['actual_forecast_SU'])+'/230SU; requestedupper '+str(gate['requested_upper_SU'])+
            '/300SU incl8reportreserve. FORMAL_COVERAGE_v1.json carries all64task/576path hashes. '
            'Fullsaved-stage array/update/statistical diagnostics follow in bounded REPORT;0newtraining. No olddata/paper edit.\n']
    prior=(C/'CODEX_REPLY.md').read_bytes();assert header.encode() not in prior,'Milestone already appended; do not duplicate.'
    section=('\n\n'+'\n'.join(lines)+'\nReviewSHA '+a.expected_review_sha256+'\n'+end+'\n').encode()
    assert (C/'CLAUDE_TASK.md').read_bytes()==review and (C/'CODEX_REPLY.md').read_bytes()==prior
    with (C/'CODEX_REPLY.md').open('ab') as f:f.write(section)
    receipt=R/('PUBLISH_'+a.stage.upper()+'_v1.json')
    with receipt.open('x',encoding='utf-8') as f:json.dump(dict(status=end,prior_bytes=len(prior),appended_bytes=len(section),review_sha256=a.expected_review_sha256),f,indent=2)
    print(end)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['pilot','formal_running','formal_done']);p.add_argument('--expected-review-sha256',required=True);append(p.parse_args())
