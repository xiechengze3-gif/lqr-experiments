"""Merge saved X10b statistics, preserve baseline bytes and apply frozen paper cross."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import numpy as np
import frozen_engine as e
from paper_cross import cross

BASE = Path('/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b')
ROOT = Path(__file__).resolve().parent


def read(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def write(path, rows, fields=None):
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open('x',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def merge(baseline, added, target):
    before, after = baseline.read_bytes(), added.read_bytes()
    first, body = after.split(b'\n',1)
    assert before.splitlines()[0].rstrip(b'\r') == first.rstrip(b'\r')
    assert before.endswith(b'\n')
    with target.open('xb') as stream:stream.write(before+body)
    assert target.read_bytes()[:len(before)] == before
    return dict(baseline_sha256=e.sha(baseline),baseline_bytes=len(before),
                merged_sha256=e.sha(target),baseline_prefix_byte_identical=True)


def derived(summary):
    result=[]
    for algorithm in ['NPG','PI']:
        for n in [24,36,48,72]:
            rows=sorted([r for r in summary if r['algorithm']==algorithm and int(float(r['n']))==n
                         and r['ratio_kind']=='failure_inclusive'],key=lambda r:float(r['rung']))
            assert len(rows) in [4,9]
            assert len({float(r['rung']) for r in rows})==len(rows) and float(rows[-1]['rung'])==1
            budgets=np.array([float(r['primitive_per_arm']) for r in rows])
            y=np.array([float(r['truncated_gap_median']) for r in rows])
            target=float(rows[-1]['dense_gap_median'])
            identified=math.isfinite(target) and target>0
            match=float(cross(budgets,y,target)) if identified else math.nan
            below=any(math.isfinite(v) and v<=target for v in y) if identified else False
            missing=not math.isfinite(match)
            result.append(dict(algorithm=algorithm,n=n,N_cal=budgets[-1],dense_gap_at_N_cal=target,
                truncated_N_to_match=abs(match),left_censored=bool(match<0),
                right_censored=bool(identified and missing and not below),
                unbracketed=bool(identified and missing and below),target_identified=identified,
                factor=budgets[-1]/abs(match) if math.isfinite(match) and match!=0 else math.nan,
                rungs=len(rows),interpretation='Descriptive median-curve crossing; no epsilon/probability guarantee'))
    return result


def main(config_path):
    e.require_compute()
    config=json.loads(config_path.read_text())
    directory=BASE/'report-v1'
    new=directory/'new-rungs'
    proof=json.loads((new/'verification.json').read_text())
    assert proof['status']=='COMPLETE' and proof['config_sha256']==e.sha(config_path)
    assert proof['endpoint_rows']==2560 and proof['paired_cells']==80
    for name,digest in proof['files'].items():assert e.sha(new/name)==digest
    summary=read(new/'summary.csv')
    assert len(summary)==80
    baseline_summary=ROOT/'baseline/summary.csv'
    old=read(baseline_summary)
    assert len(old)==64
    preservation={}
    preservation['summary.csv']=merge(baseline_summary,new/'summary.csv',directory/'summary_merged_nine_rungs.csv')
    all_rows=read(directory/'summary_merged_nine_rungs.csv')
    assert len(all_rows)==144
    assert len({(r['n'],r['algorithm'],r['rung'],r['ratio_kind']) for r in all_rows})==144
    endpoints=read(new/'endpoints.csv')
    baseline_endpoints=read(ROOT/'baseline/endpoints.csv')
    assert len(baseline_endpoints)==2048 and len(endpoints)==2560
    failures=[]
    for origin,rows in [('REUSED_X6b',baseline_endpoints),('NEW_X10b',endpoints)]:
        failures += [dict(r,origin=origin) for r in rows if r['stable']=='False']
    fields=list(dict.fromkeys(k for r in baseline_endpoints+endpoints for k in r))+['origin']
    write(directory/'failures.csv',failures,fields)
    write(directory/'failure_counts_by_cell.csv',[dict(n=r['n'],algorithm=r['algorithm'],rung=r['rung'],
         primitive_per_arm=r['primitive_per_arm'],full=32,
         dense_failures=32-int(float(r['dense_stable'])),truncated_failures=32-int(float(r['truncated_stable'])),
         dense_failure_rate=(32-int(float(r['dense_stable'])))/32,
         truncated_failure_rate=(32-int(float(r['truncated_stable'])))/32)
         for r in all_rows if r['ratio_kind']=='failure_inclusive'])
    nine,four=derived(all_rows),derived(old)
    write(directory/'transitions_saved_derived.csv',nine)
    write(directory/'transitions_saved_original_four_recomputed.csv',four)
    paper=ROOT/'report-baseline/X6b_transitions_saved_derived.csv'
    with (directory/'transitions_saved_original_four_paper.csv').open('xb') as stream:stream.write(paper.read_bytes())
    reference=read(paper)
    assert len(reference)==8
    for row in four:
        ref=next(r for r in reference if r['algorithm']==row['algorithm'] and int(float(r['n']))==row['n'])
        for key in ['N_cal','dense_gap_at_N_cal','truncated_N_to_match','factor']:
            assert math.isclose(float(ref[key]),float(row[key]),rel_tol=2e-12,abs_tol=1e-8),(row['algorithm'],row['n'],key)
        assert (ref['left_censored']=='True')==row['left_censored']
    verification=dict(status='MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED',
        config_sha256=e.sha(config_path),source_sha256=e.sha(__file__),job=os.environ['SLURM_JOB_ID'],
        new_summary_rows=80,baseline_summary_rows=64,merged_summary_rows=144,
        new_endpoint_rows=2560,baseline_endpoint_rows=2048,failures=len(failures),
        four_rung_reference_comparison='PASS_ALL_EIGHT_CELLS',preservation=preservation,
        no_new_training_transitions=True,
        files={p.name:e.sha(p) for p in directory.glob('*.csv')})
    with (directory/'PRODUCTS_COMPLETE_v1.json').open('x') as stream:json.dump(verification,stream,indent=2)
    print(json.dumps({k:v for k,v in verification.items() if k!='files'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True)
    main(p.parse_args().config)
