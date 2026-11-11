"""Saved-data X2/X3 CE report: independent policy checks, failure-inclusive statistics."""
import csv,json,math,os
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_are,solve_discrete_lyapunov
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import engine as e

def csvout(path,rows):
    assert rows
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def quant(values,p):
    a=sorted(values);at=p*(len(a)-1);l,h=math.floor(at),math.ceil(at)
    if l==h or a[l]==a[h]:return a[l]
    return math.inf if math.isinf(a[h]) else a[l]+(at-l)*(a[h]-a[l])

def summarize(values):return dict(median=quant(values,.5),q25=quant(values,.25),q75=quant(values,.75))

def emit(fig,dest,name):
    fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(dest/(name+'.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)

def audit(exp):
    completed=json.loads((e.OUT/exp/'FORMAL_CE_COMPLETE.json').read_text());assert completed['status']=='COMPLETE'
    records=[];certs=[];cert_seen=set();checked=0;max_error=0.;max_radius_error=0.
    for item in completed['raw_hashes']:
        p=Path(item['path']);assert e.sha(p)==item['sha256'];d=json.loads(p.read_text())
        ap=p.with_name(p.stem+'.audit.json');assert e.sha(ap)==item['audit_json_sha256'];a=json.loads(ap.read_text())
        zp=p.with_name(p.stem+'.audit.npz');assert e.sha(zp)==item['candidate_archive_sha256']
        with np.load(zp) as z:
            A,B,K0=z['A'],z['B'],z['K0'];n,m=B.shape
            ps=solve_discrete_are(A,B,np.eye(n),np.eye(m));jstar=float(np.trace(ps))
            for call in a['calls']:
                k=z['K_'+call['assessment_id']];f=A-B@k;rho=float(max(abs(np.linalg.eigvals(f))))
                assert (rho<1-1e-10)==call['stable']
                max_radius_error=max(max_radius_error,abs(rho-call['rho']))
                if call['stable']:
                    p_eval=solve_discrete_lyapunov(f.T,np.eye(n)+k.T@k)
                    direct=float(np.trace(p_eval))-jstar
                    error=abs(direct-call['gap'])/max(1.,abs(float(np.trace(p_eval))))
                    assert error<1e-8,(exp,str(p),call['assessment_id'],error)
                    max_error=max(max_error,error)
                checked+=1
        for row in d['records']:
            if row['stable']:assert math.isfinite(row['gap']) and math.isfinite(row['relative_gap'])
            records.append(dict(row,source_json=str(p)))
        key=(d['spec']['n'],d['spec']['r'],d['spec']['spectrum'],d['spec']['system'])
        if key not in cert_seen:certs.append(d['certificate']);cert_seen.add(key)
    assert len(records)==completed['outputs']
    return records,certs,dict(candidate_policies_independently_checked=checked,max_normalized_gap_identity_error=max_error,max_radius_error=max_radius_error)

def statistics(raw,dest):
    groups=defaultdict(list)
    for r in raw:groups[(r['n'],r['r'],r['spectrum'],r['N'],r['mode'])].append(r)
    stats=[]
    for key,rows in sorted(groups.items()):
        assert len(rows)==32 and len({(r['system'],r['trial']) for r in rows})==32
        for metric in ['gap','relative_gap']:
            vals=[r[metric] if r['stable'] else math.inf for r in rows]
            stats.append(dict(n=key[0],r=key[1],spectrum=key[2],N=key[3],N_over_d=key[3]/(2*key[0]),
               transitions=key[3]+512,mode=key[4],k=rows[0].get('k'),metric=metric,count=32,
               stable_count=sum(r['stable'] for r in rows),failures=sum(not r['stable'] for r in rows),**summarize(vals)))
    csvout(dest/'all_statistics.csv',stats);csvout(dest/'all_records.csv',raw)
    return stats,groups

def paired_x2(raw,dest):
    lookup={(r['n'],r['r'],r['N'],r['system'],r['trial'],r['mode']):r for r in raw}
    rows=[];grouped=defaultdict(dict);random=np.random.default_rng(2026110299)
    for d in raw:
        if d['mode']!='dense':continue
        t=lookup[(d['n'],d['r'],d['N'],d['system'],d['trial'],'truncated')]
        valid=d['stable'] and t['stable'] and t['gap']>0
        absolute=d['gap']/t['gap'] if valid else None
        relative=d['relative_gap']/t['relative_gap'] if valid else None
        if valid:assert abs(absolute-relative)<1e-10*max(1.,abs(absolute))
        row=dict(n=d['n'],r=d['r'],n_over_r=d['n']/d['r'],N=d['N'],N_over_d=d['N']/(2*d['n']),
          system=d['system'],trial=d['trial'],dense_stable=d['stable'],truncated_stable=t['stable'],
          finite_pair=valid,absolute_gap_ratio=absolute,relative_gap_ratio=relative)
        rows.append(row);grouped[(d['n'],d['r'],d['N'])].setdefault(d['system'],[]).append(row)
    csvout(dest/'paired_ratios.csv',rows);effects=[]
    for (n,r,N),systems in sorted(grouped.items()):
        assert len(systems)==8 and all(len(v)==4 for v in systems.values())
        clusters=list(systems.values());resamples=random.integers(0,8,size=(2000,8))
        for metric in ['absolute_gap_ratio','relative_gap_ratio']:
            observed=[p[metric] for c in clusters for p in c if p['finite_pair']]
            values=[]
            for indices in resamples:
                finite=[p[metric] for i in indices for p in clusters[i] if p['finite_pair']]
                if finite:values.append(quant(finite,.5))
            effects.append(dict(n=n,r=r,n_over_r=n/r,N=N,N_over_d=N/(2*n),metric=metric,
              finite_pairs=len(observed),full_denominator=32,dense_stable=sum(p['dense_stable'] for c in clusters for p in c),
              truncated_stable=sum(p['truncated_stable'] for c in clusters for p in c),
              paired_ratio_median=quant(observed,.5) if observed else None,
              bootstrap95_low=quant(values,.025) if values else None,bootstrap95_high=quant(values,.975) if values else None,
              bootstrap_valid=len(values),bootstrap_total=2000,independent_systems=8,
              interpretation='finite-pair diagnostic; whole-system resampling preserves all four seeds; failures retained separately'))
    csvout(dest/'paired_bootstrap_effects.csv',effects)
    selected=[r for r in effects if r['N_over_d'] in [16.,64.,256.]];assert len(selected)==7*3*2
    csvout(dest/'fixed_budget_ratios.csv',selected)
    fig,axs=plt.subplots(1,2,figsize=(11,3.8))
    for ax,metric in zip(axs,['absolute_gap_ratio','relative_gap_ratio']):
        for nd,color in zip([16,64,256],['#386aab','#cf7735','#57976a']):
            points=sorted([r for r in selected if r['r']==2 and r['N_over_d']==nd],key=lambda r:r['n'])
            valid=[r for r in points if r['paired_ratio_median'] is not None]
            x=[r['n_over_r'] for r in valid];y=[r['paired_ratio_median'] for r in valid]
            ax.plot(x,y,'o-',color=color,label=f'N/(n+m)={nd}')
            ax.fill_between(x,[r['bootstrap95_low'] for r in valid],[r['bootstrap95_high'] for r in valid],color=color,alpha=.1)
            for xx,yy,r in zip(x,y,valid):
                if r['finite_pairs']<32:ax.annotate(f"{r['finite_pairs']}/32 pairs",(xx,yy),fontsize=6)
        ax.axhline(1,color='grey',ls='--',lw=.7);ax.set(xlabel='n/r (r=2)',ylabel='Paired dense / truncated gap',title=metric.replace('_',' '),yscale='log')
        ax.grid(alpha=.2);ax.legend(fontsize=7,frameon=False)
    fig.suptitle('X2 CE: exact fixed-budget comparisons; median and system-bootstrap95% interval; no fitted law',fontsize=10)
    emit(fig,dest,'fixed_budget_ratios')
    return effects

def attainment_x2(raw,dest):
    groups=defaultdict(list)
    for r in raw:groups[(r['n'],r['r'],r['mode'])].append(r)
    random=np.random.default_rng(2026110299);output=[]
    for (n,rank,mode),rows in sorted(groups.items()):
        systems=sorted({r['system'] for r in rows});seeds=sorted({r['trial'] for r in rows});grid=sorted({r['N'] for r in rows})
        lookup={(r['system'],r['trial'],r['N']):r for r in rows};resamples=random.integers(0,8,size=(2000,8))
        for metric in ['gap','relative_gap']:
            for epsilon in [.1,.03]:
                counts=np.array([[sum(lookup[(s,t,N)]['stable'] and lookup[(s,t,N)][metric]<=epsilon for t in seeds) for N in grid] for s in systems])
                observed=counts.sum(axis=0);indices=np.flatnonzero(observed>=29);first=int(indices[0]) if len(indices) else None
                boot_counts=counts[resamples].sum(axis=1);boot=[]
                for successes in boot_counts:
                    ix=np.flatnonzero(successes>=29);boot.append(grid[int(ix[0])]+512 if len(ix) else math.inf)
                output.append(dict(n=n,r=rank,mode=mode,metric=metric,epsilon=epsilon,successes_required=29,denominator=32,
                  attained=first is not None,N=grid[first] if first is not None else math.inf,
                  total_transitions=grid[first]+512 if first is not None else math.inf,
                  successes_at_attainment=int(observed[first]) if first is not None else None,
                  max_N=grid[-1],successes_at_max=int(observed[-1]),bootstrap95_low=quant(boot,.025),bootstrap95_high=quant(boot,.975),
                  bootstrap_censored=sum(math.isinf(v) for v in boot),bootstrap_total=2000,
                  censoring='right-censored beyond tested max; no interpolation' if first is None else 'first tested prefix'))
    csvout(dest/'budget_to_epsilon.csv',output)

def paired_x3(raw,certs,dest):
    lookup={(r['n'],r['spectrum'],r['N'],r['system'],r['trial'],r['mode']):r for r in raw}
    grouped=defaultdict(list);pairs=[];random=np.random.default_rng(2026110399)
    for t in raw:
        if t['mode'] in ['dense','k0']:continue
        d=lookup[(t['n'],t['spectrum'],t['N'],t['system'],t['trial'],'dense')]
        finite=d['stable'] and t['stable'] and t['gap']>0
        ratio=d['gap']/t['gap'] if finite else None
        row=dict(n=t['n'],spectrum=t['spectrum'],N=t['N'],mode=t['mode'],system=t['system'],trial=t['trial'],
          dense_stable=d['stable'],method_stable=t['stable'],finite_pair=finite,dense_over_method=ratio)
        pairs.append(row);grouped[(t['n'],t['spectrum'],t['N'],t['mode'])].append(row)
    effects=[]
    for key,rows in sorted(grouped.items()):
        assert len(rows)==32;systems=sorted({r['system'] for r in rows});seeds=sorted({r['trial'] for r in rows})
        look={(r['system'],r['trial']):r for r in rows}
        a=np.array([[look[(s,t)]['dense_over_method'] if look[(s,t)]['finite_pair'] else np.nan for t in seeds] for s in systems])
        finite=a[np.isfinite(a)];sample=a[random.integers(0,8,size=(2000,8))].reshape(2000,32)
        good=np.isfinite(sample).any(axis=1);boots=np.nanmedian(sample[good],axis=1) if good.any() else []
        effects.append(dict(n=key[0],spectrum=key[1],N=key[2],mode=key[3],finite_pairs=len(finite),full_denominator=32,
           dense_stable=sum(r['dense_stable'] for r in rows),method_stable=sum(r['method_stable'] for r in rows),
           paired_ratio_median=quant(finite,.5) if len(finite) else None,
           bootstrap95_low=quant(boots,.025) if len(boots) else None,bootstrap95_high=quant(boots,.975) if len(boots) else None,
           bootstrap_valid=len(boots),bootstrap_total=2000,independent_systems=8,
           relative_gap_ratio_same_as_absolute=True,interpretation='finite pairs, whole-system bootstrap; failures reported out of32'))
    csvout(dest/'paired_ratios.csv',pairs);csvout(dest/'paired_bootstrap_effects.csv',effects)
    tails=[]
    for c in certs:
        for k,(tau,beta) in enumerate(zip(c['tau2'],c['beta'])):
            tails.append(dict(n=c['n'],spectrum=c['spectrum'],system=c['system'],k=k,tau_k_squared=tau,beta_k=beta,
              quantity='true B spectrum diagnostic, not a current-policy Z_K tail'))
    csvout(dest/'spectral_tails.csv',tails)

def x2_curves(stats,dest):
    fig,axs=plt.subplots(2,4,figsize=(13,6))
    for col,n in enumerate([12,24,48,96]):
        for row,metric in enumerate(['gap','relative_gap']):
            ax=axs[row,col];counts=[]
            for mode,color in [('dense','#386aab'),('truncated','#cf7735')]:
                cell=sorted([r for r in stats if r['n']==n and r['r']==2 and r['mode']==mode and r['metric']==metric],key=lambda r:r['N'])
                valid=[r for r in cell if math.isfinite(r['median'])]
                ax.plot([r['N_over_d'] for r in valid],[r['median'] for r in valid],'-o',ms=2,color=color,label=mode)
                both=[r for r in valid if math.isfinite(r['q75'])]
                ax.fill_between([r['N_over_d'] for r in both],[r['q25'] for r in both],[r['q75'] for r in both],color=color,alpha=.1)
                counts.append(f"{mode}:{sum(r['failures'] for r in cell)}/{32*len(cell)}")
            ax.set(xscale='log',yscale='log',xlabel='Regression N/(n+m)',ylabel=metric,title=f'n=m{n}, r2\nFailures '+', '.join(counts))
            ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=6)
    fig.suptitle('X2 CE: failure-inclusive median/IQR; 8 independent systems x4 seeds/cell; add512 burn transitions',fontsize=10)
    emit(fig,dest,'dimension_scaling')

def x3_envelope(stats,dest):
    lookup={(r['n'],r['spectrum'],r['N'],r['mode'],r['metric']):r for r in stats};envelope=[]
    for n in [16,32]:
        fig,axs=plt.subplots(1,3,figsize=(13,4))
        for ax,sp in zip(axs,['smooth','gapped','flat']):
            rows=[r for r in stats if r['n']==n and r['spectrum']==sp and r['metric']=='gap'];grid=sorted({r['N'] for r in rows})
            for N in grid:
                fixed=[r for r in rows if r['N']==N and r['mode'] not in ['adaptive_paper','adaptive_split','k0']]
                best=min(fixed,key=lambda r:(r['median'],r['k']))
                envelope.append(dict(n=n,spectrum=sp,N=N,transitions=N+512,best_k=best['k'],best_mode=best['mode'],
                  envelope_median=best['median'],q25=best['q25'],q75=best['q75'],stable_count=best['stable_count'],
                  diagnostic='post-hoc envelope of failure-inclusive fixed-k medians, unavailable to learner'))
            for mode,color in [('k1','#b8bec7'),('k2','#9fa7b3'),('k4','#929da8'),('k6','#7f8d9d'),
                               ('dense','#386aab'),('adaptive_paper','#cf7735'),('adaptive_split','#57976a')]:
                cell=sorted([r for r in rows if r['mode']==mode],key=lambda r:r['N'])
                valid=[r for r in cell if math.isfinite(r['median'])]
                main=mode in ['dense','adaptive_paper','adaptive_split'];label=mode if main else 'fixed '+mode
                ax.plot([r['N'] for r in valid],[r['median'] for r in valid],color=color,alpha=1 if main else .5,lw=1.7 if main else .7,label=label)
                if main:
                    for r in valid:
                        if r['failures']:ax.scatter(r['N'],r['median'],marker='x',s=12,color=color)
            env=[r for r in envelope if r['n']==n and r['spectrum']==sp and math.isfinite(r['envelope_median'])]
            ax.plot([r['N'] for r in env],[r['envelope_median'] for r in env],'k--',lw=1.2,label='fixed-k envelope (diagnostic)')
            ax.set(xscale='log',yscale='log',xlabel='Regression N (add512 burn)',ylabel='Absolute gap, full median',
              title=f'n=m{n}, {sp}\nAll tested outputs failed:{sum(r["failures"] for r in rows)}/{32*len(rows)} (incl k0)')
            ax.grid(alpha=.2)
        axs[-1].legend(fontsize=6,frameon=False);fig.suptitle('X3 CE: fixed orders and two data-only adaptive rules; crosses indicate some failed outputs',fontsize=10)
        emit(fig,dest,f'spectrum_scan_n{n}')
    csvout(dest/'fixed_k_envelope.csv',envelope)
    return envelope

def stability_heatmaps(stats,exp,dest):
    cells=sorted({(r['n'],r['r'],r['spectrum']) for r in stats})
    for n,rank,sp in cells:
        rows=[r for r in stats if r['n']==n and r['r']==rank and r['spectrum']==sp and r['metric']=='gap']
        grid=sorted({r['N'] for r in rows});modes=sorted({r['mode'] for r in rows},key=lambda m:(m!='dense',m.startswith('adaptive'),int(m[1:]) if m.startswith('k') else -1,m))
        look={(r['mode'],r['N']):r for r in rows};a=np.array([[look[(m,N)]['stable_count'] for N in grid] for m in modes])
        fig,ax=plt.subplots(figsize=(11,max(2.3,.35*len(modes)+1.2)))
        im=ax.imshow(a,aspect='auto',vmin=0,vmax=32,cmap='viridis')
        ax.set(xticks=range(len(grid)),xticklabels=grid,yticks=range(len(modes)),yticklabels=modes,
          xlabel='Exact regression prefix N; total transitions N+512',title=f'{exp}: n{n}, r{rank}, {sp}; stable outputs /32 (all tested cells)')
        ax.tick_params(axis='x',labelrotation=55,labelsize=6)
        for i in range(len(modes)):
            for j in range(len(grid)):ax.text(j,i,str(a[i,j]),ha='center',va='center',fontsize=6,color='white' if a[i,j]<18 else 'black')
        fig.colorbar(im,ax=ax,label='Stable count, denominator32');emit(fig,dest,f'stability_n{n}_r{rank}_{sp}')

def main():
    e.require_compute();plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    for exp in ['X2','X3']:
        dest=e.OUT/exp/'report-ce';assert not dest.exists();dest.mkdir()
        raw,certs,checks=audit(exp);stats,groups=statistics(raw,dest);csvout(dest/'system_certificates.csv',certs)
        if exp=='X2':paired_x2(raw,dest);attainment_x2(raw,dest);x2_curves(stats,dest)
        else:x3_envelope(stats,dest);paired_x3(raw,certs,dest)
        stability_heatmaps(stats,exp,dest)
        result=dict(status='COMPLETE',scope='CE_ONLY',experiment=exp,outputs=len(raw),failed_outputs=sum(not r['stable'] for r in raw),
          **checks,new_training_transitions=0,source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),
          full_failure_denominators=32,bootstrap_seed=2026110299 if exp=='X2' else 2026110399,
          bootstrap_scope='paired ratios for both experiments, X2 epsilon budgets; all four seeds stay inside resampled system clusters',
          job=os.environ['SLURM_JOB_ID'])
        e.save(dest/'REPORT.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
