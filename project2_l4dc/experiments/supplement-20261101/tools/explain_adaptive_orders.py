"""Review03:30: only aggregate saved CSV/certificates; no model fit or learning run."""
import ast,csv,json,math
from collections import Counter,defaultdict
from control import ROOT,sha,review,append

def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def quant(v,p):
    a=sorted(v);at=p*(len(a)-1);l,h=math.floor(at),math.ceil(at)
    return a[l] if l==h else a[l]+(at-l)*(a[h]-a[l])

checked=review();assert 'Review 03:30 CDT' in checked['review_log']
old=ROOT/'X3/report-ce';dest=ROOT/'X3/report-ce-rank-explanation-v4';assert not dest.exists();dest.mkdir()
raw=read(old/'all_records.csv');certs=read(old/'system_certificates.csv');envelope=read(old/'fixed_k_envelope.csv')
true={}
for c in certs:true[(int(c['n']),c['spectrum'],int(c['system']))]=(ast.literal_eval(c['beta']),ast.literal_eval(c['tau2']))
best={(int(r['n']),r['spectrum'],int(r['N'])):r for r in envelope}
per_run=[];groups=defaultdict(list)
for r in raw:
    if r['mode'] not in ['adaptive_paper','adaptive_split']:continue
    n,N,k=int(r['n']),int(r['N']),int(r['k']);beta,tau=true[(n,r['spectrum'],int(r['system']))];b=best[(n,r['spectrum'],N)]
    assert 0<=k<=n and len(beta)==n+1
    row=dict(n=n,spectrum=r['spectrum'],N=N,total_transitions=N+512,system=r['system'],trial=r['trial'],method=r['mode'],
      retained_k=k,stable=r['stable'],threshold=float(r['threshold']),smallest_retained_true_sigma=beta[k-1] if k else None,
      largest_omitted_true_sigma=beta[k] if k<n else 0.,true_tau_selected_order_squared=tau[k],
      best_fixed_k=int(b['best_k']),best_fixed_median=float(b['envelope_median']),best_fixed_stable_count=int(b['stable_count']),
      interpretation='True spectrum indexed by data-selected order; not an estimated-subspace alignment certificate')
    per_run.append(row);groups[(n,r['spectrum'],N,r['mode'])].append(row)
assert len(per_run)==6912
write(dest/'per_output_orders_and_thresholds.csv',per_run);summary=[]
for (n,sp,N,mode),rows in sorted(groups.items()):
    assert len(rows)==32
    k=[r['retained_k'] for r in rows];threshold=[r['threshold'] for r in rows];sigma=[r['smallest_retained_true_sigma'] for r in rows if r['retained_k']>0]
    row=dict(n=n,spectrum=sp,N=N,total_transitions=N+512,method=mode,count=32,stable_count=sum(r['stable']=='True' for r in rows),
      best_fixed_k=rows[0]['best_fixed_k'],best_fixed_median=rows[0]['best_fixed_median'],best_fixed_stable_count=rows[0]['best_fixed_stable_count'],
      retained_k_median=quant(k,.5),retained_k_q25=quant(k,.25),retained_k_q75=quant(k,.75),
      retained_k_histogram=json.dumps(dict(sorted(Counter(k).items())),separators=(',',':')),k0_count=k.count(0),
      threshold_median=quant(threshold,.5),threshold_q25=quant(threshold,.25),threshold_q75=quant(threshold,.75),
      smallest_retained_true_sigma_median=quant(sigma,.5) if sigma else None,
      smallest_retained_true_sigma_min=min(sigma) if sigma else None,smallest_retained_true_sigma_max=max(sigma) if sigma else None,
      sigma_defined_count=len(sigma),largest_omitted_true_sigma_median=quant([r['largest_omitted_true_sigma'] for r in rows],.5),
      true_tau_selected_order_squared_median=quant([r['true_tau_selected_order_squared'] for r in rows],.5))
    if mode=='adaptive_paper':assert max(threshold)-min(threshold)<1e-12
    summary.append(row)
write(dest/'orders_by_case_budget_method.csv',summary);wide=[]
for n,sp,N in sorted({(k[0],k[1],k[2]) for k in groups}):
    values=[r for r in summary if r['n']==n and r['spectrum']==sp and r['N']==N]
    row=dict(n=n,spectrum=sp,N=N,total_transitions=N+512,best_fixed_k=values[0]['best_fixed_k'],best_fixed_median=values[0]['best_fixed_median'],
       best_fixed_stable_count=values[0]['best_fixed_stable_count'])
    for r in values:
        for key in ['retained_k_median','retained_k_q25','retained_k_q75','retained_k_histogram','stable_count','k0_count','threshold_median',
                    'threshold_q25','threshold_q75','smallest_retained_true_sigma_median','largest_omitted_true_sigma_median','sigma_defined_count']:
            row[r['method']+'_'+key]=r[key]
    wide.append(row)
assert len(wide)==108 and len(summary)==216
write(dest/'adaptive_orders_vs_best_fixed.csv',wide)
result=dict(status='COMPLETE',scope='Review03:30 requested adaptive-order explanation',case_budget_rows=108,method_rows=216,per_output_rows=6912,
   source_hashes={p.name:sha(p) for p in [old/'all_records.csv',old/'system_certificates.csv',old/'fixed_k_envelope.csv']},
   code_sha256=sha(__file__),new_training_transitions=0,new_learning_runs=0,local_provenance='Standard-library aggregation of delivered Grace files; no new Slurm job',
   C5_retuned=False)
(dest/'REPORT.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
body='Scope: X3 CE Review03:30 **postprocessing-only table complete**, C5 unchanged.\n\n'
body+='For all108(n,spectrum,N) cells, `X3/report-ce-rank-explanation-v4/adaptive_orders_vs_best_fixed.csv` places both adaptive selected-order distributions next to the best fixed-k median. The216-row long table adds stable counts, k0 counts, threshold median/IQR, the smallest retained true singular value and the next omitted true singular value;6912 per-output rows retain exact k/threshold/system/seed.\n\n'
body+='| n | Spectrum | N | Best fixed k | Method | Selected k median | Threshold median | Smallest retained true sigma median | Next omitted true sigma median | Stable |\n|---:|---|---:|---:|---|---:|---:|---:|---:|---:|\n'
for n in [16,32]:
    N=max(r['N'] for r in summary if r['n']==n)
    for r in summary:
        if r['n']!=n or r['spectrum']!='gapped' or r['N']!=N:continue
        body+=f"| {n} | two-level | {N} | {r['best_fixed_k']} | {r['method']} | {r['retained_k_median']:.6g} | {r['threshold_median']:.6g} | {r['smallest_retained_true_sigma_median']:.6g} | {r['largest_omitted_true_sigma_median']:.6g} | {r['stable_count']}/32 |\n"
body+='\nThese are true singular values indexed by the data-selected order, not fitted singular values or an alignment certificate. k0 has no smallest retained singular value and is explicitly undefined, with its count shown. The next-omitted value makes the.05 tail cutoff visible. Frozen C5 and all formal outcomes remain unchanged; zero fitting, trajectories, or learning reruns. Source hashes and local processing provenance are in the new REPORT.json.\n'
(ROOT/'X3/adaptive_explanation_reply.md').write_bytes(body.encode());append('X3','REPORT',body)
print(json.dumps(result));print(body)
