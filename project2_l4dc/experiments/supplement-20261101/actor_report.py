"""Shared actor report: independently checked candidates, counts, endpoints, cluster ratios."""
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
    assert rows;keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def quant(v,p):
    s=sorted(v);at=p*(len(s)-1);l,h=math.floor(at),math.ceil(at)
    if l==h or s[l]==s[h]:return s[l]
    return math.inf if math.isinf(s[h]) else s[l]+(at-l)*(s[h]-s[l])

def emit(fig,dest,name):
    fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(dest/(name+'.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)

def ingest(exp,completion):
    endpoints=[];records=[];certificates=[];cert_seen=set();checked=0;error_max=0.;countrows=[]
    old=exp=='X1'
    for item in completion['items']:
        p=Path(item['path']);d=json.loads(p.read_text()) if p.exists() else None
        audit=json.loads(p.with_name(p.stem+'.audit.json').read_text()) if old else d
        zp=Path(item['candidate_archive']);assert e.sha(zp)==item['candidate_archive_sha256']
        spec=audit['spec'];alg=audit.get('algorithm','NPG');hard=item['error'] is not None
        with np.load(zp) as z:
            a,b,k0=z['A'],z['B'],z['K0'];n,m=b.shape
            ps=solve_discrete_are(a,b,np.eye(n),np.eye(m));js=float(np.trace(ps));f0=a-b@k0
            p0=solve_discrete_lyapunov(f0.T,np.eye(n)+k0.T@k0);initial=float(np.trace(p0))-js;assert initial>0
            calls=audit['calls'] if old else [r for r in d['records'] if 'assessment_id' in r]
            assert len(calls)==sum(k.startswith('K_') for k in z.files)
            for call in calls:
                gain=z['K_'+call['assessment_id']];f=a-b@gain;rho=float(max(abs(np.linalg.eigvals(f))))
                assert (rho<1-1e-10)==call['stable']
                if call['stable']:
                    p_eval=solve_discrete_lyapunov(f.T,np.eye(n)+gain.T@gain);cost=float(np.trace(p_eval));direct=cost-js
                    err=abs(direct-call['gap'])/max(1.,abs(cost));assert err<1e-8,(exp,str(p),err)
                    error_max=max(error_max,err)
                    assert abs(call['relative_gap']-call['gap']/initial)<1e-7*max(1.,abs(call['relative_gap']))
                checked+=1
            if d:
                records.extend(dict(r,source_json=str(p)) for r in d['records'])
                cert=d['certificate'];assert abs(cert['initial_gap']-initial)<1e-7*max(1.,initial)
                ck=(n,m,spec.get('null_scale',0.),spec.get('spectrum','exact'),spec['system'])
                if ck not in cert_seen:certificates.append(cert);cert_seen.add(ck)
        modes=['dense','truncated'] if old else sorted(item['actual_transitions'])
        if not hard:
            assert d['actual_transitions']==item['actual_transitions']
            assert all(v==item['expected_transitions_per_arm'] for v in d['actual_transitions'].values())
        for mode in modes:
            source_rows=[r for r in d['records'] if r['mode']==mode] if d else []
            last=source_rows[-1] if source_rows else {}
            stable=bool(last.get('stable',False) and not hard)
            endpoint=dict(spec,algorithm=alg,mode=mode,k=last.get('k',m if mode=='dense' else spec['r']),
              stable=stable,whole_path_stable=bool(not hard and source_rows and all(r['stable'] for r in source_rows)),
              gap=last.get('gap') if stable else None,relative_gap=last.get('relative_gap') if stable else None,
              redundant_cost=last.get('redundant_cost') if stable else None,
              hard_failure=hard,actual_transitions=item['actual_transitions'][mode],planned_transitions=item['expected_transitions_per_arm'],
              padding_transitions=last.get('padding_transitions',0),source_json=str(p))
            endpoints.append(endpoint)
            countrows.append(dict(spec,algorithm=alg,mode=mode,actual_transitions=item['actual_transitions'][mode],
              planned_transitions=item['expected_transitions_per_arm'],padding_transitions=last.get('padding_transitions',0),
              hard_failure=hard,paired_count_verified=not hard))
    assert len(endpoints)==completion['planned_actor_trajectories']
    return endpoints,records,certificates,countrows,dict(candidate_policies_independently_checked=checked,max_normalized_gap_identity_error=error_max)

def tables(exp,endpoints,dest):
    groups=defaultdict(list)
    key=lambda r:(r['algorithm'],r['n'],r['m'],r.get('null_scale',0.),r.get('spectrum','exact'),r.get('budget_multiplier',1))
    for r in endpoints:groups[key(r)+(r['mode'],)].append(r)
    stats=[]
    for k,rows in sorted(groups.items()):
        assert len(rows)==32 and len({(r['system'],r['trial']) for r in rows})==32
        for metric in ['gap','relative_gap']:
            v=[r[metric] if r['stable'] else math.inf for r in rows]
            stats.append(dict(algorithm=k[0],n=k[1],m=k[2],null_scale=k[3],spectrum=k[4],budget_multiplier=k[5],mode=k[6],
              k=rows[0]['k'],metric=metric,count=32,stable_count=sum(r['stable'] for r in rows),
              whole_path_stable_count=sum(r['whole_path_stable'] for r in rows),failures=sum(not r['stable'] for r in rows),
              planned_transitions=rows[0]['planned_transitions'],actual_transitions_min=min(r['actual_transitions'] for r in rows),
              actual_transitions_max=max(r['actual_transitions'] for r in rows),padding_transitions_total=sum(r['padding_transitions'] for r in rows),
              median=quant(v,.5),q25=quant(v,.25),q75=quant(v,.75)))
    writecsv(dest/'endpoint_statistics.csv',stats);writecsv(dest/'all_endpoints.csv',endpoints)
    lookup={key(r)+(r['system'],r['trial'],r['mode']):r for r in endpoints};pairs=[];effects=[];pairgroups=defaultdict(list)
    for t in endpoints:
        if t['mode']=='dense':continue
        d=lookup[key(t)+(t['system'],t['trial'],'dense')];finite=d['stable'] and t['stable'] and t['gap']>0
        r=dict(algorithm=t['algorithm'],n=t['n'],m=t['m'],null_scale=t.get('null_scale',0.),spectrum=t.get('spectrum','exact'),
          budget_multiplier=t.get('budget_multiplier',1),mode=t['mode'],system=t['system'],trial=t['trial'],finite_pair=finite,
          dense_stable=d['stable'],method_stable=t['stable'],dense_over_method=d['gap']/t['gap'] if finite else None)
        pairs.append(r);pairgroups[key(t)+(t['mode'],)].append(r)
    bootstrap_seed={'X1':2026110199,'X2':2026110299,'X3':2026110399}[exp]
    random=np.random.default_rng(bootstrap_seed)
    for k,rows in sorted(pairgroups.items()):
        assert len(rows)==32;systems=sorted({r['system'] for r in rows});seeds=sorted({r['trial'] for r in rows});look={(r['system'],r['trial']):r for r in rows}
        values=np.array([[look[(s,t)]['dense_over_method'] if look[(s,t)]['finite_pair'] else np.nan for t in seeds] for s in systems])
        finite=values[np.isfinite(values)];sample=values[random.integers(0,8,size=(2000,8))].reshape(2000,32);valid=np.isfinite(sample).any(axis=1)
        boot=np.nanmedian(sample[valid],axis=1) if valid.any() else []
        effects.append(dict(algorithm=k[0],n=k[1],m=k[2],null_scale=k[3],spectrum=k[4],budget_multiplier=k[5],mode=k[6],
          finite_pairs=len(finite),full_denominator=32,paired_ratio_median=quant(finite,.5) if len(finite) else None,
          bootstrap95_low=quant(boot,.025) if len(boot) else None,bootstrap95_high=quant(boot,.975) if len(boot) else None,
          bootstrap_valid=len(boot),bootstrap_total=2000,independent_systems=8,bootstrap_seed=bootstrap_seed,
          interpretation='finite paired ratios only; full-denominator failures and padding retained separately'))
    writecsv(dest/'paired_ratios.csv',pairs);writecsv(dest/'paired_bootstrap_effects.csv',effects)
    return stats

def figures(exp,stats,dest):
    colors={'dense':'#386aab','truncated':'#cf7735','k2':'#cf7735'}
    if exp=='X1':
        for null in [.25,0.]:
            fig,axs=plt.subplots(2,2,figsize=(10,6))
            for row,alg in enumerate(['NPG','PI']):
                for col,metric in enumerate(['gap','relative_gap']):
                    ax=axs[row,col];counts=[]
                    for mode in ['dense','truncated']:
                        cell=sorted([r for r in stats if r['algorithm']==alg and r['null_scale']==null and r['mode']==mode and r['metric']==metric],key=lambda r:r['m'])
                        valid=[r for r in cell if math.isfinite(r['median'])]
                        x=[r['m']-2 for r in valid];ax.plot(x,[r['median'] for r in valid],'o-',color=colors[mode],label=mode)
                        finite=[r for r in valid if math.isfinite(r['q75'])]
                        ax.fill_between([r['m']-2 for r in finite],[r['q25'] for r in finite],[r['q75'] for r in finite],color=colors[mode],alpha=.1)
                        for r in cell:
                            if r['failures']:ax.text(r['m']-2,.03,f"{mode}:{r['failures']}/32",transform=ax.get_xaxis_transform(),fontsize=6,rotation=20)
                        counts.append(f"{mode} {sum(r['failures'] for r in cell)}/{32*len(cell)}")
                    ax.set(yscale='log',xlabel='Redundant inputs m-r',ylabel=metric,title=f'{alg}; M=93308928 each arm\nEndpoint failures '+', '.join(counts));ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
            fig.suptitle(f'X1 actors null={null}: full32-repeat median/IQR; absorbing failure and discarded K0 padding disclosed',fontsize=9)
            emit(fig,dest,f'actor_null{int(100*null)}')
    elif exp=='X2':
        fig,axs=plt.subplots(1,2,figsize=(10,3.6))
        for ax,metric in zip(axs,['gap','relative_gap']):
            for mode in ['dense','k2']:
                cell=sorted([r for r in stats if r['mode']==mode and r['metric']==metric],key=lambda r:r['n']);valid=[r for r in cell if math.isfinite(r['median'])]
                ax.plot([r['n'] for r in valid],[r['median'] for r in valid],'o-',color=colors[mode],label=mode)
                for r in valid:ax.annotate(f"{r['stable_count']}/32",(r['n'],r['median']),xytext=(3,4 if mode=='dense' else -9),textcoords='offset points',fontsize=7)
            ax.set(yscale='log',xticks=[12,24],xlabel='n=m; compare arms within each n',ylabel=metric,title='Dense-calibrated nd/a_t² schedule');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
        fig.suptitle('X2 NPG endpoints; n12 eta/T .0111539/96, n24 .00282803/384; full32-repeat medians',fontsize=9);emit(fig,dest,'npg_dimension_endpoints')
    else:
        for mult in [1,4,16]:
            fig,axs=plt.subplots(1,3,figsize=(12,3.8))
            for ax,sp in zip(axs,['smooth','gapped','flat']):
                cell=sorted([r for r in stats if r['spectrum']==sp and r['budget_multiplier']==mult and r['metric']=='gap'],key=lambda r:r['k']);valid=[r for r in cell if math.isfinite(r['median'])]
                ax.plot([r['k'] for r in valid],[r['median'] for r in valid],'o-',color='#386aab')
                for r in cell:ax.text(r['k'],.03,f"{r['stable_count']}/32",transform=ax.get_xaxis_transform(),fontsize=6,ha='center')
                ax.set(yscale='log',xticks=[1,2,4,6,12],xlabel='Retained order k; dense=k12',ylabel='Absolute gap, full median',title=f'{sp}; M={cell[0]["planned_transitions"]:,}');ax.grid(alpha=.2)
            fig.suptitle(f'X3 NPG batch multiplier{mult}; actual M includes every burn/baseline/padding transition',fontsize=9);emit(fig,dest,f'npg_order_scan_b{mult}')

def report(exp):
    e.require_compute();scope='ACTOR' if exp=='X1' else 'NPG';completion=json.loads((e.OUT/exp/f'FORMAL_{scope}_COMPLETE.json').read_text())
    assert completion['status']=='COMPLETE';dest=e.OUT/exp/'report-actors';assert not dest.exists();dest.mkdir()
    endpoints,raw,certs,counts,checks=ingest(exp,completion);stats=tables(exp,endpoints,dest)
    writecsv(dest/'primitive_transition_counts.csv',counts);writecsv(dest/'all_recorded_iterates.csv',raw);writecsv(dest/'system_certificates.csv',certs)
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'});figures(exp,stats,dest)
    result=dict(status='COMPLETE',scope=scope,experiment=exp,endpoints=len(endpoints),failed_endpoints=sum(not r['stable'] for r in endpoints),
      hard_failure_attempts=completion['hard_failure_attempts'],unequal_actual_transition_attempts=completion['unequal_actual_transition_attempts'],
      full_failure_denominator_per_cell=32,padding_transitions=sum(r['padding_transitions'] for r in endpoints),
      all_recorded_iterates=len(raw),**checks,source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),
      numerical_accuracy_claim='Relative endpoint comparisons only; no NPG epsilon attainment or theorem-constant certification',
      new_training_transitions=0,job=os.environ['SLURM_JOB_ID'])
    e.save(dest/'REPORT.json',result);print(json.dumps(result),flush=True)

