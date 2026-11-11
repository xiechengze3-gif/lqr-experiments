"""Review04:05: saved-policy redundancy/action split and zero-sample population references."""
import csv,json,math,os,time
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_are,solve_discrete_lyapunov
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import engine as e
from actor_report import writecsv,quant,emit

METRICS=['total_gap','relative_gap','redundant_D','action_gap','D_over_gap','null_error_fro2','action_error_fro2',
         'population_relative_gap','learned_minus_population_relative_gap','null_distance_to_population_fro2','action_distance_to_population_fro2']

def model(a,b,k0,spec,eta,T,model_id,source):
    n,m=b.shape;_,singular,vh=np.linalg.svd(b,full_matrices=True);rank=2
    assert abs(singular[1]-1)<1e-10 and np.linalg.norm(singular[2:])<1e-10
    v=vh[:rank].T;u=vh[rank:].T;pi=np.eye(m) if m==rank else v@v.T
    assert np.linalg.norm(b@pi-b)<1e-10 and np.linalg.norm(b@u)<1e-10
    ps=solve_discrete_are(a,b,np.eye(n),np.eye(m));ks=np.linalg.solve(np.eye(m)+b.T@ps@b,b.T@ps@a)
    f0=a-b@k0;p0=solve_discrete_lyapunov(f0.T,np.eye(n)+k0.T@k0);initial=float(np.trace(p0-ps));assert initial>0
    return dict(A=a,B=b,K0=k0,Pstar=ps,Kstar=ks,Hstar=np.eye(m)+b.T@ps@b,V=v,U=u,Pi=pi,
      initial_gap=initial,eta=eta,T=T,spec=spec,model_id=model_id,source_json=source)

def decomposition(s,k):
    a,b=s['A'],s['B'];f=a-b@k;rho=float(max(abs(np.linalg.eigvals(f))));assert rho<1-1e-10
    cov=solve_discrete_lyapunov(f,np.eye(len(a)));delta=k-s['Kstar'];projected=s['Pi']@k
    assert np.linalg.norm(a-b@projected-f)<1e-9*max(1.,np.linalg.norm(f))
    null=s['U'].T@k;delta_projected=projected-s['Kstar'];null_error=s['U'].T@delta;action_error=s['V'].T@delta
    D=float(np.trace(null@cov@null.T));g=float(np.trace(cov@delta.T@s['Hstar']@delta))
    action=float(np.trace(cov@delta_projected.T@s['Hstar']@delta_projected))
    split=abs(g-D-action)/max(1.,abs(g));orth=abs(float(np.sum(delta**2))-float(np.sum(null_error**2)+np.sum(action_error**2)))
    assert split<1e-8 and orth<1e-8*max(1.,float(np.sum(delta**2)))
    assert g>0 and D>=-1e-12 and D<=g+1e-8*max(1.,g)
    return dict(rho=rho,total_gap=g,relative_gap=g/s['initial_gap'],redundant_D=D,action_gap=action,D_over_gap=D/g,
      null_error_fro2=float(np.sum(null_error**2)),action_error_fro2=float(np.sum(action_error**2)),
      total_error_fro2=float(np.sum(delta**2)),gap_split_residual=split,frobenius_split_residual=orth)

def population(s):
    k=s['K0'].copy();ks=[];rows=[];maximum_rank_error=0.
    meta=s['spec'];T=s['T']
    for stage in range(T+1):
        q=decomposition(s,k);ks.append(k.copy())
        rows.append(dict(meta,model_id=s['model_id'],stage=stage,T=T,eta=s['eta'],**q))
        if stage==T:break
        f=s['A']-s['B']@k;p=solve_discrete_lyapunov(f.T,np.eye(len(f))+k.T@k);z=-s['B'].T@p@f
        rank_error=float(np.linalg.norm(z-e.trunc(z,2)))/max(1.,float(np.linalg.norm(z)))
        assert rank_error<1e-10;maximum_rank_error=max(maximum_rank_error,rank_error)
        k=k-s['eta']*(k+z)
    null0=s['U'].T@s['K0'];nullT=s['U'].T@k
    expected=(1-s['eta'])**(2*T)*float(np.sum(null0**2));null_error=abs(float(np.sum(nullT**2))-expected)
    assert null_error<1e-9*max(1.,expected)
    return ks,rows,maximum_rank_error,null_error

def summary_rows(rows,model_rows):
    # Each late-window aggregate is made within a run before aggregating32 runs.
    per_run=defaultdict(list)
    for r in rows:
        key=(r['experiment'],r['n'],r['m'],r['null_scale'],r['mode'],r['system'],r['trial'])
        per_run[key].append(r)
    phase_values=defaultdict(list)
    for key,path in per_run.items():
        T=path[0]['T']
        windows={'endpoint':lambda t:t==T,'pre_last_update':lambda t:t==T-1,
                 'last16_updates':lambda t:t>=max(1,T-15),'last_quarter_updates':lambda t:t>3*T//4}
        for phase,predicate in windows.items():
            selected=[r for r in path if predicate(r['stage'])];assert selected
            for metric in METRICS:
                value=quant([r[metric] for r in selected],.5)
                phase_values[key[:5]+(phase,metric)].append(value)
    output=[]
    for key,values in sorted(phase_values.items()):
        assert len(values)==32
        output.append(dict(experiment=key[0],n=key[1],m=key[2],m_minus_r=key[2]-2,null_scale=key[3],mode=key[4],phase=key[5],metric=key[6],
          count=32,independent_systems=8,median=quant(values,.5),q25=quant(values,.25),q75=quant(values,.75),
          late_window_summary='per-run window median, then32-run median/IQR'))
    groups=defaultdict(list)
    for r in model_rows:
        if r['stage']!=r['T']:continue
        for metric in ['total_gap','relative_gap','redundant_D','action_gap','D_over_gap','null_error_fro2','action_error_fro2']:
            groups[(r['experiment'],r['n'],r['m'],r['null_scale'],metric)].append(r[metric])
    pop=[]
    for k,v in sorted(groups.items()):
        assert len(v)==8
        pop.append(dict(experiment=k[0],n=k[1],m=k[2],null_scale=k[3],metric=k[4],physical_models=8,
             median=quant(v,.5),q25=quant(v,.25),q75=quant(v,.75)))
    return output,pop

def paired_endpoints(rows):
    endpoints=[r for r in rows if r['stage']==r['T']]
    lookup={(r['experiment'],r['n'],r['m'],r['null_scale'],r['system'],r['trial'],r['mode']):r for r in endpoints}
    groups=defaultdict(list);pairs=[];random=np.random.default_rng(2026110501)
    for t in endpoints:
        if t['mode']!='truncated':continue
        d=lookup[(t['experiment'],t['n'],t['m'],t['null_scale'],t['system'],t['trial'],'dense')]
        for metric in ['redundant_D','action_gap','total_gap']:
            finite=t[metric]>0 and math.isfinite(t[metric]) and math.isfinite(d[metric])
            r=dict(experiment=t['experiment'],n=t['n'],m=t['m'],null_scale=t['null_scale'],system=t['system'],trial=t['trial'],
              metric=metric,finite_pair=finite,dense_over_truncated=d[metric]/t[metric] if finite else None)
            pairs.append(r);groups[(r['experiment'],r['n'],r['m'],r['null_scale'],metric)].append(r)
    effects=[]
    for k,cell in sorted(groups.items()):
        assert len(cell)==32;systems=sorted({r['system'] for r in cell});seeds=sorted({r['trial'] for r in cell});look={(r['system'],r['trial']):r for r in cell}
        a=np.array([[look[(s,t)]['dense_over_truncated'] if look[(s,t)]['finite_pair'] else np.nan for t in seeds] for s in systems])
        finite=a[np.isfinite(a)];sample=a[random.integers(0,8,size=(2000,8))].reshape(2000,32);good=np.isfinite(sample).any(axis=1)
        boots=np.nanmedian(sample[good],axis=1) if good.any() else []
        effects.append(dict(experiment=k[0],n=k[1],m=k[2],null_scale=k[3],metric=k[4],finite_pairs=len(finite),full_denominator=32,
          paired_ratio_median=quant(finite,.5) if len(finite) else None,bootstrap95_low=quant(boots,.025) if len(boots) else None,
          bootstrap95_high=quant(boots,.975) if len(boots) else None,bootstrap_valid=len(boots),bootstrap_total=2000,independent_systems=8,seed=2026110501))
    return pairs,effects

def figures(stats,pop,dest):
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axs=plt.subplots(1,3,figsize=(12,3.8))
    for ax,metric in zip(axs,['redundant_D','action_gap','D_over_gap']):
        for mode,color in [('dense','#386aab'),('truncated','#cf7735')]:
            cell=sorted([r for r in stats if r['experiment']=='X1' and r['null_scale']==.25 and r['mode']==mode and r['phase']=='endpoint' and r['metric']==metric],key=lambda r:r['m'])
            x=[r['m_minus_r'] for r in cell];ax.plot(x,[r['median'] for r in cell],'o-',color=color,label=mode)
            ax.fill_between(x,[r['q25'] for r in cell],[r['q75'] for r in cell],color=color,alpha=.1)
        ax.set(xlabel='Redundant inputs m-r',ylabel=metric,title='X1 NPG endpoint;32 runs/cell')
        if metric!='D_over_gap':ax.set_yscale('log')
        else:ax.set_ylim(0,1)
        ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
    fig.suptitle('P1: true redundant and action-space costs, per-output fractions; component medians need not add',fontsize=9);emit(fig,dest,'P1_component_gaps')
    fig,axs=plt.subplots(1,2,figsize=(10,3.8))
    for ax,exp in zip(axs,['X1','X2']):
        for mode,color in [('dense','#386aab'),('truncated','#cf7735')]:
            cell=sorted([r for r in stats if r['experiment']==exp and r['null_scale']==.25 and r['phase']=='endpoint' and r['metric']=='relative_gap' and r['mode']==mode],key=lambda r:r['m'])
            x=[r['m_minus_r'] if exp=='X1' else r['n'] for r in cell];ax.plot(x,[r['median'] for r in cell],'o-',color=color,label=mode+' sampled')
            ax.fill_between(x,[r['q25'] for r in cell],[r['q75'] for r in cell],color=color,alpha=.1)
        cell=sorted([r for r in pop if r['experiment']==exp and r['null_scale']==.25 and r['metric']=='relative_gap'],key=lambda r:r['m'])
        x=[r['m']-2 if exp=='X1' else r['n'] for r in cell];ax.plot(x,[r['median'] for r in cell],'k--',label='Exact-gradient reference')
        ax.fill_between(x,[r['q25'] for r in cell],[r['q75'] for r in cell],color='grey',alpha=.12)
        ax.set(yscale='log',xlabel='m-r' if exp=='X1' else 'n=m',ylabel='Relative gap, median/IQR',title=f'{exp}: same frozen eta/T;8 population models,32 sampled runs');ax.legend(frameon=False,fontsize=6);ax.grid(alpha=.2)
    fig.suptitle('P2: optimization reference; sampled-reference difference is not an additive variance decomposition',fontsize=9);emit(fig,dest,'P2_population_vs_sampled')

def main():
    e.require_compute();root=Path(__file__).parent;dest=e.OUT/'analysis-P1-P2-v1';assert not dest.exists();dest.mkdir()
    cfg1=json.loads((root/'configs/X1_actor_base2048_v2.json').read_text());cfg2=json.loads((root/'configs/X2_NPG_formal_v1.json').read_text())
    models={};model_gains={};population_rows=[];observed=[];sources=[];max_rank_error=0.;max_null_error=0.;max_original_error=0.;max_source_D_error=0.;duplicate_matrix_error=0.
    for exp,scope in [('X1','ACTOR'),('X2','NPG')]:
        proof=json.loads((e.OUT/exp/f'FORMAL_{scope}_COMPLETE.json').read_text());assert proof['status']=='COMPLETE' and proof['hard_failure_attempts']==0
        expected_hash=e.sha(root/('configs/X1_actor_base2048_v2.json' if exp=='X1' else 'configs/X2_NPG_formal_v1.json'))
        assert proof['config_sha256']==expected_hash
        for item in proof['items']:
            path=Path(item['path'])
            if path.parent.name!='NPG':continue
            assert item['status']=='COMPLETE' and e.sha(path)==item['json_sha256']
            zp=Path(item['candidate_archive']);assert e.sha(zp)==item['candidate_archive_sha256'];data=json.loads(path.read_text());spec=data['spec']
            n,m,system=spec['n'],spec['m'],spec['system'];null=spec['null_scale'];model_key=(exp,n,m,null,system)
            if exp=='X1':eta,T=cfg1['eta'],len(cfg1['npg_batches'])
            else:
                case=next(c for c in cfg2['cases'] if c['n']==n);eta,T=case['eta'],len(case['npg_batches'])
            with np.load(zp) as z:
                a,b,k0=z['A'],z['B'],z['K0']
                if model_key not in models:
                    meta=dict(experiment=exp,n=n,m=m,r=2,null_scale=null,system=system)
                    s=model(a,b,k0,meta,eta,T,str(len(models)),str(path));popks,poprows,re,ne=population(s)
                    s['population_gains']=popks;s['population_rows']=poprows;models[model_key]=s
                    population_rows.extend(poprows);model_gains['K_population_'+s['model_id']]=popks[-1];model_gains['Kstar_'+s['model_id']]=s['Kstar']
                    max_rank_error=max(max_rank_error,re);max_null_error=max(max_null_error,ne)
                s=models[model_key]
                duplicate=max(float(np.max(abs(s['A']-a))),float(np.max(abs(s['B']-b))),float(np.max(abs(s['K0']-k0))))
                assert duplicate<1e-12;duplicate_matrix_error=max(duplicate_matrix_error,duplicate)
                for record in data['records']:
                    assert record['stable'] and 'assessment_id' in record
                    stage=record['stage'];k=z['K_'+record['assessment_id']];q=decomposition(s,k)
                    error=abs(q['total_gap']-record['gap'])/max(1.,abs(record['gap']));assert error<1e-8;max_original_error=max(max_original_error,error)
                    de=abs(q['redundant_D']-record['redundant_cost']);assert de<1e-8*max(1.,q['redundant_D']);max_source_D_error=max(max_source_D_error,de)
                    pk=s['population_gains'][stage];popq=s['population_rows'][stage];difference=k-pk
                    row=dict(s['spec'],trial=spec['trial'],mode='dense' if record['mode']=='dense' else 'truncated',source_mode=record['mode'],
                      stage=stage,T=T,eta=eta,actual_M=record['transitions'],model_id=s['model_id'],source_json=str(path),assessment_id=record['assessment_id'],**q,
                      population_relative_gap=popq['relative_gap'],learned_minus_population_relative_gap=q['relative_gap']-popq['relative_gap'],
                      null_distance_to_population_fro2=float(np.sum((s['U'].T@difference)**2)),action_distance_to_population_fro2=float(np.sum((s['V'].T@difference)**2)))
                    observed.append(row)
            sources.append(dict(path=str(path),json_sha256=e.sha(path),candidate_archive=str(zp),candidate_archive_sha256=e.sha(zp)))
            if len(sources)%32==0:print(json.dumps(dict(processed_sources=len(sources),iterates=len(observed))),flush=True)
    assert len(models)==88 and len(observed)==86720 and len(sources)==352
    writecsv(dest/'all_saved_iterate_decompositions.csv',observed);writecsv(dest/'population_reference_iterates.csv',population_rows)
    endpoints=[r for r in observed if r['stage']==r['T']];writecsv(dest/'endpoint_decompositions.csv',endpoints)
    stats,pop=summary_rows(observed,population_rows);writecsv(dest/'decomposition_statistics.csv',stats);writecsv(dest/'population_model_statistics.csv',pop)
    popend=[r for r in population_rows if r['stage']==r['T']];writecsv(dest/'population_reference_endpoints.csv',popend)
    pairs,effects=paired_endpoints(observed);writecsv(dest/'paired_endpoint_decomposition.csv',pairs);writecsv(dest/'paired_decomposition_effects.csv',effects)
    matching=[]
    for system in range(101,109):
        for null in [0.,.25]:
            cell=[r for r in popend if r['experiment']=='X1' and r['system']==system and r['null_scale']==null]
            difference=max(r['total_gap'] for r in cell)-min(r['total_gap'] for r in cell);assert difference<1e-8
            matching.append(dict(system=system,null_scale=null,models=len(cell),population_endpoint_gap_range=difference))
    writecsv(dest/'X1_population_matching_check.csv',matching)
    np.savez_compressed(dest/'population_reference_gains.npz',**model_gains);figures(stats,pop,dest)
    report=dict(status='COMPLETE',scope='Review04:05_P1_P2_NPG_MECHANISM',saved_iterates=86720,saved_endpoints=len(endpoints),
      population_physical_models=88,population_reference_iterates=len(population_rows),new_sampled_learning_trajectories=0,new_training_transitions=0,
      max_gap_split_residual=max(r['gap_split_residual'] for r in observed),max_frobenius_split_residual=max(r['frobenius_split_residual'] for r in observed),
      max_original_gap_discrepancy=max_original_error,max_original_D_discrepancy=max_source_D_error,max_duplicate_matrix_error=duplicate_matrix_error,
      max_population_true_rank_truncation_residual=max_rank_error,max_population_null_decay_error=max_null_error,
      original_eta_T_unchanged=True,source_files=sources,source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),job=os.environ['SLURM_JOB_ID'],
      interpretation='Exact-gradient reference measures optimization at the frozen eta/T; sampled-reference deviations may include finite-H bias, truncation effects and noise, not a nonnegative additive variance decomposition.')
    e.save(dest/'REPORT.json',report);print(json.dumps({k:v for k,v in report.items() if k!='source_files'}),flush=True)

if __name__=='__main__':main()
