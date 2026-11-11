"""Join completed, audited CE/NPG/PI reports on the exact same frozen systems."""
import argparse
import csv
import os
from pathlib import Path
import platform
import sys
if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
import numpy as np
import scipy
import numba
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import rank_sweep100 as e
from rank_sweep100_report import csv_write,wilson


def run(cfg):
    out=Path(cfg['output']);dest=out/'joined-report';dest.mkdir(exist_ok=True)
    ce=Path(cfg['ce_source']);c=e.read(ce/'report-confirm/summary.json')
    primary=e.read(out/'report-confirm/summary.json')
    assert c['status']==primary['status']=='complete'
    assert e.read(ce/'verification.json')['system_hashes']==cfg['system_artifact_sha256']
    assert all(v['status']=='PASS' for v in primary['audits'].values()) and c['audit']['status']=='PASS'
    with (ce/'report-confirm/success_by_budget.csv').open(encoding='utf-8-sig') as f:ce_rates=list(csv.DictReader(f))
    ce_hash=e.sha(ce/'report-confirm/summary.json');main_hash=e.sha(out/'report-confirm/summary.json')
    oracle=e.read(out/'oracle.json')['records'];rows=[]
    for q in c['requirements']:
        eps=q['relative_target'];n=q['seeds'];assert n==30 and q['initial_gap']==1
        matched=[v for v in ce_rates if int(v['rank'])==q['rank'] and v['method']==q['method'] and float(v['relative_target'])==eps]
        at=next((v for v in matched if q['N_hat_90'] is not None and float(v['transitions'])==q['N_hat_90']),None)
        ci=wilson(q['max_successes'],n);ii=wilson(q['max_instabilities'],n)
        rows.append(dict(algorithm='CE',rank=q['rank'],method=q['method'],initial_gap=1.,relative_target=eps,absolute_target=eps,
            seeds=n,N_hat_90=int(q['N_hat_90']) if q['N_hat_90'] is not None else None,status=q['status'],
            bootstrap95_low=q['bootstrap95_low'],bootstrap95_high=q['bootstrap95_high'],
            bootstrap95_low_censored=q['bootstrap95_low_censored'],bootstrap95_high_censored=q['bootstrap95_high_censored'],
            max_budget=q['max_budget'],success_at_N_hat=float(at['success_rate']) if at else None,
            success_ci95_at_N_hat=[float(at['ci95_low']),float(at['ci95_high'])] if at else None,
            max_success_rate=q['max_successes']/n,max_success_ci95=ci,max_failure_rate=1-q['max_successes']/n,
            instability_rate=q['max_instabilities']/n,instability_ci95=ii,numerical_failures=q['max_numerical_failures'],
            endpoint_gap_median=q['endpoint_gap_median'],oracle_iterations=None,stability_criterion='output policy',source_summary_sha256=ce_hash))
    for q in primary['requirements']:
        kind='exact_npg' if q['route']=='npg' else 'exact_pi'
        iterations=next(v['stage'] for v in oracle if v['rank']==q['rank'] and v['kind']==kind and v['gap']<=q['epsilon'])
        rows.append(dict(algorithm=q['route'].upper(),rank=q['rank'],method=q['method'],initial_gap=1.,relative_target=q['epsilon'],absolute_target=q['epsilon'],
            seeds=q['seeds'],N_hat_90=q['N_hat_epsilon_90'],status=q['status'],
            bootstrap95_low=q['bootstrap95_low'],bootstrap95_high=q['bootstrap95_high'],
            bootstrap95_low_censored=q['bootstrap95_low_censored'],bootstrap95_high_censored=q['bootstrap95_high_censored'],
            max_budget=q['max_budget'],success_at_N_hat=q['success_at_N_hat'],success_ci95_at_N_hat=q['success_ci95_at_N_hat'],
            max_success_rate=q['max_budget_success_rate'],max_success_ci95=q['max_budget_success_ci95'],
            max_failure_rate=q['max_budget_failure_rate'],instability_rate=q['max_budget_instability_rate'],
            instability_ci95=q['max_budget_instability_ci95'],numerical_failures=q['max_budget_numerical_failures'],
            endpoint_gap_median=q['max_budget_gap_median'],oracle_iterations=iterations,
            stability_criterion='whole learning path',source_summary_sha256=main_hash))
    assert len(rows)==60 and all(q['seeds']==30 for q in rows)
    csv_write(dest/'all_algorithms_sample_complexity.csv',rows)
    e.atomic_json(dest/'all_algorithms_summary.json',dict(status='complete',requirements=rows,
        system_hashes=cfg['system_artifact_sha256'],sources={str(ce/'report-confirm/summary.json'):ce_hash,str(out/'report-confirm/summary.json'):main_hash},
        seed_scope='30 formal data seeds per rank and algorithm; pairing is within each algorithm, not across algorithms',
        threshold_scope='First measured budget under each fixed sampling schedule with >=90% empirical success; bootstrap intervals do not optimize schedules or interpolate censored ranks.',
        report_source_sha256=e.sha(Path(__file__)),report_backend='Grace saved-result processing',slurm_job_id=os.environ.get('SLURM_JOB_ID'),
        environment=dict(python=sys.executable,python_version=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,numba=numba.__version__,matplotlib=matplotlib.__version__)))
    plt.rcParams.update({'font.size':9,'axes.grid':True,'grid.alpha':.17})
    fig,axes=plt.subplots(3,2,figsize=(12,11),layout='constrained')
    colors={'dense':'#b94835','truncated':'#176da0'}
    for rowaxes,algorithm in zip(axes,('CE','NPG','PI')):
        for ax,eps in zip(rowaxes,cfg['relative_targets']):
            for method,color in colors.items():
                rr=[q for q in rows if q['algorithm']==algorithm and q['method']==method and q['relative_target']==eps]
                ax.plot([q['rank'] for q in rr],[q['N_hat_90'] if q['N_hat_90'] is not None else np.nan for q in rr],'-o',color=color,label=method)
                for q in rr:
                    if q['N_hat_90'] is None:ax.plot(q['rank'],q['max_budget'],'^',mfc='none',mec=color)
                    elif q['bootstrap95_low'] is not None:
                        upper=q['bootstrap95_high'] if q['bootstrap95_high'] is not None else q['max_budget']
                        ax.vlines(q['rank'],q['bootstrap95_low'],upper,color=color)
                        if q['bootstrap95_high'] is None:ax.annotate('',xy=(q['rank'],upper*1.13),xytext=(q['rank'],upper),arrowprops=dict(arrowstyle='->',color=color))
            reference=next(q for q in rows if q['algorithm']==algorithm and q['method']=='dense' and q['rank']==100 and q['relative_target']==eps)
            if reference['N_hat_90'] is not None:ax.axhline(reference['N_hat_90'],ls=':',color='.4',label='rank100 dense')
            ax.set(yscale='log',xticks=cfg['ranks'],xlabel='Actuation rank',ylabel='Transitions for >=90% empirical success',title=f'{algorithm} | relative = absolute target {eps:g}')
            ax.set_ylim(top=reference['max_budget']*1.3);ax.legend(fontsize=8)
    fig.suptitle('Matched initial gap = 1 | same exact systems and initial policies | 30 formal seeds\nOpen triangles: not reached; arrows: censored bootstrap CI; lines break at censored ranks',fontsize=12)
    for ext in ('png','svg'):fig.savefig(dest/('all_algorithms_sample_complexity.'+ext),dpi=180,facecolor='white')
    plt.close(fig)
    print('Joined CE/NPG/PI report complete',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args();run(e.read(a.manifest))
