"""X12 saved-data products, preserving all accepted X10b baseline CSV bytes."""
import argparse,csv,json,math,os
from pathlib import Path
import numpy as np
import frozen_engine as e
from paper_cross import cross
B=Path('/scratch/user/changze/lqr_experiments/results/x12-20261106');R=Path(__file__).resolve().parent
def read(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write(p,rows,fields=None):
    fields=fields or list(dict.fromkeys(k for r in rows for k in r))
    with p.open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def merge(old,added,out):
    before,after=old.read_bytes(),added.read_bytes();head,body=after.split(b'\n',1)
    assert before.splitlines()[0].rstrip(b'\r')==head.rstrip(b'\r') and before.endswith(b'\n')
    with out.open('xb') as f:f.write(before+body)
    assert out.read_bytes()[:len(before)]==before
    return dict(baseline_sha256=e.sha(old),baseline_bytes=len(before),merged_sha256=e.sha(out),baseline_prefix_byte_identical=True)
def derived(summary):
    result=[]
    for alg in ['NPG','PI']:
        rows=sorted([r for r in summary if r['algorithm']==alg and r['ratio_kind']=='failure_inclusive'],key=lambda r:float(r['rung']))
        assert len(rows)==9 and {int(float(r['n'])) for r in rows}=={60}
        budgets=np.array([float(r['primitive_per_arm']) for r in rows]);y=np.array([float(r['truncated_gap_median']) for r in rows])
        target=float(rows[-1]['dense_gap_median']);identified=math.isfinite(target) and target>0
        match=float(cross(budgets,y,target)) if identified else math.nan
        below=any(math.isfinite(v) and v<=target for v in y) if identified else False;missing=not math.isfinite(match)
        result.append(dict(algorithm=alg,n=60,N_cal=budgets[-1],dense_gap_at_N_cal=target,truncated_N_to_match=abs(match),
            left_censored=bool(match<0),right_censored=bool(identified and missing and not below),
            unbracketed=bool(identified and missing and below),target_identified=identified,
            factor=budgets[-1]/abs(match) if math.isfinite(match) and match!=0 else math.nan,rungs=9,
            interpretation='Descriptive median-curve crossing; no epsilon/probability guarantee'))
    return result
def main(config):
    e.require_compute();d=B/'report-v1';new=d/'new-n60';proof=json.loads((new/'verification.json').read_text())
    assert proof['status']=='COMPLETE' and proof['config_sha256']==e.sha(config)
    assert proof['endpoint_rows']==1152 and proof['paired_cells']==36
    for n,h in proof['files'].items():assert e.sha(new/n)==h
    baseline=R/'baseline';manifest=json.loads((baseline/'MANIFEST_v1.json').read_text())
    for n,h in manifest['files'].items():assert e.sha(baseline/n)==h
    rows=read(new/'summary.csv');old=read(baseline/'summary.csv');assert len(rows)==36 and len(old)==144
    preservation={}
    preservation['summary']=merge(baseline/'summary.csv',new/'summary.csv',d/'summary_merged_nine_rungs.csv')
    allrows=read(d/'summary_merged_nine_rungs.csv');assert len(allrows)==180
    assert len({(r['n'],r['algorithm'],r['rung'],r['ratio_kind']) for r in allrows})==180
    derived_rows=derived(rows);oldderived=read(baseline/'transitions_saved_derived.csv');assert len(oldderived)==8
    write(d/'transitions_saved_derived.csv',derived_rows,list(oldderived[0]))
    preservation['derived']=merge(baseline/'transitions_saved_derived.csv',d/'transitions_saved_derived.csv',d/'transitions_saved_merged_nine_rungs.csv')
    assert len(read(d/'transitions_saved_merged_nine_rungs.csv'))==10
    endpoints=read(new/'endpoints.csv');assert len(endpoints)==1152
    failures=[dict(r,origin='NEW_X12') for r in endpoints if r['stable']=='False']
    oldfail=read(baseline/'failures.csv');fields=list(oldfail[0]) if oldfail else list(endpoints[0])+['origin']
    write(d/'failures_new_n60.csv',failures,fields)
    preservation['failures']=merge(baseline/'failures.csv',d/'failures_new_n60.csv',d/'failures.csv')
    cells=[dict(n=r['n'],algorithm=r['algorithm'],rung=r['rung'],primitive_per_arm=r['primitive_per_arm'],full=32,
                dense_failures=32-int(float(r['dense_stable'])),truncated_failures=32-int(float(r['truncated_stable'])),
                dense_failure_rate=(32-int(float(r['dense_stable'])))/32,truncated_failure_rate=(32-int(float(r['truncated_stable'])))/32)
           for r in rows if r['ratio_kind']=='failure_inclusive']
    oldcounts=read(baseline/'failure_counts_by_cell.csv');assert len(oldcounts)==72 and len(cells)==18
    write(d/'failure_counts_new_n60.csv',cells,list(oldcounts[0]))
    preservation['failure_counts']=merge(baseline/'failure_counts_by_cell.csv',d/'failure_counts_new_n60.csv',d/'failure_counts_by_cell.csv')
    result=dict(status='MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED',config_sha256=e.sha(config),source_sha256=e.sha(__file__),
                job=os.environ['SLURM_JOB_ID'],new_summary_rows=36,baseline_summary_rows=144,merged_summary_rows=180,
                new_endpoint_rows=1152,baseline_reanalysis=False,preservation=preservation,new_failures=len(failures),
                no_new_training_transitions=True,files={p.name:e.sha(p) for p in d.glob('*.csv')})
    with (d/'PRODUCTS_COMPLETE_v1.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);main(p.parse_args().config)
