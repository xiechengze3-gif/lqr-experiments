"""Saved-gain reconstruction of X3's actual last NPG estimator; zero sampled runs."""
import csv,json,math,os
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import engine as e
from actor_report import writecsv,quant,emit

RANKS=[1,2,4,6,12]
METRICS=['error_fro','error_fro_squared','error_relative_fro','target_rank_bias_fro',
         'distance_to_target_rankk_fro','target_fro','effective_estimate_fro']

def numbers(estimate,target,k):
    norm=lambda v:float(np.linalg.norm(v,'fro'))
    target_k=e.trunc(target,k);den=norm(target);error=norm(estimate-target)
    singular=np.linalg.svd(target,compute_uv=False)
    bias=norm(target_k-target)
    assert abs(bias**2-float(np.sum(singular[k:]**2)))<1e-10*max(1.,den**2)
    return dict(error_fro=error,error_fro_squared=error**2,error_relative_fro=error/den if den>0 else None,
      target_rank_bias_fro=bias,distance_to_target_rankk_fro=norm(estimate-target_k),
      target_fro=den,effective_estimate_fro=norm(estimate))

def algebra_check():
    # Deterministic linear algebra only, no random observations or policy learning.
    k=np.arange(144,dtype=float).reshape(12,12)/200
    z=np.cos(np.arange(144,dtype=float)).reshape(12,12)
    eta=.014930779908372525;maximum=0.
    for rank in RANKS:
        used=e.trunc(z,rank);after=k-eta*(k+used);recovered=(k-after)/eta-k
        error=float(np.linalg.norm(recovered-used));maximum=max(maximum,error)
        assert error<1e-11
    return maximum

def summarize(rows):
    groups=defaultdict(list)
    for r in rows:groups[(r['branch'],r['spectrum'],r['budget_multiplier'],r['k'])].append(r)
    stats=[]
    for key,cell in sorted(groups.items()):
        assert len(cell)==32 and len({(r['system'],r['trial']) for r in cell})==32
        for metric in METRICS:
            values=[r[metric] for r in cell if r['estimator_available'] and r.get(metric) is not None]
            stats.append(dict(branch=key[0],spectrum=key[1],budget_multiplier=key[2],k=key[3],metric=metric,
              full_denominator=32,valid_estimators=len(values),missing_estimators=32-len(values),
              actual_M=cell[0]['planned_transitions'],median=quant(values,.5) if values else None,
              q25=quant(values,.25) if values else None,q75=quant(values,.75) if values else None,
              summary='Conditional on saved final update; valid/full counts explicit'))
    return stats

def ratios(rows):
    lookup={(r['branch'],r['spectrum'],r['budget_multiplier'],r['system'],r['trial'],r['k']):r for r in rows}
    pairs=[];groups=defaultdict(list)
    for r in rows:
        if r['k']==12:continue
        key=(r['branch'],r['spectrum'],r['budget_multiplier'],r['system'],r['trial'])
        d=lookup[key+(12,)]
        valid=bool(r['estimator_available'] and d['estimator_available'] and r['error_fro']>0)
        row=dict(branch=key[0],spectrum=key[1],budget_multiplier=key[2],system=key[3],trial=key[4],k=r['k'],
          finite_pair=valid,dense_over_k_error_fro=d['error_fro']/r['error_fro'] if valid else None)
        pairs.append(row);groups[key[:3]+(r['k'],)].append(row)
    random=np.random.default_rng(2026110601);out=[]
    for key,cell in sorted(groups.items()):
        assert len(cell)==32
        systems=sorted({r['system'] for r in cell});trials=sorted({r['trial'] for r in cell})
        by={(r['system'],r['trial']):r for r in cell}
        v=np.array([[by[(s,t)]['dense_over_k_error_fro'] if by[(s,t)]['finite_pair'] else np.nan for t in trials] for s in systems])
        finite=v[np.isfinite(v)];boot=v[random.integers(0,8,size=(2000,8))].reshape(2000,32)
        good=np.isfinite(boot).any(axis=1);values=np.nanmedian(boot[good],axis=1) if good.any() else []
        out.append(dict(branch=key[0],spectrum=key[1],budget_multiplier=key[2],k=key[3],finite_pairs=len(finite),
          full_denominator=32,paired_error_ratio_median=quant(finite,.5) if len(finite) else None,
          bootstrap95_low=quant(values,.025) if len(values) else None,bootstrap95_high=quant(values,.975) if len(values) else None,
          bootstrap_valid=len(values),bootstrap_total=2000,independent_systems=8,bootstrap_seed=2026110601))
    return pairs,out

def figures(stats,endpoints,dest):
    colors=['#6a7da6','#cf7735','#57976a','#9c6ab0','#354858']
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    for branch in ['own_arm_actual_update','common_dense_policy_and_raw_estimate']:
        fig,axs=plt.subplots(1,3,figsize=(12,3.8))
        for ax,sp in zip(axs,['smooth','gapped','flat']):
            for k,color in zip(RANKS,colors):
                cell=sorted([r for r in stats if r['branch']==branch and r['spectrum']==sp and r['k']==k and r['metric']=='error_fro'],key=lambda r:r['actual_M'])
                good=[r for r in cell if r['median'] is not None and r['median']>0]
                x=[r['actual_M'] for r in good]
                ax.plot(x,[r['median'] for r in good],'o-',color=color,label=f'k{k}')
                ax.fill_between(x,[r['q25'] for r in good],[r['q75'] for r in good],color=color,alpha=.08)
                for r in good:
                    if r['valid_estimators']<32:ax.annotate(str(r['valid_estimators'])+'/32',(r['actual_M'],r['median']),fontsize=6)
            ax.set(xscale='log',yscale='log',xlabel='Planned transitions M per arm',ylabel='Last ||used estimate - Z_K||F',title=sp);ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
        fig.suptitle(branch.replace('_',' ')+'; median/IQR, missing-estimator counts in CSV; no new sampled runs',fontsize=9)
        emit(fig,dest,'last_error_'+branch)
    fig,axs=plt.subplots(1,2,figsize=(10,3.8))
    for ax,metric in zip(axs,['gap','relative_gap']):
        for k,color in zip(RANKS,colors):
            cell=sorted([r for r in endpoints if r['spectrum']=='gapped' and int(r['k'])==k and r['metric']==metric],key=lambda r:int(r['budget_multiplier']))
            finite=[r for r in cell if math.isfinite(float(r['median']))]
            x=[int(r['planned_transitions']) for r in finite]
            ax.plot(x,[float(r['median']) for r in finite],'o-',color=color,label=f'k{k}')
            iq=[r for r in finite if math.isfinite(float(r['q75']))]
            ax.fill_between([int(r['planned_transitions']) for r in iq],[float(r['q25']) for r in iq],[float(r['q75']) for r in iq],color=color,alpha=.08)
            for r in cell:
                if int(r['stable_count'])<32 and math.isfinite(float(r['median'])):ax.annotate(r['stable_count']+'/32',(int(r['planned_transitions']),float(r['median'])),fontsize=6)
        ax.set(xscale='log',yscale='log',xlabel='Transitions M, all overhead counted',ylabel=metric.replace('_',' '),title='Two-level spectrum: actual endpoints');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
    fig.suptitle('X3 two-level endpoint median/IQR; failures +inf, full denominator32; common-fit diagnostic is not a new learner',fontsize=9)
    emit(fig,dest,'two_level_endpoint_gaps')

def run():
    e.require_compute();dest=e.OUT/'X3/report-npg-last-estimator-v1';assert not dest.exists()
    cfgpath=Path(__file__).parent/'configs/X3_NPG_formal_v1.json';cfg=json.loads(cfgpath.read_text())
    proofpath=e.OUT/'X3/FORMAL_NPG_COMPLETE.json';proof=json.loads(proofpath.read_text())
    assert proof['status']=='COMPLETE' and proof['config_sha256']==e.sha(cfgpath)
    assert len(proof['items'])==288 and proof['planned_actor_trajectories']==1440
    synthetic=algebra_check();rows=[];matrices={};rankmax=0.;updatemax=0.;valid_total=0
    for item in proof['items']:
        path=Path(item['path']);assert e.sha(path)==item['json_sha256'];d=json.loads(path.read_text());spec=d['spec']
        archive=Path(item['candidate_archive']);assert e.sha(archive)==item['candidate_archive_sha256']
        case=next(c for c in cfg['cases'] if c['spectrum']==spec['spectrum']);T=case['T'];eta=case['eta']
        with np.load(archive) as gains:
            a,b=gains['A'],gains['B'];n=len(a);R=np.eye(b.shape[1]);assert n==12
            dense_recovered=None;dense_target=None
            for mode,k in [('dense',12),('k1',1),('k2',2),('k4',4),('k6',6)]:
                before=next((r for r in d['records'] if r['mode']==mode and r['stage']==T-1),None)
                after=next((r for r in d['records'] if r['mode']==mode and r['stage']==T),None)
                available=bool(d['status']=='COMPLETE' and before and after and before.get('stable') and 'assessment_id' in before and 'assessment_id' in after)
                endpoint_ok=bool(d['status']=='COMPLETE' and after and after.get('stable'))
                common=dict(spectrum=spec['spectrum'],budget_multiplier=spec['budget_multiplier'],system=spec['system'],trial=spec['trial'],
                  stage=T,behavior_stage=T-1,eta=eta,mode=mode,k=k,planned_transitions=d['planned_transitions_per_arm'],
                  actual_transitions=d['actual_transitions'][mode],source_json=str(path),source_json_sha256=e.sha(path),
                  source_archive_sha256=e.sha(archive),endpoint_stable=endpoint_ok,
                  endpoint_gap=after['gap'] if endpoint_ok else math.inf,
                  endpoint_relative_gap=after['relative_gap'] if endpoint_ok else math.inf)
                row=dict(common,branch='own_arm_actual_update',estimator_available=available,
                  missing_reason='' if available else 'No actual saved final update (failed/partial path); no replay')
                if available:
                    prev=gains['K_'+before['assessment_id']];last=gains['K_'+after['assessment_id']]
                    f=a-b@prev;rho=float(max(abs(np.linalg.eigvals(f))));assert rho<1-1e-10
                    p=solve_discrete_lyapunov(f.T,np.eye(n)+prev.T@prev)
                    target=-b.T@p@f;recovered=(prev-last)/eta-R@prev
                    residual=float(np.linalg.norm(recovered-e.trunc(recovered,k)))/max(1.,float(np.linalg.norm(recovered)))
                    assert residual<1e-9,(str(path),mode,residual);rankmax=max(rankmax,residual)
                    update=float(np.linalg.norm(last-(prev-eta*(R@prev+recovered))))/max(1.,float(np.linalg.norm(last)))
                    assert update<1e-12;updatemax=max(updatemax,update)
                    row.update(behavior_rho=rho,recovered_rank_residual=residual,update_reconstruction_residual=update,**numbers(recovered,target,k))
                    ident=f'{spec["spectrum"]}-b{spec["budget_multiplier"]}-s{spec["system"]}-t{spec["trial"]}-{mode}'
                    matrices[ident+'-used']=recovered;matrices[ident+'-target']=target
                    valid_total+=1
                    if mode=='dense':dense_recovered=recovered;dense_target=target
                rows.append(row)
            for k in RANKS:
                row=dict(spectrum=spec['spectrum'],budget_multiplier=spec['budget_multiplier'],system=spec['system'],trial=spec['trial'],
                  stage=T,behavior_stage=T-1,eta=eta,k=k,mode='offline_k'+str(k),branch='common_dense_policy_and_raw_estimate',
                  planned_transitions=d['planned_transitions_per_arm'],source_json=str(path),source_json_sha256=e.sha(path),
                  source_archive_sha256=e.sha(archive),estimator_available=dense_recovered is not None,
                  missing_reason='' if dense_recovered is not None else 'Dense saved final update unavailable')
                if dense_recovered is not None:row.update(**numbers(e.trunc(dense_recovered,k),dense_target,k))
                rows.append(row)
    assert len(rows)==2880
    dest.mkdir();stats=summarize(rows);pairs,effects=ratios(rows)
    writecsv(dest/'last_stage_per_output.csv',rows);writecsv(dest/'last_estimator_statistics.csv',stats)
    writecsv(dest/'paired_last_error_ratios.csv',pairs);writecsv(dest/'paired_last_error_bootstrap.csv',effects)
    np.savez_compressed(dest/'recovered_effective_estimates_and_targets.npz',**matrices)
    endpointpath=e.OUT/'X3/report-actors/endpoint_statistics.csv'
    with endpointpath.open(newline='') as f:endpoints=list(csv.DictReader(f))
    writecsv(dest/'two_level_endpoint_statistics.csv',[r for r in endpoints if r['spectrum']=='gapped'])
    figures(stats,endpoints,dest)
    result=dict(status='COMPLETE',scope='X3_SAVED_LAST_NPG_ESTIMATOR_MECHANISM',own_arm_planned_updates=1440,
      own_arm_available_final_updates=valid_total,per_output_rows=len(rows),summary_rows=len(stats),bootstrap_effect_rows=len(effects),
      max_recovered_rank_residual=rankmax,max_update_reconstruction_residual=updatemax,synthetic_recovery_max_error=synthetic,
      source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),config_sha256=e.sha(cfgpath),proof_sha256=e.sha(proofpath),
      endpoint_statistics_sha256=e.sha(endpointpath),new_training_transitions=0,new_learning_runs=0,job=os.environ['SLURM_JOB_ID'],
      target_definition='Z_K=-B^T P_K (A-BK), evaluated at each actual K_(T-1)',
      recovery='S_k=(K_(T-1)-K_T)/eta-R K_(T-1); raw Zhat of truncated arms not saved or recoverable',
      limitations=['Own-arm policies differ across k; see separate common-dense-policy/common-estimate branch',
       'No top-2 null/redundant-cost identity for full-rank B',
       'Frobenius errors include finite-H bias, sampling error and truncation; no theorem small-error certification',
       'Conditional estimator-error summaries always include valid/full counts; failed endpoint gaps remain +inf'])
    e.save(dest/'REPORT.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':run()
