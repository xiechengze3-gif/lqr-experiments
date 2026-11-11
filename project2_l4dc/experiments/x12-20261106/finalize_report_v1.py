"""Verified local products, complete raw coverage, then actual visual QA/accounting."""
import argparse,csv,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;C=R.parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def read(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def new(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(b if isinstance(b,bytes) else (json.dumps(b,indent=2)+'\n').encode())
def prepare():
    delivery=R/'delivery-report-v1';seal=load(delivery.with_suffix('.verified.json'))
    assert seal['status']=='VERIFIED_EXTRACTED_X12_DELIVERY'
    root=delivery/'report-v1';products=load(root/'PRODUCTS_COMPLETE_v1.json');render=load(root/'RENDER_COMPLETE_v1.json')
    assert products['status']=='MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED' and products['new_summary_rows']==36 and products['merged_summary_rows']==180
    assert render['status']=='SAVED_CSV_FIGURES_TABLES_RENDERED'
    for name,h in dict(products['files'],**render['files']).items():assert sha(root/name)==h
    analysis=load(root/'new-n60/verification.json');inspect=load(root/'diagnostics-n60/verification.json')
    assert analysis['paired_cells']==36 and analysis['endpoint_rows']==1152
    assert inspect['endpoint_rows']==1152 and inspect['stage_rows']==14976 and inspect['training_primitive_transitions']==193644738560
    assert inspect['max_update_relative_error']<1e-11
    for name,h in analysis['files'].items():assert sha(root/'new-n60'/name)==h
    for m in products['preservation'].values():assert m['baseline_prefix_byte_identical']
    old=R.parent/'x10-20261106'
    assert list(read(root/'new-n60/summary.csv')[0])==list(read(old/'summary_merged_nine_rungs.csv')[0])
    for file in ['summary_merged_nine_rungs.csv','failures.csv','failure_counts_by_cell.csv']:
        b=(old/file).read_bytes();assert (root/file).read_bytes()[:len(b)]==b
    before=(old/'transitions_saved_derived.csv').read_bytes()
    assert (root/'transitions_saved_merged_nine_rungs.csv').read_bytes()[:len(before)]==before
    cfg=load(R/'formal-release-v1/formal-config.json');coverage=load(R/'FORMAL_COVERAGE_v1.json')
    assert coverage['bundles']==64 and coverage['paired_paths']==576
    done_paths=[]
    for group in cfg['formal_groups']:
        for index in range(32):
            folder=delivery/'formal-v1'/group['id']/('task-'+str(index));done=load(folder/'DONE.json')
            expected=next(x for x in coverage['audits'] if x['group']==group['id'] and x['index']==index)
            assert sha(folder/'DONE.json')==expected['receipt_sha256'] and len(done['paths'])==9
            for path in done['paths']:
                p=folder/path['path']/'DONE.json';assert sha(p)==path['done_sha256'];done_paths.append(p)
    assert len(done_paths)==576
    new(R/'FULL_RAW_E_COVERAGE_v1.json',dict(status='ALL_64_TASKS_576_PAIRED_RAW_PATHS_VERIFIED_ON_E',
        coverage_sha256=sha(R/'FORMAL_COVERAGE_v1.json'),archive_sha256=seal['archive_sha256'],archive_members=seal['files'],
        paired_paths=576,arms=1152,primitive_transitions=193644738560,no_numerical_reanalysis=True))
    mapping={'summary.csv':root/'new-n60/summary.csv','summary_merged_nine_rungs.csv':root/'summary_merged_nine_rungs.csv',
             'endpoints_new_n60.csv':root/'new-n60/endpoints.csv','REPORT.md':root/'SCIENCE_REPORT.md'}
    for name in ['transitions_saved_derived.csv','transitions_saved_merged_nine_rungs.csv','failures_new_n60.csv','failures.csv','failure_counts_new_n60.csv','failure_counts_by_cell.csv']:
        mapping[name]=root/name
    for path in (root/'figures').glob('*'):mapping['figures/'+path.name]=path
    hashes={}
    for name,src in mapping.items():new(R/name,src.read_bytes());assert sha(R/name)==sha(src);hashes[name]=sha(src)
    new(R/'LOCAL_PRODUCTS_VERIFIED_v1.json',dict(status='X12_LOCAL_PRODUCTS_RAW_VERIFIED_VISUAL_QA_PENDING',files=hashes,
        new_rows=36,merged_rows=180,old_bytes_preserved=True,raw_complete=True,statistics_recomputed=False))
    print(json.dumps(dict(status='X12_LOCAL_PRODUCTS_RAW_VERIFIED_VISUAL_QA_PENDING',new_rows=36,merged_rows=180,
                         paired_paths=576,max_update_relative_error=inspect['max_update_relative_error'])))
def complete(a,review):
    receipt=R/'REPORT_DONE_APPEND_RECEIPT_v1.json';assert not receipt.exists()
    assert a.visual_qa_note and len(a.visual_qa_note)>30 and a.accounting
    local=load(R/'LOCAL_PRODUCTS_VERIFIED_v1.json')
    for n,h in local['files'].items():assert sha(R/n)==h
    account=load(a.accounting);assert account['status']=='OWN_X12_ACCOUNTING_VERIFIED'
    assert account['Slurm_allocation_rows']==78 and all(x['state']=='COMPLETED' for x in account['allocations'])
    assert not account['unknown_Slurm_billing_jobs'] and not account['unparsed_own_AMS_rows']
    assert account['cumulative_requested_SU']<=300 and account['measured_forecast_actual_SU']<=230
    assert load(R/'FULL_RAW_E_COVERAGE_v1.json')['paired_paths']==576
    qa=dict(status='VISUAL_QA_PASS',note=a.visual_qa_note,images={n:h for n,h in local['files'].items() if n.endswith('.png')})
    assert len(qa['images'])==3
    prior=(C/'CODEX_REPLY.md').read_bytes();assert b'## X12 REPORT\n' not in prior
    lines=['\n\n## X12 REPORT\n',
       'Completed n=m60 exactrank2 extension:64formal allocations/576pairedpaths/1152arms/193644738560primitive transitions; '
       'all8systems x4seeds x9rungs x2algorithms x2arms retained. N_cal2097152 from registered pilot-only rule. '
       'FrozenSteinNPG16/PI8,eta.2,H16,burn16+baseline1,continuousstates/pairedexternalrandomness unchanged.\n',
       'Delivered experiments/x12-20261106/{summary.csv(36newrows),summary_merged_nine_rungs.csv(180rows),'
       'transitions_saved_derived.csv(2newn60rows),transitions_saved_merged_nine_rungs.csv(10rows),failurecounts/rates/lists,REPORT.md,figures/}. '
       'Accepted144summaryrows/8derivedrows/failuretables are exact byte prefixes;0oldsimulation/bootstrap/reanalysis.\n',
       '|algorithm|n60 saving factor|left censored|right censored|unbracketed|','|---|---:|---|---|---|']
    for row in read(R/'transitions_saved_derived.csv'):
        lines.append('|'+ '|'.join(row[k] for k in ['algorithm','factor','left_censored','right_censored','unbracketed'])+'|')
    lines+=['\nFull32medians/IQR with failures at infinity; bothpaired-ratio definitions/bootstrapundefinedmass/allcensors retained. '
        'Descriptive median-curve crossing by verbatim paper cross, no epsilon/probability guarantee or theorem-verification claim. '
        'All14,976stage records, savedupdates/checkpoints/estimatorarrays audited with unchanged analyzer.\n',
        'Visual QA PASS: '+a.visual_qa_note+'\n',
        'Full raw E coverage PASS: all64task/576path receipts plus every sealedarchive member verified. Sources/models/calibration/timing/failedsubmissionhistory/ledgers/logs retained. '
        'Codex did not edit old results/releases/paper source. Metadata-only UTF8 preparation correction and its failed draft retained.\n',
        'Accounting '+account['checked_utc']+': original measured actualforecast '+str(account['measured_forecast_actual_SU'])+'/230SU; '
        'requestedupper '+str(account['cumulative_requested_SU'])+'/300SU; completedSlurm '+str(account['Slurm_elapsed_billing_SU'])+'SU; '
        'AMSsettled '+str(account['AMS_settled_walltime_slots_SU'])+'SU. AMS/Slurm overlap and are not added; settlement may lag. '
        'All78allocation rows COMPLETED; rejectedsbatchattempts had0allocation and remain in history.\n',
        'STATUS: REPORT DONE X12\n']
    section='\n'.join(lines).encode();assert (C/'CLAUDE_TASK.md').read_bytes()==review and (C/'CODEX_REPLY.md').read_bytes()==prior
    new(R/'VISUAL_QA_v1.json',qa)
    with (C/'CODEX_REPLY.md').open('ab') as f:f.write(section)
    assert (C/'CODEX_REPLY.md').read_bytes()==prior+section
    new(receipt,dict(review_sha256=hashlib.sha256(review).hexdigest(),prior_bytes=len(prior),appended_bytes=len(section),
                     accounting_sha256=sha(a.accounting),old_bytes_preserved=True))
    print(json.dumps(dict(status='REPORT_DONE_APPENDED_X12',Slurm_elapsed_SU=account['Slurm_elapsed_billing_SU'],requested_upper_SU=account['cumulative_requested_SU'])))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','complete']);p.add_argument('--expected-review-sha256',required=True)
    p.add_argument('--visual-qa-note');p.add_argument('--accounting',type=Path);a=p.parse_args()
    review=(C/'CLAUDE_TASK.md').read_bytes();assert hashlib.sha256(review).hexdigest()==a.expected_review_sha256
    if a.stage=='prepare':prepare()
    else:complete(a,review)
