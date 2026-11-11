"""Verified shallow actor tables, then REPORT after image QA and own accounting."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CHANNEL=HERE.parents[1]


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def read(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:return list(csv.DictReader(stream))


def new(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(data)


def prepare():
    delivered=HERE/'delivery-actor-report-v1'
    proof=json.loads(delivered.with_suffix('.verified.json').read_text())
    assert proof['status']=='VERIFIED_EXTRACTED_X10B_DELIVERY'
    root=delivered/'report-v1'
    products=json.loads((root/'PRODUCTS_COMPLETE_v1.json').read_text())
    rendered=json.loads((root/'RENDER_COMPLETE_v1.json').read_text())
    assert products['status']=='MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED'
    assert products['merged_summary_rows']==144 and products['new_summary_rows']==80
    assert products['four_rung_reference_comparison']=='PASS_ALL_EIGHT_CELLS'
    assert rendered['status']=='SAVED_CSV_FIGURES_TABLES_RENDERED'
    for name,digest in dict(products['files'],**rendered['files']).items():assert sha(root/name)==digest
    analysis=json.loads((root/'new-rungs/verification.json').read_text())
    assert analysis['paired_cells']==80 and analysis['endpoint_rows']==2560
    for name,digest in analysis['files'].items():assert sha(root/'new-rungs'/name)==digest
    for meta in products['preservation'].values():assert meta['baseline_prefix_byte_identical']
    baseline=HERE/'actor-draft-v2/baseline/summary.csv'
    assert list(read(root/'new-rungs/summary.csv')[0])==list(read(baseline)[0])
    assert (root/'summary_merged_nine_rungs.csv').read_bytes()[:baseline.stat().st_size]==baseline.read_bytes()
    mapping={'summary.csv':root/'new-rungs/summary.csv',
             'summary_merged_nine_rungs.csv':root/'summary_merged_nine_rungs.csv',
             'endpoints_new_rungs.csv':root/'new-rungs/endpoints.csv',
             'ACTOR_REPORT.md':root/'SCIENCE_REPORT.md'}
    for name in ['transitions_saved_derived.csv','transitions_saved_original_four_recomputed.csv',
                 'transitions_saved_original_four_paper.csv','failures.csv','failure_counts_by_cell.csv']:
        mapping[name]=root/name
    for path in (root/'figures').glob('*'):mapping['actor_figures/'+path.name]=path
    hashes={}
    for name,source in mapping.items():
        target=HERE/name;assert not target.exists(),'Do not overwrite an older delivery.'
        new(target,source.read_bytes());assert sha(target)==sha(source);hashes[name]=sha(target)
    result=dict(status='SHALLOW_ACTOR_VERIFIED_DELIVERY_PREPARED',files=hashes,
                new_summary_rows=80,merged_summary_rows=144,baseline_prefix_byte_identical=True,numerical_reanalysis=False)
    new(HERE/'ACTOR_SHALLOW_DELIVERY_v1.json',(json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))


def complete(args,review):
    receipt=HERE/'ACTOR_REPORT_DONE_APPEND_RECEIPT_v1.json';assert not receipt.exists()
    assert args.visual_qa_note and len(args.visual_qa_note)>30 and args.accounting
    delivery=json.loads((HERE/'ACTOR_SHALLOW_DELIVERY_v1.json').read_text())
    for name,digest in delivery['files'].items():assert sha(HERE/name)==digest
    accounting=json.loads(args.accounting.read_text())
    assert accounting['status']=='OWN_X10B_ACCOUNTING_VERIFIED'
    assert accounting['Slurm_allocation_rows']==264 and all(r['state']=='COMPLETED' for r in accounting['allocations'])
    assert not accounting['unknown_Slurm_billing_jobs'] and not accounting['unparsed_own_AMS_rows']
    assert accounting['cumulative_requested_SU']<=200+1e-9 and accounting['measured_forecast_actual_SU']<=160
    qa=dict(status='VISUAL_QA_PASS',note=args.visual_qa_note,
            images={name:digest for name,digest in delivery['files'].items() if name.endswith('.png')},
            no_statistics_recomputed=True)
    assert len(qa['images'])==3
    prior=(CHANNEL/'CODEX_REPLY.md').read_bytes();assert b'## X10b REPORT\n' not in prior
    lines=['\n\n## X10b REPORT\n',
        'Frozen saved-data diagnostics/statistics, baseline-byte preservation, nine-rung interpolation and PNG/SVG presentation completed. Delivered `experiments/x10-20261106/summary.csv` (80new-only rows, exactX6bschema), `summary_merged_nine_rungs.csv` (144rows, original64rowbytes preserved), `transitions_saved_derived.csv` (nine-rung), both originalfour-rung comparisons, allfailures/percellfailurecounts/rates, `ACTOR_REPORT.md`, actor_figures/ and2560newendpoints. Full savedstates/policies/checkpoints/models/sources/configs/ledgers/logs in delivery-actor-report-v1/.\n',
        'All registered 4n ×2algorithms ×5newrungs ×8systems ×4seeds ×2arms retained:1280pairedpaths/2560arms/243008280576new primitive transitions. Original4rungs reused byreference, no old-data rerun/rebootstrap. Report adds zero training transitions. Gap median/IQR use all32 outcomes with failures at infinity; both ratio definitions and invalid bootstrap mass retained. Report coverage-only assertion adaptation and unchanged statistical function proof included.\n',
        '|n|algorithm|nine-rung saving factor|four-rung factor|left censored|right censored|unbracketed|',
        '|---:|---|---:|---:|---|---|---|']
    nine=read(HERE/'transitions_saved_derived.csv');four=read(HERE/'transitions_saved_original_four_recomputed.csv')
    assert len(nine)==len(four)==8
    for row in nine:
        old=next(r for r in four if r['algorithm']==row['algorithm'] and float(r['n'])==float(row['n']))
        lines.append('|'+ '|'.join([row['n'],row['algorithm'],row['factor'],old['factor'],
                                   row['left_censored'],row['right_censored'],row['unbracketed']])+'|')
    lines += ['\nThe full32 median curve is matched to the dense full-rung gap with the verbatim original paper cross function. The originalfour-rung CSV comparison PASS in all8cells. Every newlowbudgetfailure and every censor remains explicit; no smoothing/extrapolation or epsilon/probability claim. Descriptive densification, no new theorem verification. No paper/result/release edited.\n',
        'Visual QA PASS: '+args.visual_qa_note+'\n',
        ('Accounting snapshot '+accounting['checked_utc']+': requested upper '+str(accounting['cumulative_requested_SU'])
         +'/200 SU; preformal measured actual-spend forecast '+str(accounting['measured_forecast_actual_SU'])
         +'/160 SU; completed Slurm elapsed billing '+str(accounting['Slurm_elapsed_billing_SU'])+' SU; AMS settled '
         +str(accounting['AMS_settled_walltime_slots_SU'])+' SU ('+str(accounting['AMS_own_settled_rows'])+'own rows). '
         'Slurm and AMS overlap and are never added; AMS can settle later, Used & Pending contains reservations. '
         'All264allocations (3pilot+256formal+5report)COMPLETED, no automatic retry. Snapshot `experiments/x10-20261106/'+args.accounting.name+'`.\n'),
        'Proofs: ACTOR_FORMAL_COVERAGE_v1.json; delivery-actor-report-v1/report-v1/{new-rungs/verification,PRODUCTS_COMPLETE_v1,RENDER_COMPLETE_v1}.json; ACTOR_SHALLOW_DELIVERY_v1.json; ACTOR_VISUAL_QA_v1.json.\n',
        'STATUS: REPORT DONE X10b\n']
    section='\n'.join(lines).encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes()==review and (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior
    new(HERE/'ACTOR_VISUAL_QA_v1.json',(json.dumps(qa,indent=2)+'\n').encode())
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior+section
    new(receipt,(json.dumps(dict(prior_bytes=len(prior),appended_bytes=len(section),prior_preserved=True,
        review_sha256=hashlib.sha256(review).hexdigest(),accounting_sha256=sha(args.accounting)),indent=2)+'\n').encode())
    print(json.dumps(dict(status='REPORT_DONE_APPENDED',experiment='X10b',requested_upper_SU=accounting['cumulative_requested_SU'],
        Slurm_elapsed_billing_SU=accounting['Slurm_elapsed_billing_SU'],AMS_settled_SU=accounting['AMS_settled_walltime_slots_SU'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','complete'])
    p.add_argument('--expected-review-sha256',required=True);p.add_argument('--visual-qa-note');p.add_argument('--accounting',type=Path)
    args=p.parse_args();review=(CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert hashlib.sha256(review).hexdigest()==args.expected_review_sha256
    if args.stage=='prepare':prepare()
    else:complete(args,review)
