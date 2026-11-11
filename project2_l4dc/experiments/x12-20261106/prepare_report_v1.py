"""Freeze X12 saved-data report only after whole-formal coverage PASS."""
import argparse,csv,json
from pathlib import Path
import prepare_followon_v1 as p
R=Path(__file__).resolve().parent;X=R.parent/'x10-20261106'
def main(a):
    rb=p.review(a.expected_review_sha256);formal=R/'formal-release-v1';files={}
    for line in (formal/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        h,n=line.split('  ',1);assert p.sha(formal/n)==h;files[n]=(formal/n).read_bytes()
    covpath=R/'FORMAL_COVERAGE_v1.json';cov=p.load(covpath)
    assert cov['status']=='FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS' and cov['bundles']==64 and cov['paired_paths']==576
    assert cov['primitive_transitions']==193644738560 and cov['config_sha256']==p.sha(formal/'formal-config.json')
    files['FORMAL_COVERAGE_v1.json']=covpath.read_bytes()
    for name in ['report_products_v1.py','report_render_v3.py','transfer_report_v1.py','copy_report_provenance_v1.py','submit_report_v1.py','REPORT_SOURCE_PREPARED_v1.json','REPORT_NARRATIVE_CORRECTION_v2.json','REPORT_NARRATIVE_CLARIFICATION_v3.json']:
        files[name]=(R/name).read_bytes()
    sourceproof=p.load(R/'REPORT_SOURCE_PREPARED_v1.json')
    for name,h in sourceproof['files'].items():assert p.sha(R/name)==h
    correction=p.load(R/'REPORT_NARRATIVE_CORRECTION_v2.json')
    assert p.sha(R/'report_render_v2.py')==correction['new_sha256']
    clarification=p.load(R/'REPORT_NARRATIVE_CLARIFICATION_v3.json')
    assert p.sha(R/'report_render_v3.py')==clarification['new_sha256']
    oldproof=X/'delivery-actor-report-v1/report-v1/PRODUCTS_COMPLETE_v1.json';old=p.load(oldproof)
    assert old['status']=='MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED'
    mapping={'summary.csv':'summary_merged_nine_rungs.csv','transitions_saved_derived.csv':'transitions_saved_derived.csv',
             'failures.csv':'failures.csv','failure_counts_by_cell.csv':'failure_counts_by_cell.csv'}
    baseline={}
    for name,src in mapping.items():
        local=X/src;delivered=X/'delivery-actor-report-v1/report-v1'/src
        assert p.sha(local)==p.sha(delivered)==old['files'][src],src
        files['baseline/'+name]=local.read_bytes();baseline[name]=p.sha(local)
    files['baseline/MANIFEST_v1.json']=p.encode(dict(status='ACCEPTED_X10B_BASELINE_BYTES_ONLY',files=baseline,
        source_products_proof_sha256=p.sha(oldproof),old_statistics_recomputed=False,old_training_transitions=0))
    command='analyze_actor.py inspect --config formal-config.json --n 60 --raw "$base/results/x12-20261106/formal-v1" --out "$base/results/x12-20261106/report-v1/diagnostics-n60"'
    files['report-inspect.sbatch']=p.script('report',command)
    python='/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B '
    commands=['analyze_actor.py summarize --config formal-config.json --raw "$base/results/x12-20261106/report-v1" --out "$base/results/x12-20261106/report-v1/new-n60"',
              'report_products_v1.py --config formal-config.json','report_render_v3.py --config formal-config.json','copy_report_provenance_v1.py',
              'transfer_report_v1.py pack --archive "$base/tmp/x12-20261106/x12-report-v1.tar.gz"']
    files['report-aggregate.sbatch']=p.script('report',commands[0]+'\n'+'\n'.join(python+c for c in commands[1:]))
    assert (p.C/'CLAUDE_TASK.md').read_bytes()==rb
    p.package('report',files,a.expected_review_sha256)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--expected-review-sha256',required=True);main(ap.parse_args())
