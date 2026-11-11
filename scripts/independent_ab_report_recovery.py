"""Retain the frozen scientific audit; render all-failure comparisons explicitly."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('study',choices=['ce','stein']);p.add_argument('phase',choices=['pilot','confirm']);p.add_argument('--release',type=Path,required=True);a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    sys.path[:0]=[str(a.release),str(a.release/'scripts')]
    if os.environ.get('LQR_NUMBA_SITE'):sys.path.append(os.environ['LQR_NUMBA_SITE'])
    name='ce500' if a.study=='ce' else 'stein'
    cfg=json.loads((a.release/'configs'/(name+'_independent_stabilizer_20261022.json')).read_text())
    module=importlib.import_module(name+'_independent_stabilizer')
    identity=module.identity(cfg)
    from threadpoolctl import threadpool_limits
    expected_plot_failure=None
    with threadpool_limits(1):
        try:module.report(cfg,identity,a.phase)
        except ValueError as err:
            if a.study!='stein' or 'no positive values' not in str(err):raise
            expected_plot_failure=str(err)
    if a.study=='stein':
        # The frozen report already independently checked every observed policy
        # before committing these tables. Only its subsequent plotting failed.
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.close('all');dest=Path(cfg['output'])/('report-'+a.phase)
        summary=json.loads((dest/'summary.json').read_text());assert summary['status']=='complete'
        endpoints=summary['endpoints'];fig,axes=plt.subplots(2,len(cfg['dimensions']),figsize=(11,7),squeeze=False,layout='constrained')
        counts=cfg['PI'][a.phase+'_N']
        transitions=[cfg['PI']['updates']*(cfg['burn']+(n+1)*cfg['H']) for n in counts]
        for j,n in enumerate(cfg['dimensions']):
            top,below=axes[:,j]
            for method,color in [('dense','#ad493b'),('known_rank','#1777a4')]:
                medians=[];fractions=[]
                for count in counts:
                    rr=[r for r in endpoints if r['n']==n and r['method']==method and r['N']==count]
                    assert len(rr)==len(cfg[a.phase+'_system_seeds'])
                    values=[r['g'] if r['stable'] else np.inf for r in rr]
                    value=float(np.median(values));medians.append(value if np.isfinite(value) else np.nan)
                    fractions.append(sum(r['stable'] for r in rr)/len(rr))
                top.plot(transitions,medians,'-o',label=method,color=color)
                below.plot(transitions,fractions,'-o',label=method,color=color)
            top.axhline(.1,color='.5',ls=':');top.set(xscale='log',yscale='log',
                xlim=(min(transitions)*.8,max(transitions)*1.2),ylim=(1e-3,10),
                title=f'n={n}, rank=4',ylabel='Median relative control error g')
            if not any(r['stable'] for r in endpoints if r['n']==n):
                top.text(.5,.55,'No stable final policies at these budgets',ha='center',transform=top.transAxes)
            below.set(xscale='log',xlim=(min(transitions)*.8,max(transitions)*1.2),ylim=(-.05,1.05),
                xlabel='Assigned primitive transitions',ylabel='Fraction stable after 6 updates')
            below.legend()
        fig.suptitle('Independent unstable A/B; stability-only K0; frozen six-update Stein PI')
        for ext in ('png','svg'):fig.savefig(dest/('stein_relative_error.'+ext),dpi=170)
        plt.close(fig)
    record=dict(status='PASS',study=a.study,phase=a.phase,plotting_issue=expected_plot_failure,
        numerical_source_unchanged=True,identity=identity,job=os.environ['SLURM_JOB_ID'])
    out=Path(cfg['output']);(out/('report-'+a.phase)/'report_recovery.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',study=a.study,phase=a.phase,plot_recovered=bool(expected_plot_failure))))


if __name__=='__main__':main()
