"""X3 saved-endpoint order envelope and clearly labeled true-B spectral diagnostics."""
import ast,csv,json,math,os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import engine as e
from actor_report import writecsv,emit

def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))

def extend():
    e.require_compute();old=e.OUT/'X3/report-actors';dest=e.OUT/'X3/report-actors-order-envelope-v2'
    assert not dest.exists();dest.mkdir();stats=read(old/'endpoint_statistics.csv');certs=read(old/'system_certificates.csv')
    env=[];tails=[]
    for spectrum in ['smooth','gapped','flat']:
        for multiplier in [1,4,16]:
            for metric in ['gap','relative_gap']:
                cell=[r for r in stats if r['spectrum']==spectrum and int(r['budget_multiplier'])==multiplier and r['metric']==metric]
                assert len(cell)==5
                best=min(cell,key=lambda r:(float(r['median']),int(r['k'])))
                env.append(dict(spectrum=spectrum,budget_multiplier=multiplier,actual_M=int(best['planned_transitions']),metric=metric,
                  best_k=int(best['k']),best_mode=best['mode'],envelope_median=float(best['median']),q25=float(best['q25']),q75=float(best['q75']),
                  stable_count=int(best['stable_count']),denominator=32,diagnostic='Post-hoc envelope of fixed-order group medians, unavailable to learner'))
    for c in certs:
        beta,tau=ast.literal_eval(c['beta']),ast.literal_eval(c['tau2'])
        for k in range(13):
            tails.append(dict(n=12,spectrum=c['spectrum'],system=c['system'],k=k,tau_k_squared=tau[k],beta_k=beta[k],
               quantity='True B spectrum diagnostic; NPG truncates Zhat, these are not every current Z_K tail'))
    writecsv(dest/'fixed_order_median_envelope.csv',env);writecsv(dest/'true_B_spectral_tails.csv',tails)
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    for metric in ['gap','relative_gap']:
        fig,axs=plt.subplots(3,3,figsize=(12,8.8))
        for row,mult in enumerate([1,4,16]):
            for col,sp in enumerate(['smooth','gapped','flat']):
                ax=axs[row,col];cell=sorted([r for r in stats if r['spectrum']==sp and int(r['budget_multiplier'])==mult and r['metric']==metric],key=lambda r:int(r['k']))
                for r in cell:
                    k=int(r['k']);v=float(r['median']);lo,hi=float(r['q25']),float(r['q75'])
                    if math.isfinite(v):
                        if math.isfinite(hi):ax.errorbar(k,v,yerr=[[v-lo],[hi-v]],fmt='o',capsize=3,color='#386aab')
                        else:ax.scatter(k,v,color='#386aab');ax.annotate('upper IQR inf',(k,v),fontsize=5)
                    else:ax.text(k,.5,'inf',transform=ax.get_xaxis_transform(),ha='center',fontsize=6)
                    ax.text(k,.02,r['stable_count']+'/32',transform=ax.get_xaxis_transform(),ha='center',fontsize=6)
                dense=next(r for r in cell if r['mode']=='dense')
                if math.isfinite(float(dense['median'])):ax.axhline(float(dense['median']),ls='--',color='#999999',lw=.8)
                ax.set(yscale='log',xticks=[1,2,4,6,12],xlabel='Retained k (dense=12)',ylabel=metric.replace('_',' '),
                   title=f'{sp}, batch multiplier{mult}\nM={int(cell[0]["planned_transitions"]):,}, same per arm')
                ax.grid(alpha=.2)
        fig.suptitle('X3 NPG fixed-order median/IQR; all failures retained; labels give stable/full32 counts; dashed=dense median',fontsize=9)
        emit(fig,dest,'fixed_order_iqr_'+metric)
    fig,axs=plt.subplots(1,3,figsize=(11,3.4))
    for ax,sp in zip(axs,['smooth','gapped','flat']):
        cell=sorted([r for r in env if r['spectrum']==sp and r['metric']=='gap'],key=lambda r:r['actual_M'])
        ax.step([r['actual_M'] for r in cell],[r['best_k'] for r in cell],where='mid',color='#386aab');ax.scatter([r['actual_M'] for r in cell],[r['best_k'] for r in cell],color='#386aab')
        ax.set(xscale='log',yticks=[1,2,4,6,12],xlabel='Actual transitions M, all overhead counted',ylabel='Best fixed k by group median',title=sp+' (post-hoc diagnostic)');ax.grid(alpha=.2)
    fig.suptitle('X3 NPG fixed-order envelope: actual selected orders shown without monotonic fitting',fontsize=9);emit(fig,dest,'best_fixed_order')
    result=dict(status='COMPLETE',scope='X3_NPG_FIXED_ORDER_ENVELOPE_AND_B_TAIL_DIAGNOSTIC',envelope_rows=len(env),spectral_rows=len(tails),
      source_statistics_sha256=e.sha(old/'endpoint_statistics.csv'),source_report_sha256=e.sha(old/'REPORT.json'),source_sha256=e.sha(__file__),
      new_training_transitions=0,new_learning_runs=0,truth_used_for_evaluation_only=True,
      limitation='True B tail is not every current-policy Z_K tail; no adaptive NPG was run',job=os.environ['SLURM_JOB_ID'])
    e.save(dest/'REPORT.json',result);print(json.dumps(result),flush=True)

