"""Audit every assigned output and generate the two main figures and tables."""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from final_story import (CFG,OUT,KS,BUDGETS,identity,tasks,sha,assigned,plant,
                         robustness,provenance,atomic_json,require_compute)


def csvwrite(p,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def quant(group,key='gap'):
    vals=np.array([r.get(key) if r.get('complete',r.get('stable',False)) and
                   r.get('stable',False) and r.get(key) is not None else np.inf for r in group])
    stable=vals[np.isfinite(vals)]
    return dict(n=len(vals),failures=int(np.count_nonzero(~np.isfinite(vals))),
        median=float(np.median(vals)) if len(vals) and np.isfinite(np.median(vals)) else None,
        stable_median=float(np.median(stable)) if len(stable) else None,
        q25=float(np.quantile(stable,.25)) if len(stable) else None,
        q75=float(np.quantile(stable,.75)) if len(stable) else None)


def main():
    require_compute();report=OUT/'report';report.mkdir(exist_ok=True)
    sel=json.loads((OUT/'threshold_frozen.json').read_text())
    expected=tasks('formal',sel['selection']); endpoints=[];ce=[];stage_rows=[];certs={};checks=[]
    frozen_identity=identity()
    for t in expected:
        p=OUT/'formal'/(t['id']+'.json');d=json.loads(p.read_text())
        assert d['identity']==frozen_identity and d['spec']==t
        assert sha(p.with_suffix('.npz'))==d['policy_sha256']
        c=d['certificates'];certs[(t['family'],t['system'],c['m'])]=c
        spec={k:v for k,v in t.items() if k!='id'}
        if t['algorithm']=='CE':
            for row in d['rows']:
                assert row['transitions']==row['N']+CFG['burn']
                ce.append(dict(spec,**row,complete=True,id=t['id']))
        else:
            planned=assigned(CFG['e1_final'] if t['algorithm']=='PI' else t['final'])
            assert d['assigned_transitions']==planned
            complete=d['status']=='complete';last=d['rows'][-1]
            assert not complete or d['actual_transitions']==planned
            endpoints.append(dict(spec,**last,complete=complete,status=d['status'],
                                  assigned_transitions=planned,id=t['id']))
            stage_rows += [dict(spec,**row,run_complete=complete,id=t['id']) for row in d['rows']]
        checks.append(dict(id=t['id'],json_sha256=sha(p),policy_sha256=d['policy_sha256'],
                           actual_transitions=d['actual_transitions'],seconds=d['seconds'],job=d['provenance']['job']))
    csvwrite(report/'actor_endpoints.csv',endpoints);csvwrite(report/'actor_stages.csv',stage_rows)
    csvwrite(report/'ce_all_prefixes.csv',ce);csvwrite(report/'output_coverage.csv',checks)
    tailrows=[];erows=[]
    for c in certs.values():
        flat={k:v for k,v in c.items() if k not in ['tails','effective_ranks','spectrum']}
        flat['spectrum']=json.dumps(c['spectrum'])
        for tail in c['tails']:tailrows.append(dict(flat,**tail))
        for er in c['effective_ranks']:erows.append(dict(flat,**er))
    csvwrite(report/'system_tails_certificates.csv',tailrows)
    csvwrite(report/'effective_ranks_operational_c1.csv',erows)
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,
                         'figure.dpi':160,'savefig.bbox':'tight','svg.fonttype':'none'})
    fig,axs=plt.subplots(1,2,figsize=(7.1,2.8));e1summary=[]
    colors={('NPG','dense'):'#b53b38',('NPG','truncated'):'#1966a6',
            ('PI','dense'):'#b53b38',('PI','truncated'):'#1966a6'}
    for alg in ['NPG','PI']:
        for mode in ['dense','truncated']:
            ys=[];lo=[];hi=[]
            for m in CFG['ms']:
                group=[e for e in endpoints if e['family']=='E1' and e['algorithm']==alg and e['mode']==mode and e['m']==m]
                q=quant(group);assert q['n']==24
                e1summary.append(dict(algorithm=alg,mode=mode,m=m,m_minus_r=m-2,**q))
                ys.append(q['median']);lo.append(q['q25']);hi.append(q['q75'])
            x=np.array(CFG['ms'])-2
            axs[0].plot(x,ys,'o-' if alg=='NPG' else 's--',ms=3,color=colors[alg,mode],label=alg+' '+mode)
            if all(y is not None for y in ys):axs[0].fill_between(x,lo,hi,color=colors[alg,mode],alpha=.09)
    axs[0].set(xlabel=r'Redundant inputs $m-r$',ylabel=r'Final $J-J^\star$',yscale='log',title='(a) Same assigned transition budget')
    axs[0].legend(fontsize=7,ncol=2)
    ce_summary=[]
    for mode,color in [('dense','#b53b38'),('truncated','#1966a6')]:
        ys=[];lo=[];hi=[]
        for m in CFG['ms']:
            group=[e for e in ce if e['family']=='E1' and e['mode']==mode and e['m']==m and e['N']==8192]
            q=quant(group,'redundant_cost');assert q['n']==24
            ce_summary.append(dict(mode=mode,m=m,m_minus_r=m-2,**q));ys.append(q['median']);lo.append(q['q25']);hi.append(q['q75'])
        axs[1].plot(np.array(CFG['ms'])-2,ys,'o-',ms=3,color=color,label=mode+' CE')
        axs[1].fill_between(np.array(CFG['ms'])-2,lo,hi,color=color,alpha=.12)
    axs[1].plot(np.array(CFG['ms'])-2,[0]*4,'k:',label='True-space projection (oracle)')
    axs[1].set(xlabel=r'Redundant inputs $m-r$',ylabel='True redundant action cost',title='(b) Same OLS data; 8,324 transitions')
    axs[1].legend(fontsize=7);fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(report/('figure1_strict_rank.'+ext))
    plt.close(fig);csvwrite(report/'e1_summary.csv',e1summary);csvwrite(report/'e1_ce_redundant_summary.csv',ce_summary)
    e2summary=[];diagnostics=[];all_e2=[e for e in endpoints if e['family']=='E2']
    fig,axs=plt.subplots(1,2,figsize=(7.1,2.8));palette=['#a8cce4','#649fcb','#286da8','#073d72']
    rank_curves={}
    for final,color in zip(BUDGETS,palette):
        ys=[]
        for k in KS:
            group=[e for e in all_e2 if e['final']==final and e.get('k')==k and e['mode']!='adaptive']
            q=quant(group);assert q['n']==24
            e2summary.append(dict(final=final,transitions=assigned(final),method='fixed',k=k,**q));ys.append(q['median'])
        rank_curves[final]=ys
        axs[0].plot(KS,ys,'o-',color=color,ms=3,label=f'{assigned(final)/1e6:.2f}M')
        finite=[(y,k) for y,k in zip(ys,KS) if y is not None]
        best=min(finite)[1] if finite else None
        dense=[e for e in all_e2 if e['final']==final and e.get('k')==12]
        errors=[e['raw_spectral_error']**2 for e in dense if e['complete']]
        a2=float(np.median(errors)) if errors else None
        _,_,c=plant('E2',101)
        oracle={k:k*a2+c['tails'][k]['tau_k2'] for k in KS} if a2 is not None else None
        diag=dict(final=final,transitions=assigned(final),empirical_best_k=best,
                  a2_dense_final_raw_error_diagnostic=a2,oracle_bound_best_k=min(oracle,key=oracle.get) if oracle is not None else None,
                  min_gap=min(finite)[0] if finite else None,
                  interior_minimum=best not in [None,0,12],oracle_values=oracle)
        diagnostics.append(diag)
    for mode,label,color in [('fixed2','Fixed k=2','#b38c30'),('adaptive','Frozen threshold','#1966a6'),('dense','Dense','#b53b38')]:
        ys=[]
        for final in BUDGETS:
            group=[e for e in all_e2 if e['final']==final and (e['mode']=='adaptive' if mode=='adaptive' else e.get('k')==(2 if mode=='fixed2' else 12))]
            q=quant(group);assert q['n']==24
            ys.append(q['median']);e2summary.append(dict(final=final,transitions=assigned(final),method=mode,**q))
        axs[1].plot([assigned(x) for x in BUDGETS],ys,'o-',color=color,ms=3,label=label)
    axs[1].plot([assigned(x) for x in BUDGETS],[d['min_gap'] for d in diagnostics],'k:',label='Fixed-k median envelope')
    axs[0].set(xlabel='Truncation order k',ylabel=r'Final $J-J^\star$',yscale='log',title='(a) Full-rank geometric spectrum')
    axs[0].legend(title='Total transitions',fontsize=7,title_fontsize=7)
    axs[1].set(xlabel='Assigned transition budget',ylabel=r'Final $J-J^\star$',xscale='log',yscale='log',title='(b) Frozen rank versus threshold')
    axs[1].legend(fontsize=7);fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(report/('figure2_effective_rank.'+ext))
    plt.close(fig);csvwrite(report/'e2_summary.csv',e2summary)
    atomic_json(report/'e2_narrative_diagnostic.json',dict(rows=diagnostics,threshold_selection=sel['selection'],
        warnings=['U-shape and rightward shift are empirical, not theorem conclusions.',
        'a uses true final dense error only offline; the threshold learner does not receive it.',
        'c_eff=1 tail ranks are operational illustrations, not calibrated theorem constants.']))
    robustness();rr=json.loads((OUT/'robustness.json').read_text())['rows'];csvwrite(report/'e3_all_evaluations.csv',rr)
    robust=[]
    for alg in ['NPG','PI']:
        for mode in ['dense','truncated']:
            for delta in [0.,1.,2.,4.,8.,16.]:
                group=[r for r in rr if r['algorithm']==alg and r['mode']==mode and r['delta']==delta]
                vals=[r['relative_change'] for r in group if r['stable']]
                robust.append(dict(algorithm=alg,mode=mode,delta=delta,n_policies=24,directions_per_policy=10,
                    evaluations=len(group),unstable=sum(not r['stable'] for r in group),
                    stable_median_signed_relative_change=float(np.median(vals)) if vals else None,
                    stable_median_absolute_relative_change=float(np.median(np.abs(vals))) if vals else None))
    csvwrite(report/'e3_small_table.csv',robust)
    planned_ids=[]
    for p in OUT.glob('submission-*.json'):planned_ids+=list(json.loads(p.read_text())['jobs'].values())
    ledger=subprocess.check_output(['sacct','-j',','.join(planned_ids),'-n','-P',
        '--format=JobIDRaw,JobID,State,ElapsedRaw,AllocCPUS,AllocTRES'],text=True)
    (report/'slurm_accounting.psv').write_text(ledger)
    used={}
    for line in ledger.splitlines():
        col=line.split('|')
        if len(col)>=6 and col[0] and '.' not in col[1]:
            used[col[0]]=int(col[3] or 0)*int(col[4] or 0)/3600
    summary=dict(status='COMPLETE',formal_task_files=len(expected),actor_trajectories=len(endpoints),
        actor_failures=sum(not e['complete'] for e in endpoints),ce_outputs=len(ce),
        ce_unstable_or_failed=sum(not e['stable'] for e in ce),threshold_selection=sel['selection'],
        formal_physical_transitions=sum(c['actual_transitions'] for c in checks),
        allocated_core_hours_snapshot=sum(used.values()),e1=e1summary,e1_ce=ce_summary,e2=diagnostics,
        e3=robust,identity=identity(),provenance=provenance(),
        accounting_note='Snapshot includes running report elapsed only; final settlement is collected separately.')
    atomic_json(report/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k in ['status','formal_task_files','actor_failures','e2','threshold_selection']}),flush=True)
    manifest={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.suffix in ['.json','.npz','.csv','.svg','.png','.psv'] and p.name!='artifact_sha256.json'}
    atomic_json(OUT/'artifact_sha256.json',manifest)
    archive=BASE/'exports/final-story-20261024.tar.gz';archive.parent.mkdir(exist_ok=True)
    with tarfile.open(archive,'w:gz') as bundle:bundle.add(OUT,arcname=OUT.name)
    atomic_json(archive.with_suffix('.receipt.json'),dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,
         report_sha256=sha(report/'summary.json'),manifest_sha256=sha(OUT/'artifact_sha256.json')))


if __name__=='__main__':main()
