"""Shallow CE delivery and append-only REPORT, after saved statistics and image QA."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CHANNEL=HERE.parents[1]
OUT=HERE/'ce-report-v2'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:return list(csv.DictReader(stream))


def new(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(data)


def prepare():
    statistics=json.loads((OUT/'REPORT_DONE.json').read_text())
    render=json.loads((OUT/'CE_PRESENTATION_v1.json').read_text())
    assert statistics['status']=='COMPLETE_NEW_ROWS_BASELINE_BYTES_PRESERVED'
    assert render['status']=='SAVED_CE_CSV_FIGURES_FAILURE_RATES_RENDERED'
    for name,digest in dict(statistics['files'],**render['files']).items():assert sha(OUT/name)==digest
    mapping={}
    for name in ['X8_sample_cost.csv','X6a_sample_cost_derived.csv','X1_normalized_statistics.csv']:
        mapping[name]=OUT/('new_'+name)
        mapping[Path(name).stem+'_merged.csv']=OUT/('merged_'+name)
    for name in ['censoring_flags.csv','failures.csv','all_failure_rates_by_prefix.csv','plotted_curve_failure_rates.csv']:
        mapping['CE_'+name]=OUT/name
    mapping['CE_REPORT.md']=OUT/'SCIENCE_REPORT.md'
    for path in (OUT/'figures').glob('*'):mapping['ce_figures/'+path.name]=path
    hashes={}
    for name,source in mapping.items():
        target=HERE/name;assert not target.exists(),'Never overwrite an old delivery.'
        new(target,source.read_bytes());assert sha(target)==sha(source);hashes[name]=sha(target)
    proof=dict(status='SHALLOW_CE_VERIFIED_DELIVERY_PREPARED',files=hashes,
               baseline_bytes_preserved=True,source_report_sha256=sha(OUT/'REPORT_DONE.json'),
               presentation_sha256=sha(OUT/'CE_PRESENTATION_v1.json'),numerical_reanalysis=False)
    new(HERE/'CE_SHALLOW_DELIVERY_v1.json',(json.dumps(proof,indent=2)+'\n').encode())
    print(json.dumps(dict(status=proof['status'],files=len(hashes))))


def complete(args,review):
    receipt=HERE/'CE_REPORT_DONE_APPEND_RECEIPT_v1.json';assert not receipt.exists()
    assert args.visual_qa_note and len(args.visual_qa_note)>30
    delivery=json.loads((HERE/'CE_SHALLOW_DELIVERY_v1.json').read_text())
    for name,digest in delivery['files'].items():assert sha(HERE/name)==digest
    coverage=json.loads((HERE/'CE_FORMAL_COVERAGE_v1.json').read_text())
    assert coverage['status']=='PASS_LOCAL_FORMAL_COVERAGE_SOURCES_COUNTS_ARTIFACTS'
    assert coverage['paths']==672 and coverage['primitive_transitions']==236797952
    proof=json.loads((OUT/'REPORT_DONE.json').read_text())
    assert all(r['baseline_prefix_byte_identical'] for r in proof['preservation'].values())
    qa=dict(status='VISUAL_QA_PASS',note=args.visual_qa_note,
            images={name:digest for name,digest in delivery['files'].items() if name.endswith('.png')},
            no_statistics_recomputed=True)
    assert len(qa['images'])==2
    prior=(CHANNEL/'CODEX_REPLY.md').read_bytes();assert b'## X10a REPORT\n' not in prior
    lines=['\n\n## X10a REPORT\n',
       'Completed frozen saved-record statistics, CSV-byte preservation and PNG/SVG presentation. Canonical new-only CSVs at `experiments/x10-20261106/X8_sample_cost.csv`, `X6a_sample_cost_derived.csv`, `X1_normalized_statistics.csv`; `_merged.csv` copies retain every old row as a byte-identical prefix. CE_REPORT.md, ce_figures/, CE_censoring_flags.csv, CE_failures.csv and exact old/new per-prefix failure rates delivered alongside. Full new raw outputs/models/CE fits remain under ce-formal-v2/ and ce-report-v2/.\n',
       'Scope: 672 new physical paths,236797952 primitive transitions. New summary rows32 X8 /7 dimensions /24 normalized cost. One local worker/thread; Grace requested/elapsed0/0 SU, true host/PID and no Slurm id. No old result, release or paper source changed. No extra trajectories for REPORT.\n',
       '|new X8 configuration|absolute target|dense regression N|truncated regression N|',
       '|---|---:|---:|---:|']
    costs=read(HERE/'X8_sample_cost.csv')
    for config in ['r3','r6','r12','r24','rho0.4','rho0.6','rho0.75','rho0.85']:
        rows=[r for r in costs if r['config']==config and float(r['eps'])==.01]
        assert len(rows)==2
        d=next(r for r in rows if r['arm']=='dense');t=next(r for r in rows if r['arm']=='truncated')
        lines.append('|'+ '|'.join([config,'.01',d['N_req'],t['N_req']])+'|')
    lines+=['\n|new n=m|dense N at absolute .01|truncated N at absolute .01|','|---:|---:|---:|']
    for r in read(HERE/'X6a_sample_cost_derived.csv'):
        lines.append('|'+ '|'.join([r['n'],r['dense_N_req'],r['truncated_N_req']])+'|')
    lines += ['\nThe additional X8 .005 target and all X1 N4096/N8192 rows are fully exported. X8 targets follow its accepted absolute-gap amendment; dimension target is absolute .01; X1 normalization is N D(K)/v_star. Median-curve crossings, CIs/IQR and all censor flags use original arithmetic, with no smoothing/extrapolation or 29/32 claim. Every fixed X8 order remains saved. Figures use all failures and explicit right-censor markers; exact failure rates are exported per prefix/arm, including reused inputs.\n',
       'Failed pilot-v1 attempt is preserved and disclosed (portable wrapper missing import json); Claude-authorized v2 correction passed all fixed bitwise checks. The completed original X8 pilot receipt was reused without rerun; no outcome-dependent tuning or cut. Geometric k_eps .01=3/5/10/19, .005=3/6/11/21 from fixed spectra.\n',
       'Descriptive densification of the existing CE experiments; no new theorem-verification or epsilon-probability claim. NPG/PI X10b remains a separate stream under its measured pilot/cap gates.\n',
       'Visual QA PASS: '+args.visual_qa_note+'\n',
       'Proofs: CE_FORMAL_COVERAGE_v1.json; ce-report-v2/REPORT_DONE.json; CE_PRESENTATION_v1.json; CE_SHALLOW_DELIVERY_v1.json; CE_VISUAL_QA_v1.json.\n',
       'STATUS: REPORT DONE X10a\n']
    section='\n'.join(lines).encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes()==review and (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior
    new(HERE/'CE_VISUAL_QA_v1.json',(json.dumps(qa,indent=2)+'\n').encode())
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior+section
    new(receipt,(json.dumps(dict(prior_bytes=len(prior),appended_bytes=len(section),prior_preserved=True,
          review_sha256=hashlib.sha256(review).hexdigest()),indent=2)+'\n').encode())
    print(json.dumps(dict(status='REPORT_DONE_APPENDED',experiment='X10a',Grace_SU=0)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','complete'])
    p.add_argument('--expected-review-sha256',required=True);p.add_argument('--visual-qa-note')
    args=p.parse_args();review=(CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert hashlib.sha256(review).hexdigest()==args.expected_review_sha256
    if args.stage=='prepare':prepare()
    else:complete(args,review)
