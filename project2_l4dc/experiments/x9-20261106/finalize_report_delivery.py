"""Prepare shallow verified delivery, then append REPORT after image QA/accounting."""
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
    delivered=HERE/'delivery-report-v1'
    proof=json.loads(delivered.with_suffix('.verified.json').read_text())
    assert proof['status']=='VERIFIED_EXTRACTED_X9_DELIVERY'
    root=delivered/'report-v1'
    analysis=json.loads((root/'verification.json').read_text())
    rendered=json.loads((root/'RENDER_COMPLETE_v1.json').read_text())
    assert analysis['status']=='COMPLETE' and analysis['summary_rows']==80 and analysis['endpoint_rows']==2560
    assert rendered['status']=='SAVED_CSV_FIGURES_TABLES_RENDERED'
    assert rendered['plot_gap_denominator']=='FULL32_FAILURE_INCLUSIVE'
    for name,digest in dict(analysis['files'],**rendered['files']).items():assert sha(root/name)==digest
    summary=read(root/'summary.csv');assert len(summary)==80
    old_fields=list(read(HERE/'baseline/summary.csv')[0])
    assert list(summary[0])==old_fields+['alpha','tau2_sq']
    assert len(read(root/'endpoints.csv'))==2560
    assert len(read(root/'transitions_saved_derived.csv'))==10
    files={}
    sources=[(source,source.relative_to(root)) for source in list(root.glob('*.csv'))+[root/'SCIENCE_REPORT.md']]
    layout_path=HERE/'presentation-v3/PRESENTATION_v3.json'
    layout=None
    if layout_path.exists():
        layout=json.loads(layout_path.read_text(encoding='utf-8'))
        assert layout['status']=='SAVED_CSV_LAYOUT_ONLY_RENDER_COMPLETE'
        assert layout['summary_sha256']==sha(root/'summary.csv')
        assert layout['original_render_proof_sha256']==sha(root/'RENDER_COMPLETE_v1.json')
        assert layout['source_sha256']==sha(layout_path.parent/'render_saved_csv.py')
        assert not layout['numerical_statistics_recomputed'] and layout['new_training_transitions']==0 and layout['Grace_SU']==0
        for name,digest in layout['files'].items():
            source=layout_path.parent/name;assert sha(source)==digest
            sources.append((source,Path(name)))
        sources.append((layout_path,Path('PRESENTATION_v3.json')))
    else:
        sources.extend((source,source.relative_to(root)) for source in (root/'figures').glob('*'))
    for source,relative in sources:
        assert source.is_file()
        target=HERE/relative
        assert not target.exists(),'Do not overwrite any earlier delivery.'
        data=source.read_bytes();new(target,data);assert sha(target)==sha(source)
        files[relative.as_posix()]=sha(target)
    receipt=dict(status='SHALLOW_X9_VERIFIED_DELIVERY_PREPARED',archive_sha256=proof['archive_sha256'],
                 summary_rows=80,endpoint_rows=2560,files=files,numerical_reanalysis=False,
                 selected_presentation='LAYOUT_V3_SAME_FROZEN_CSV' if layout else 'ORIGINAL_V1',
                 original_figures_retained_in_complete_delivery=True)
    new(HERE/'SHALLOW_DELIVERY_v1.json',(json.dumps(receipt,indent=2)+'\n').encode())
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'}))


def complete(args,review):
    assert args.visual_qa_note and len(args.visual_qa_note)>30
    receipt=HERE/'REPORT_DONE_APPEND_RECEIPT_v1.json';assert not receipt.exists()
    delivery=json.loads((HERE/'SHALLOW_DELIVERY_v1.json').read_text())
    assert delivery['status']=='SHALLOW_X9_VERIFIED_DELIVERY_PREPARED'
    for name,digest in delivery['files'].items():assert sha(HERE/name)==digest
    assert args.accounting
    accounting=json.loads(args.accounting.read_text())
    assert accounting['status']=='OWN_X9_ACCOUNTING_VERIFIED'
    assert accounting['Slurm_allocation_rows']==389
    assert all(r['state']=='COMPLETED' for r in accounting['allocations'])
    assert not accounting['unknown_Slurm_billing_jobs'] and not accounting['unparsed_own_AMS_rows']
    assert abs(accounting['cumulative_requested_SU']-49.93333333333334)<1e-8
    qa=dict(status='VISUAL_QA_PASS',note=args.visual_qa_note,
            images={k:v for k,v in delivery['files'].items() if k.endswith('.png')},
            statistics_recomputed=False)
    assert len(qa['images'])==3
    prior=(CHANNEL/'CODEX_REPLY.md').read_bytes();assert b'## X9 REPORT\n' not in prior
    lines=['\n\n## X9 REPORT\n',
        'Completed the frozen saved-data report and verified/extracted the full hashed delivery. Shallow CSVs, PNG/SVG figures, raw endpoint/failure files and SCIENCE_REPORT.md are in `experiments/x9-20261106/`; full states, policies, checkpoints, models, sources/configs/ledgers/logs remain in `delivery-report-v1/`. No original record, release or paper file was changed.\n',
        '80 summary rows, 2560 endpoints (including the entire 512-endpoint saved alpha0 cell), 10 derived matching-budget rows. Every gap median/IQR uses all32 outcomes with failures at infinity. Both ratio definitions and cluster-bootstrap undefined mass retained. Positive-alpha redundant-cost decomposition is N/A.\n',
        'After image QA, layout-v3 moves failure labels and a shared legend outside data axes and preserves correct UTF8 symbols. It reads the identical hash-verified frozen summary, performs zero statistical recomputation/training and uses0GraceSU locally. Source/input/output hashes in presentation-v3/ and PRESENTATION_v3.json; original v1 figures remain in the complete delivery.\n' if delivery.get('selected_presentation')=='LAYOUT_V3_SAME_FROZEN_CSV' else '',
        '|alpha|algorithm|dense absolute|truncated absolute|dense relative|truncated relative|stable D/T (/32)|paired ratio [95% CI]|',
        '|---:|---|---:|---:|---:|---:|---|---|']
    rows=read(HERE/'summary.csv')
    selected=sorted([r for r in rows if float(r['rung'])==1 and r['ratio_kind']=='failure_inclusive'],
                    key=lambda r:(float(r['alpha']),r['algorithm']))
    assert len(selected)==10
    for r in selected:
        lines.append('|'+ '|'.join([r['alpha'],r['algorithm'],r['dense_gap_median'],r['truncated_gap_median'],
          r['dense_relative_gap_median'],r['truncated_relative_gap_median'],r['dense_stable']+'/'+r['truncated_stable'],
          r['paired_ratio_median']+' ['+r['ci_low']+', '+r['ci_high']+']'])+'|')
    lines+=['\nThe full registered four-rung tables, IQRs, first-failure stages, censoring and matching-budget factors are in the linked CSVs/report. X9 is an empirical scan outside the certified conditions of Theorem3 (fixed k2, inherited empirical schedule, alpha.4 large-tail control); no epsilon/probability attainment or theorem-verification claim. Alpha0 is reused by reference, not a new replication.\n',
      f"Visual QA PASS: {args.visual_qa_note}\n",
      ('Accounting snapshot '+accounting['checked_utc']+': requested upper '+str(accounting['cumulative_requested_SU'])
       +'/50 SU; completed Slurm elapsed billing '+str(accounting['Slurm_elapsed_billing_SU'])
       +' SU; AMS settled '+str(accounting['AMS_settled_walltime_slots_SU'])+' SU ('
       +str(accounting['AMS_own_settled_rows'])+' own settled rows). Slurm and AMS overlap and are never added. '
       'AMS may settle later; Used & Pending includes reservations. Snapshot `experiments/x9-20261106/'+args.accounting.name+'`.\n'),
      'All384 formal allocations and the4pilot+1report allocations COMPLETED; no automatic retry. Raw formal coverage1024pairedpaths,2048arms,128849584128newtransitions verified. Report analysis/plots add zero training transitions.\n',
      'STATUS: REPORT DONE X9\n']
    section='\n'.join(lines).encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes()==review
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior
    new(HERE/'VISUAL_QA_v1.json',(json.dumps(qa,indent=2)+'\n').encode())
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior+section
    new(receipt,(json.dumps(dict(prior_bytes=len(prior),appended_bytes=len(section),prior_preserved=True,
         review_sha256=hashlib.sha256(review).hexdigest(),accounting_sha256=sha(args.accounting)),indent=2)+'\n').encode())
    print(json.dumps(dict(status='REPORT_DONE_APPENDED',experiment='X9',requested_upper_SU=accounting['cumulative_requested_SU'],
        completed_Slurm_elapsed_SU=accounting['Slurm_elapsed_billing_SU'],AMS_settled_SU=accounting['AMS_settled_walltime_slots_SU'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','complete'])
    p.add_argument('--expected-review-sha256',required=True);p.add_argument('--visual-qa-note');p.add_argument('--accounting',type=Path)
    args=p.parse_args();review=(CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert hashlib.sha256(review).hexdigest()==args.expected_review_sha256
    if args.stage=='prepare':prepare()
    else:complete(args,review)
