"""Saved diagnostic tables: per-cell summaries, paired changes, append-ready reports."""
import csv,json,math
from collections import defaultdict
from control import ROOT,sha,review,append

def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

review();source=ROOT/'analysis-P1-P2-v1';dest=ROOT/'analysis-P1-P2-tables-v2';assert not dest.exists();dest.mkdir()
stats=read(source/'decomposition_statistics.csv');pop=read(source/'population_model_statistics.csv');endpoints=read(source/'endpoint_decompositions.csv')
effects=read(source/'paired_decomposition_effects.csv');reference=read(source/'population_reference_endpoints.csv');report=json.loads((source/'REPORT.json').read_text())
lookup={(r['experiment'],r['n'],r['m'],r['null_scale'],r['mode'],r['phase'],r['metric']):r for r in stats}
metrics=['total_gap','relative_gap','redundant_D','action_gap','D_over_gap','null_error_fro2','action_error_fro2',
         'learned_minus_population_relative_gap','null_distance_to_population_fro2','action_distance_to_population_fro2']
wide=[]
for key in sorted({(r['experiment'],r['n'],r['m'],r['null_scale'],r['mode'],r['phase']) for r in stats}):
    row=dict(experiment=key[0],n=key[1],m=key[2],m_minus_r=int(key[2])-2,null_scale=key[3],mode=key[4],phase=key[5],count=32,independent_systems=8)
    for metric in metrics:
        r=lookup[key+(metric,)]
        for quantile in ['median','q25','q75']:row[metric+'_'+quantile]=r[quantile]
    wide.append(row)
assert len(wide)==88;write(dest/'cell_phase_component_summary.csv',wide)
getkey=lambda r:(r['experiment'],r['n'],r['m'],r['null_scale'],r['system'],r['trial'])
bykey={getkey(r)+(r['mode'],):r for r in endpoints};changes=[];groups=defaultdict(list)
for t in endpoints:
    if t['mode']!='truncated':continue
    d=bykey[getkey(t)+('dense',)];deltaD=float(t['redundant_D'])-float(d['redundant_D']);deltaA=float(t['action_gap'])-float(d['action_gap'])
    deltaG=float(t['total_gap'])-float(d['total_gap']);tol=1e-10*max(1.,float(t['total_gap']),float(d['total_gap']))
    assert abs(deltaG-deltaD-deltaA)<tol
    row=dict(zip(['experiment','n','m','null_scale','system','trial'],getkey(t)))
    row.update(delta_D_trunc_minus_dense=deltaD,delta_action_gap=deltaA,delta_total_gap=deltaG,numerical_sign_tolerance=tol,
       D_reduced=deltaD<-tol,action_gap_increased=deltaA>tol,total_gap_increased=deltaG>tol,
       redundant_benefit_offset=deltaD<-tol and deltaA>tol)
    changes.append(row);groups[getkey(t)[:4]].append(row)
write(dest/'paired_component_changes.csv',changes);counts=[]
for k,rows in sorted(groups.items()):
    assert len(rows)==32
    counts.append(dict(experiment=k[0],n=k[1],m=k[2],null_scale=k[3],denominator=32,
      D_reduced=sum(r['D_reduced'] for r in rows),action_gap_increased=sum(r['action_gap_increased'] for r in rows),
      redundant_benefit_offset=sum(r['redundant_benefit_offset'] for r in rows),total_gap_increased=sum(r['total_gap_increased'] for r in rows)))
write(dest/'paired_tradeoff_counts.csv',counts)
(dest/'REPORT.json').write_bytes((json.dumps(dict(status='COMPLETE',source_report_sha256=sha(source/'REPORT.json'),code_sha256=sha(__file__),
    summary_rows=88,paired_changes=352,paired_change_identity_verified=True,new_policy_evaluations=0,new_training_transitions=0),indent=2)+'\n').encode())

def interval(r):return f"{float(r['median']):.6g} [{float(r['q25']):.6g}, {float(r['q75']):.6g}]"

for exp in ['X1','X2']:
    body=f'Scope: **{exp} Review04:05 P1/P2 REPORT complete**, saved policies plus deterministic exact-gradient model reference; no sampled learner rerun.\n\n'
    body+='P1 evaluated every saved NPG iterate:55,872 X1+30,848 X2=86,720;704 endpoints. U is the orthonormal input null basis ker(B), V_r spans range(B^T), R=I, Pi=V_r V_r^T. The identity g(K)=D+g(Pi K) holds per output; max normalized residual2.04451e-15, orthogonal Frobenius split residual5.68434e-14. Original gap values match exactly; max original D discrepancy7.10543e-14.\n\n'
    body+='Endpoint medians [IQR], each cell32 runs across8 independent systems; D/g is computed per output before summary:\n\n| null | n,m | Method | D | g(Pi K) | D/g | Null Frobenius error² | Action Frobenius error² |\n|---:|---|---|---|---|---|---|---|\n'
    cells=sorted({(r['n'],r['m'],r['null_scale'],r['mode']) for r in stats if r['experiment']==exp},key=lambda k:(float(k[2]),int(k[0]),int(k[1]),k[3]))
    for n,m,null,mode in cells:
        selected=[lookup[(exp,n,m,null,mode,'endpoint',metric)] for metric in ['redundant_D','action_gap','D_over_gap','null_error_fro2','action_error_fro2']]
        body+=f"| {null} | {n},{m} | {mode} | "+' | '.join(interval(z) for z in selected)+' |\n'
    body+='\nP2 population reference uses the same saved K0, original eta/T and exact objective gradient,88 physical model references total (72 X1,16 X2);8 independent system draws per cell. Sampling seeds do not add population models. True-rank2 Z truncation residual<=7.77658e-15 validates one common dense/truncated population reference. No eta/T retuning.\n\n| null | n,m | eta | T | Population relative gap [IQR],8 models |\n|---:|---|---:|---:|---|\n'
    for p in pop:
        if p['experiment']!=exp or p['metric']!='relative_gap':continue
        r=next(z for z in reference if all(z[k]==p[k] for k in ['experiment','n','m','null_scale']))
        body+=f"| {p['null_scale']} | {p['n']},{p['m']} | {float(r['eta']):.9g} | {r['T']} | {interval(p)} |\n"
    if exp=='X1':
        body+='\nInterpretation: the redundant component is not already negligible. In the nonzero-null family, dense median D/g rises.597/.686/.780/.825 with m-r2/4/7/10; truncated fractions remain.502/.490/.550/.568. Paired D ratios are1.20/1.42/1.61/1.90 with component-bootstrap intervals above1, while action-gap ratio intervals include1 and the original total-gap gain intervals still include1. This is component-specific mechanism evidence, not a clear total-gap advantage. Population relative median.05375 matches across all m>r; sampled endpoints.118–.309 dense and.114–.284 truncated are higher. Small eta has not erased null-direction error.\n'
    else:
        body+='\nInterpretation: dense D/g medians.87565/.86880 at n12/24 are large, rather than negligible. Truncation lowers them to.39981/.34434 and reduces true D (paired ratios1.848[1.803,2.065],3.151[2.804,3.400]). At the same time, truncated action-gap medians.25995/.43577 exceed dense.05788/.10838; the action-gap paired ratio at n12 is.165[.118,.908], and at n24.298[.0427,1.340]. Thus component tradeoffs can offset the redundant-cost reduction. The original mixed total-gap result remains unchanged. Population relative medians.025608/.017115 are below the sampled.577/.715 and.144/.151 levels, so an optimization-step floor alone does not explain the observed errors.\n'
    body+='\nThe per-pair changes and how often D decreases while action error increases are in `analysis-P1-P2-tables-v2/paired_component_changes.csv` and `paired_tradeoff_counts.csv`. This describes endpoint tradeoffs; it does not identify a pure variance or projection-bias causal term. Exact-gradient vs sampled differences may also include finite-H bias and truncation effects. Do not add component medians or call a signed sampled-minus-population gap nonnegative statistical error.\n\n'
    body+='Files: `analysis-P1-P2-v1/all_saved_iterate_decompositions.csv`, `endpoint_decompositions.csv`, `decomposition_statistics.csv`, `population_reference_iterates.csv`, `population_reference_endpoints.csv`, `population_model_statistics.csv`, `population_reference_gains.npz`, `paired_decomposition_effects.csv`, `X1_population_matching_check.csv`, `P1_component_gaps.png/.svg`, `P2_population_vs_sampled.png/.svg`, `REPORT.json`. Complete endpoint/pre-last-update/final16/final-quarter per-run summaries are also joined in `analysis-P1-P2-tables-v2/cell_phase_component_summary.csv`; no correlated iterate is counted as an independent repeat.\n\n'
    body+='New code/config/request protocol frozen in `packages/supplement-20261101-p1-p2-report-v27.manifest.json`; job20359649 completed150s. Delivery15files45,257,314bytes verified locally, old178 files unchanged. Figures visually inspected. Population references are separately counted; training transitions and sampled-learning reruns both0. The original accepted learning results/eta/T remain unchanged, and X3-NPG continues as planned.\n'
    (ROOT/exp/'P1_P2_report_reply.md').write_bytes(body.encode());append(exp,'REPORT',body)
print(json.dumps(dict(status='COMPLETE',reports=['X1','X2'],per_cell_phase_rows=88,paired_tradeoffs=counts)))
