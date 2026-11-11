"""Validate hashes, coverage and saved report fields. No numerical model work."""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import publish_saved_ce as pub

ROOT=Path(__file__).resolve().parent
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_new(name,data):
    path=ROOT/name;assert not path.exists()
    path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')

def main():
    proof=json.loads((ROOT/'summary-verification.json').read_text())
    assert proof['status']=='COMPLETE' and proof['zero_new_transitions']
    assert proof['physical_training_transitions']==37814272
    for name,sha in pub.SOURCES.items():assert digest(ROOT/name)==sha
    assert digest(ROOT/'prepared-formal-v1/formal-config.json')==proof['config_sha256']
    counts={}
    for name,expected in pub.EXPECTED.items():
        assert digest(ROOT/name)==proof['files'][name]
        counts[name]=len(read(name));assert counts[name]==expected
    ss=read('summary.csv');rr=read('paired_ratios.csv');oo=read('adaptive_orders.csv');ll=read('log_slopes.csv')
    assert all(r['full']=='32' and r['stable']=='32' for r in ss)
    assert len({(r['n'],r['spectrum'],r['N'],r['mode']) for r in ss})==336
    by={(r['n'],r['spectrum'],r['N'],r['mode'],r['ratio_kind']):r for r in rr}
    assert len(by)==624
    for r in rr:
        assert all(r[k]=='32' for k in ('ratio_pairs','dense_stable','other_stable','both_stable'))
        assert all(r[k]=='0' for k in ('both_failed','dense_only_failed','other_only_failed','bootstrap_empty'))
        assert r['bootstrap_valid']=='5000'
        other=by[(r['n'],r['spectrum'],r['N'],r['mode'],
            'failure_inclusive' if r['ratio_kind']=='both_stable' else 'both_stable')]
        for key in ('paired_ratio_median','ci_low','ci_high'):assert r[key]==other[key]
    assert all(r['identified']=='True' and r['bootstrap_unidentified']=='0' and r['bootstrap_identified']=='5000' for r in ll)
    for n in ('24','48'):
        for spectrum in ('geometric','polynomial'):
            selected=[r for r in oo if r['n']==n and r['spectrum']==spectrum and r['mode']=='adaptive_paper']
            selected.sort(key=lambda r:int(r['N']))
            assert selected[0]['zero_order']=='32' and selected[0]['k_median']=='0.0'
    acct=json.loads((ROOT/'accounting-20261102T235343.json').read_text())
    assert acct['status']=='BILLING_VERIFIED' and len(acct['allocations'])==41
    assert all(r['state']=='COMPLETED' for r in acct['allocations'])
    assert acct['cumulative_requested_SU']<=15 and not acct['unknown_billing_jobs']
    sealed={}
    for scope,count in [('formal',2049),('report',77)]:
        manifest=ROOT/f'downloads-v1/x7-{scope}-v1.tar.json'
        saved=json.loads(manifest.read_text())
        receipt=json.loads((ROOT/f'delivery-{scope}-v1.verified.json').read_text())
        assert saved['status']=='SEALED' and len(saved['files'])==count
        assert receipt['status']=='VERIFIED_EXTRACTED' and receipt['files']==count
        assert receipt['archive_sha256']==saved['archive_sha256']
        sealed[scope]={'manifest_sha256':digest(manifest),'archive_sha256':saved['archive_sha256'],
            'verified_members':count,'receipt_sha256':digest(ROOT/f'delivery-{scope}-v1.verified.json')}
    figures=json.loads((ROOT/'figures-v1/PLOT_MANIFEST.json').read_text())
    assert figures['source_csv_sha256']==proof['files']
    assert figures['script_sha256']==digest(ROOT/'plot_saved_ce.py')
    for name,expected in figures['figures'].items():assert digest(ROOT/'figures-v1'/name)==expected
    checks={'status':'DELIVERY_PASS','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'csv_counts':counts,'stable_outputs':10752,'failed_outputs':0,'registered_summary_cells':336,
        'ratio_rows':624,'all_pair_counts':32,'bootstrap_repetitions':5000,
        'empty_ratio_draws_per_row':0,'unidentified_slope_draws_per_row':0,
        'completed_allocations':41,'automatic_retries':0,'new_report_transitions':0,
        'formal_physical_transitions':37814272,'requested_bound_SU':acct['cumulative_requested_SU'],
        'slurm_elapsed_billing_SU':acct['slurm_elapsed_billing_SU'],
        'ams_settled_walltime_slots_SU':acct['ams_settled_walltime_slots_SU'],
        'accounting_utc':acct['checked_utc'],'accounting_views_are_not_additive':True,
        'sealed_deliveries':sealed,'visual_qa':'VISUAL_QA_v1.md',
        'scope':'Saved-field consistency, coverage and hashes only; no local numerical analysis'}
    write_new('DELIVERY_CHECK_v1.json',checks)
    names=list(pub.EXPECTED)+list(pub.SOURCES)+[
        'README.md','SCIENCE_REPORT.md','RESULT_TABLES.md','PER_ARM_TABLE.md','VISUAL_QA_v1.md',
        'PROTOCOL.md','PROTOCOL_MANIFEST.json','config-protocol-v1.json','SHA256SUMS',
        'prepared-formal-v1/formal-config.json','prepared-formal-v1/formal-plan.json',
        'RESOURCE_COMPLETE_v1.json','FORMAL_COMPLETE_v1.json','DIAGNOSTICS_COMPLETE_v3.json',
        'SUMMARY_SUBMISSION_v3.json','summary-verification.json','PUBLICATION_CHECK_v1.json',
        'accounting-20261102T235343.json','plot_saved_ce.py','publish_saved_ce.py',
        'validate_saved_delivery.py','transfer_x7.py','DELIVERY_CHECK_v1.json',
        'figures-v1/PLOT_MANIFEST.json']+['figures-v1/'+name for name in figures['figures']]
    write_new('DELIVERY_MANIFEST_v1.json',{'status':'SEALED_SHALLOW_DELIVERY',
        'created_utc':checks['checked_utc'],'files':{name:digest(ROOT/name) for name in names},
        'sealed_raw_report':sealed,'manifest_self_hash':'record externally in CODEX_REPLY.md',
        'note':'No paper tex or earlier result modified. Download manifests enumerate every raw member.'})
    print(json.dumps(checks))
    print('DELIVERY_MANIFEST_SHA256',digest(ROOT/'DELIVERY_MANIFEST_v1.json'))

if __name__=='__main__':main()
