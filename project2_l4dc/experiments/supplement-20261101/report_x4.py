"""X4 diagnostic report; whole-system bootstrap preserves seeds and fixed directions."""
import json,math,os
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import engine as e
from actor_report import writecsv,quant,emit

def main():
    e.require_compute();source=e.OUT/'X4/formal/outputs.json';data=json.loads(source.read_text());assert data['status']=='COMPLETE'
    rows=data['records'];assert len(rows)==5760
    dest=e.OUT/'X4/report';assert not dest.exists();dest.mkdir();writecsv(dest/'all_outputs.csv',rows)
    groups=defaultdict(list)
    for r in rows:groups[(r['algorithm'],r['mode'],r['scale'])].append(r)
    stats=[]
    for (alg,mode,scale),cell in sorted(groups.items()):
        assert len(cell)==320 and len({(r['system'],r['trial'],r['direction']) for r in cell})==320
        gaps=[r['gap'] if r['stable'] else math.inf for r in cell]
        normalized=[r['relative_gap_source_normalization'] if r['stable'] else math.inf for r in cell]
        reference=[r for r in cell if r['reference_K0_gap'] is not None]
        relative=[r['relative_gap'] if r['stable'] else math.inf for r in reference]
        stats.append(dict(algorithm=alg,mode=mode,scale=scale,count=320,independent_systems=8,sampling_seeds=4,fixed_directions=10,
          stable_count=sum(r['stable'] for r in cell),source_failed_count=sum(not r['source_endpoint_stable'] for r in cell),
          new_instability_count=sum(r['source_endpoint_stable'] and not r['stable'] for r in cell),
          gap_median=quant(gaps,.5),gap_q25=quant(gaps,.25),gap_q75=quant(gaps,.75),
          relative_source_normalization_median=quant(normalized,.5),relative_source_normalization_q25=quant(normalized,.25),relative_source_normalization_q75=quant(normalized,.75),
          perturbed_K0_reference_defined=len(reference),relative_gap_median_defined_reference=quant(relative,.5) if relative else None,
          relative_gap_q25_defined_reference=quant(relative,.25) if relative else None,relative_gap_q75_defined_reference=quant(relative,.75) if relative else None,
          relative_interpretation='conditional on a stable K0 reference; omitted reference is not a learned-policy failure'))
    writecsv(dest/'robustness_statistics.csv',stats)
    lookup={(r['algorithm'],r['mode'],r['scale'],r['system'],r['trial'],r['direction']):r for r in rows}
    pairgroups=defaultdict(list);pairs=[]
    for t in rows:
        if t['mode']!='truncated':continue
        d=lookup[(t['algorithm'],'dense',t['scale'],t['system'],t['trial'],t['direction'])]
        finite=d['stable'] and t['stable'] and t['gap']>0
        r=dict(algorithm=t['algorithm'],scale=t['scale'],system=t['system'],trial=t['trial'],direction=t['direction'],
          dense_stable=d['stable'],truncated_stable=t['stable'],finite_pair=finite,dense_over_truncated=d['gap']/t['gap'] if finite else None)
        pairs.append(r);pairgroups[(t['algorithm'],t['scale'])].append(r)
    random=np.random.default_rng(2026110499);effects=[]
    for (alg,scale),cell in sorted(pairgroups.items()):
        systems=sorted({r['system'] for r in cell});clusters=[[r for r in cell if r['system']==s] for s in systems]
        assert len(clusters)==8 and all(len(c)==40 for c in clusters)
        values=np.array([[r['dense_over_truncated'] if r['finite_pair'] else np.nan for r in c] for c in clusters])
        finite=values[np.isfinite(values)];sample=values[random.integers(0,8,size=(2000,8))].reshape(2000,320)
        valid=np.isfinite(sample).any(axis=1);boot=np.nanmedian(sample[valid],axis=1) if valid.any() else []
        effects.append(dict(algorithm=alg,scale=scale,finite_pairs=len(finite),full_denominator=320,independent_systems=8,
          paired_ratio_median=quant(finite,.5) if len(finite) else None,bootstrap95_low=quant(boot,.025) if len(boot) else None,
          bootstrap95_high=quant(boot,.975) if len(boot) else None,bootstrap_valid=len(boot),bootstrap_total=2000,bootstrap_seed=2026110499,
          interpretation='same system/seed/direction/perturbation; whole-system bootstrap includes all40 observations per selected cluster'))
    writecsv(dest/'paired_ratios.csv',pairs);writecsv(dest/'paired_bootstrap_effects.csv',effects)
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axs=plt.subplots(2,3,figsize=(12,6))
    for col,alg in enumerate(['CE','NPG','PI']):
        for mode,color in [('dense','#386aab'),('truncated','#cf7735')]:
            cell=sorted([r for r in stats if r['algorithm']==alg and r['mode']==mode],key=lambda r:r['scale']);finite=[r for r in cell if math.isfinite(r['gap_median'])]
            axs[0,col].plot([r['scale'] for r in finite],[r['gap_median'] for r in finite],'o-',color=color,label=mode)
            iqr=[r for r in finite if math.isfinite(r['gap_q75'])]
            axs[0,col].fill_between([r['scale'] for r in iqr],[r['gap_q25'] for r in iqr],[r['gap_q75'] for r in iqr],color=color,alpha=.1)
            axs[1,col].plot([r['scale'] for r in cell],[r['stable_count']/320 for r in cell],'o-',color=color,label=mode)
            for r in cell:axs[1,col].annotate(f"{r['stable_count']}/320",(r['scale'],r['stable_count']/320),xytext=(0,4 if mode=='dense' else -10),textcoords='offset points',fontsize=6)
        axs[0,col].set(yscale='log',ylabel='Perturbed absolute gap, full median/IQR',title=alg+' fixed learned policy')
        axs[1,col].set(ylim=(-.06,1.12),ylabel='Stable fraction (8 independent systems)',xlabel='||DeltaB|| / ||B||',xticks=[.25,.5,1.])
        for ax in axs[:,col]:ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
    fig.suptitle('X4 offline diagnostic: DeltaB V_r=0; 8 systems x4 seeds x10 fixed directions; no retraining',fontsize=9);emit(fig,dest,'fixed_policy_robustness')
    result=dict(status='COMPLETE',scope='OPTIONAL_OFFLINE_DIAGNOSTIC',outputs=5760,
      source_failed_outputs=sum(not r['source_endpoint_stable'] for r in rows),new_instability=sum(r['source_endpoint_stable'] and not r['stable'] for r in rows),
      max_normalized_gap_identity_error=max((r.get('independent_gap_error',0.) for r in rows),default=0.),
      max_null_constraint_error=data['max_orthogonality_error'],max_operator_norm_error=data['max_operator_norm_error'],
      source_outputs_sha256=e.sha(source),source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),
      new_training_transitions=0,retraining=False,job=os.environ['SLURM_JOB_ID'])
    e.save(dest/'REPORT.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
