"""X1 CE report with independent policy-cost checks and system-cluster bootstrap."""
import csv,json,math,os
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_are,solve_discrete_lyapunov
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import engine as e

def writecsv(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r));path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def quant(values,q):
    s=sorted(values);p=q*(len(s)-1);l,h=math.floor(p),math.ceil(p)
    if l==h or s[l]==s[h]:return s[l]
    if math.isinf(s[h]):return math.inf
    return s[l]+(p-l)*(s[h]-s[l])
def summary(values):return dict(median=quant(values,.5),q25=quant(values,.25),q75=quant(values,.75))
def main():
    e.require_compute();source=e.OUT/'X1/formal/CE';dest=e.OUT/'X1/report-ce';dest.mkdir(parents=True,exist_ok=True)
    files=[p for p in source.glob('*.json') if not p.name.endswith('.audit.json')];assert len(files)==288
    records=[];certs=[];seen_certs=set();max_error=0.;policies=0;raw_hashes=[]
    for p in sorted(files):
        data=json.loads(p.read_text());audit=json.loads(p.with_name(p.stem+'.audit.json').read_text())
        path=p.with_name(p.stem+'.audit.npz');assert e.sha(path)==audit['candidate_archive_sha256']
        with np.load(path) as z:
            a,b,k0=z['A'],z['B'],z['K0'];n,m=b.shape
            ps=solve_discrete_are(a,b,np.eye(n),np.eye(m));jstar=float(np.trace(ps))
            for call in audit['calls']:
                k=z['K_'+call['assessment_id']];f=a-b@k;rho=float(np.max(np.abs(np.linalg.eigvals(f))))
                assert (rho<1-1e-10)==call['stable']
                if call['stable']:
                    pc=solve_discrete_lyapunov(f.T,np.eye(n)+k.T@k);gap=float(np.trace(pc))-jstar
                    err=abs(gap-call['gap'])/max(1.,abs(float(np.trace(pc))))
                    assert err<1e-8;max_error=max(max_error,err)
                policies+=1
        assert data['transitions']==8704 and data['source_sha256']==e.sha(e.__file__)
        for row in data['records']:
            assert row['transitions']==row['N']+512;records.append(dict(row,source_json=str(p)))
        cert_key=(data['spec']['system'],data['spec']['m'],data['spec']['null_scale'])
        if cert_key not in seen_certs:certs.append(data['certificate']);seen_certs.add(cert_key)
        raw_hashes.append({'path':str(p),'sha256':e.sha(p)})
    assert len(records)==1728
    groups=defaultdict(list)
    for r in records:groups[(r['null_scale'],r['m'],r['N'],r['mode'])].append(r)
    stats=[]
    for key,group in sorted(groups.items()):
        assert len(group)==32 and len({(r['system'],r['trial']) for r in group})==32
        failures=sum(not r['stable'] for r in group)
        for metric in ['gap','relative_gap','redundant_cost']:
            values=[r.get(metric) if r['stable'] else math.inf for r in group]
            assert all(v is not None for v in values)
            stats.append(dict(null_scale=key[0],m=key[1],m_minus_r=key[1]-2,N=key[2],transitions=key[2]+512,
              mode=key[3],metric=metric,count=32,failures=failures,stable_count=32-failures,**summary(values)))
    writecsv(dest/'all_statistics.csv',stats);writecsv(dest/'all_records.csv',records);writecsv(dest/'system_certificates.csv',certs)
    lookup={(r['null_scale'],r['m'],r['N'],r['system'],r['trial'],r['mode']):r for r in records}
    ratio_groups=defaultdict(lambda:defaultdict(list));ratios=[];boot=np.random.default_rng(2026110199)
    for r in records:
        if r['mode']!='dense':continue
        t=lookup[(r['null_scale'],r['m'],r['N'],r['system'],r['trial'],'truncated')]
        val=r['gap']/t['gap'] if r['stable'] and t['stable'] and t['gap']>0 else None
        ratios.append(dict(null_scale=r['null_scale'],m=r['m'],N=r['N'],system=r['system'],trial=r['trial'],dense_over_trunc=val,
          dense_stable=r['stable'],truncated_stable=t['stable']))
        if val is not None:ratio_groups[(r['null_scale'],r['m'],r['N'])][r['system']].append(val)
    effect=[]
    for key,systems in sorted(ratio_groups.items()):
        per_system=np.array([np.median(systems[s]) for s in sorted(systems)])
        resamples=boot.integers(0,len(per_system),size=(2000,len(per_system)))
        medians=np.median(per_system[resamples],axis=1)
        effect.append(dict(null_scale=key[0],m=key[1],N=key[2],finite_pairs=sum(len(v) for v in systems.values()),total_pairs=32,
          independent_systems=len(per_system),paired_ratio_system_median=float(np.median(per_system)),
          bootstrap95_low=float(np.quantile(medians,.025)),bootstrap95_high=float(np.quantile(medians,.975)),
          interpretation='same system/seed/budget; finite-pair ratio diagnostic, failures retained separately'))
    writecsv(dest/'paired_ratios.csv',ratios);writecsv(dest/'system_bootstrap_effects.csv',effect)
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    colors={'dense':'#456ea7','truncated':'#d57538','oracle_true_space_diagnostic':'#5a9762'}
    labels={'dense':'Dense CE','truncated':'Rank-2 CE','oracle_true_space_diagnostic':'True-space oracle (diagnostic)'}
    fig,axs=plt.subplots(1,3,figsize=(12,3.6))
    for ax,metric,label in zip(axs,['gap','relative_gap','redundant_cost'],['Absolute gap','Relative gap','True redundant cost D']):
        for mode in colors:
            cell=[r for r in stats if r['null_scale']==.25 and r['N']==8192 and r['mode']==mode and r['metric']==metric]
            base=next(r for r in stats if r['null_scale']==0 and r['m']==2 and r['N']==8192 and r['mode']==mode and r['metric']==metric)
            rows=[base]+sorted(cell,key=lambda r:r['m']);x=[r['m_minus_r'] for r in rows]
            y=[r['median'] if math.isfinite(r['median']) else np.nan for r in rows]
            ax.plot(x[1:],y[1:],'o-',color=colors[mode],label=labels[mode]);ax.scatter(x[:1],y[:1],marker='x',color=colors[mode])
            for xx,yy,r in zip(x,y,rows):
                if r['failures']:ax.annotate(f"{r['failures']}/32 failed",(xx,yy if math.isfinite(yy) else 0),fontsize=6)
        maxfail=max(r['failures'] for r in stats if r['metric']==metric and r['N']==8192)
        ax.set(xlabel='Redundant inputs m-r',ylabel=label,title=f'Full denominators; failures {maxfail}/32 max per cell')
        if metric!='redundant_cost':ax.set_yscale('log')
        ax.grid(alpha=.2)
    axs[0].legend(fontsize=7,frameon=False);fig.suptitle('X1 CE: unstable independent plants, 8 systems x 4 sampling seeds; m=r is a separate zero-null baseline',fontsize=10)
    fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(dest/('ce_main.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,3.6))
    for N,style in [(4096,'--'),(8192,'-')]:
        for mode in ('dense','truncated'):
            cell=sorted([r for r in stats if r['null_scale']==.25 and r['N']==N and r['mode']==mode and r['metric']=='redundant_cost'],key=lambda r:r['m'])
            ax.plot([r['m_minus_r'] for r in cell],[N*r['median'] for r in cell],style,marker='o',color=colors[mode],label=labels[mode]+f', N={N}')
    scaled_max_fail=max(r['failures'] for r in stats if r['null_scale']==.25 and r['mode'] in ('dense','truncated') and r['metric']=='redundant_cost')
    ax.set(xlabel='Redundant inputs m-r (>0 matched-cost family)',ylabel='N x true redundant cost D',title=f'Both shared OLS prefixes; failures up to {scaled_max_fail}/32 per cell')
    ax.legend(fontsize=7,frameon=False);ax.grid(alpha=.2);fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(dest/('ce_scaled_redundant_cost.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)
    report=dict(status='COMPLETE',scope='X1_CE_ONLY',trajectories=288,outputs=len(records),candidate_policies_independently_checked=policies,
      max_normalized_gap_identity_error=max_error,unstable_outputs=sum(not r['stable'] for r in records),new_training_transitions=288*8704,
      actor_status='REVISE; no actor formal results claimed',raw_hashes=raw_hashes,job=os.environ['SLURM_JOB_ID'],
      source_hashes={'engine':e.sha(e.__file__),'report':e.sha(__file__)})
    e.save(dest/'REPORT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='raw_hashes'}))

if __name__=='__main__':main()
