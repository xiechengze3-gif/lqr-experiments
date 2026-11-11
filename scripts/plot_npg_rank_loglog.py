"""Log-log rank plots and descriptive diagnostics from frozen Grace results."""
import argparse
import csv
import hashlib
import json
import os
import socket
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, ScalarFormatter, NullFormatter


def slope_fit(xs, ys):
    x, y = np.log(xs), np.log(ys)
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (intercept + slope*x)
    spread = np.sum((y-y.mean())**2)
    return dict(slope=float(slope), intercept=float(intercept), points=len(xs),
                r_squared=float(1-np.sum(residual**2)/spread) if spread > 0 else None)


def save(fig, out, name):
    for ext in ('png', 'pdf'):
        fig.savefig(out/f'{name}.{ext}', dpi=190, bbox_inches='tight')
    plt.close(fig)


def main():
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Plotting and numerical diagnostics require a real Slurm allocation')
    p = argparse.ArgumentParser()
    p.add_argument('--result', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    root, out = Path(args.result), Path(args.output)
    report = root/'report'
    summary = json.loads((report/'summary.json').read_text())
    assert summary['status'] == 'complete' and not summary['missing_tasks']
    config = json.loads((root/'source/configs/npg_budget_order.json').read_text())
    rows = summary['minimum_budgets']
    lookup = {(r['r'],r['method'],r['epsilon']):r for r in rows}
    ranks = summary['ranks']
    tolerances = (.5, .25, .125)
    colors = {'raw':'#777777','truncated':'#12699c'}
    plt.rcParams.update({'font.size':11, 'axes.titlesize':12, 'legend.fontsize':8.5})
    out.mkdir(parents=True, exist_ok=True)
    fits, allocations = [], []
    fig, axes = plt.subplots(1,3,figsize=(14.8,5.0),sharey=True)
    for ax, eps in zip(axes,tolerances):
        for method in ('raw','truncated'):
            selected = [lookup[r,method,eps] for r in ranks]
            good = [r for r in selected if r['minimum_budget'] is not None]
            ax.plot([r['r'] for r in good], [r['minimum_budget']/1e6 for r in good],
                    'o-', color=colors[method], label=method, linewidth=2, zorder=4)
            for r in selected:
                if r['right_censored']:
                    ax.plot(r['r'],r['lower_tested_budget']/1e6,'^',
                            color=colors[method],markersize=8,zorder=5)
                if r['left_censored']:
                    ax.plot(r['r'],r['minimum_budget']/1e6,'v',
                            color=colors[method],markersize=8,zorder=5)
            for r in good:
                for schedule in r['attaining_schedule_ids']:
                    counts = config['schedules'][schedule]
                    floor = config['profiles'][schedule]['minimum_batch']
                    baseline = len(counts)*(config['burn']+config['horizon'])
                    floor_samples = len(counts)*floor*config['horizon']
                    excess = sum((n-floor)*config['horizon'] for n in counts)
                    assert baseline+floor_samples+excess == r['minimum_budget']
                    allocations.append(dict(r=r['r'],method=method,epsilon=eps,
                        schedule_id=schedule,total=r['minimum_budget'],burn_and_baseline=baseline,
                        minimum_floor_component=floor_samples,above_floor_component=excess,
                        floor_fraction=floor_samples/r['minimum_budget']))
        uncensored = [lookup[r,'truncated',eps] for r in ranks if r<=16
                      and not lookup[r,'truncated',eps]['left_censored']
                      and not lookup[r,'truncated',eps]['right_censored']]
        fit = slope_fit([r['r'] for r in uncensored],[r['minimum_budget'] for r in uncensored])
        original = next(f for f in summary['descriptive_fits']
                        if f['axis']=='rank' and f['method']=='truncated' and f['epsilon']==eps)
        assert abs(fit['slope']-original['slope']) < 1e-10
        fits.append(dict(axis='budget_rank',method='truncated',epsilon=eps,**fit))
        x = np.geomspace(1,16,100)
        anchor = lookup[1,'truncated',eps]['minimum_budget']/1e6
        ax.plot(x,anchor*x,':',color='#222222',linewidth=1.6,label='slope 1 guide, anchored at r=1')
        ax.plot(x,np.exp(fit['intercept'])*x**fit['slope']/1e6,'--',color=colors['truncated'],
                linewidth=1.3,label='truncated fit, r<=16')
        ax.axvspan(16,55,color='#eeeeee',alpha=.65,zorder=0)
        if eps == .125:
            ax.text(.03,.82,'Triangles: raw has no passing\nschedule in the tested grid',
                    transform=ax.transAxes,fontsize=8.5,color='#555555')
        ax.set_xscale('log',base=2)
        ax.set_yscale('log')
        ax.set_xticks(ranks,labels=ranks)
        ax.yaxis.set_major_locator(FixedLocator([100,200,500,1000,2000,4000]))
        ax.yaxis.set_major_formatter(ScalarFormatter())
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.set_xlim(.9,55);ax.set_ylim(55,4400)
        ax.grid(which='major',alpha=.22)
        ax.set_xlabel('Rank r (log scale)')
        ax.set_title(f"Absolute cost gap <= {eps:g}\nTruncated fit slope: {fit['slope']:.2f}")
    axes[0].set_ylabel('Total transitions / run (millions, log scale)')
    fig.suptitle('Equal-precision sample budget versus rank: log-log\n'
                 'n=m=50; all four systems must pass; shaded ranks excluded from fits',fontsize=14)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=4,frameon=False)
    fig.tight_layout(rect=(0,.065,1,.87))
    save(fig,out,'budget_rank_loglog')

    fig, ax = plt.subplots(figsize=(8.6,5.3))
    gain_points = []
    for eps, color in ((.5,'#d55e00'),(.25,'#12699c')):
        selected = [r for r in summary['comparisons'] if r['epsilon']==eps]
        assert all(r['grid_ratio'] is not None and not r['raw_left_censored']
                   and not r['truncated_left_censored'] for r in selected)
        ax.plot([r['r'] for r in selected],[r['grid_ratio'] for r in selected],
                'o-',color=color,linewidth=2,label=f'gap <= {eps:g}')
        good = [r for r in selected if r['r']<=16]
        fit = slope_fit([r['r'] for r in good],[r['grid_ratio'] for r in good])
        fits.append(dict(axis='budget_gain_rank',epsilon=eps,**fit))
        gain_points.extend(selected)
    x = np.geomspace(1,50,100)
    ax.plot(x,50/x,'k:',linewidth=1.7,label='50/r heuristic (not a guaranteed ratio)')
    ax.axhline(1,color='#777777',linewidth=1,alpha=.5)
    ax.set_xscale('log',base=2);ax.set_yscale('log')
    ax.set_xticks(ranks,labels=ranks);ax.set_xlim(.9,55);ax.set_ylim(.85,65)
    ax.yaxis.set_major_locator(FixedLocator([1,2,4,8,16,32,50]))
    ax.yaxis.set_major_formatter(ScalarFormatter());ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel('Rank r (log scale)');ax.set_ylabel('Raw budget / truncated budget (log scale)')
    ax.set_title('Measured sample saving versus rank\nEqual precision; same shared schedule grid')
    ax.grid(alpha=.22);ax.legend(loc='upper right')
    fig.tight_layout();save(fig,out,'sample_saving_rank_loglog')

    # Existing critic diagnostics at the SAME large allocation, not new simulations.
    # Average the last epoch within each system before displaying the four-system range.
    critic = defaultdict(lambda:defaultdict(list))
    with (report/'records.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            if r['schedule_id']=='min-32768-final-2097152' and 241<=int(r['stage'])<=256:
                assert r['observed']=='True' and r['stable']=='True'
                key = (int(r['r']),r['method'],int(r['system_seed']))
                for field in ('critic_error_fro2','horizon_bias_fro2','gram_condition','gap'):
                    critic[key][field].append(float(r[field]))
    critic_summary = []
    for rank in ranks:
        for method in ('raw','truncated'):
            d = dict(r=rank,method=method,stages=[241,256],systems=4,
                     schedule_id='min-32768-final-2097152')
            for field in ('critic_error_fro2','horizon_bias_fro2','gram_condition','gap'):
                by_system = []
                for seed in range(4):
                    values = critic[rank,method,seed][field]
                    assert len(values)==16
                    by_system.append(float(np.mean(values)))
                d[field] = dict(mean=float(np.mean(by_system)),minimum=min(by_system),
                                maximum=max(by_system),by_system=by_system)
            critic_summary.append(d)
    for method in ('raw','truncated'):
        selected = [r for r in critic_summary if r['method']==method and r['r']<=16]
        fits.append(dict(axis='same_allocation_last_epoch_critic_fro2_rank',method=method,
                         **slope_fit([r['r'] for r in selected],
                                     [r['critic_error_fro2']['mean'] for r in selected])))
    diagnostics = dict(status='PASS',job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256={name:hashlib.sha256((report/name).read_bytes()).hexdigest()
                      for name in ('summary.json','records.csv')},
        config_sha256=hashlib.sha256((root/'source/configs/npg_budget_order.json').read_bytes()).hexdigest(),
        fits=fits,gain_points=gain_points,attaining_allocations=allocations,
        same_allocation_last_epoch=critic_summary,
        caveats=['Descriptive finite-grid plots; no new simulations or asymptotic guarantees.',
                 'Minimum-floor component is useful sampling, not entirely wasted overhead.',
                 'Critic Frobenius squared errors include bias; policies differ across rank/method.',
                 'Last-epoch averages are not 64 independent estimator replications.',
                 '50/r compares a heuristic derived from bounds, not proven actual optimal budgets.'])
    (out/'loglog_diagnostics.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',job_id=diagnostics['job_id'],fits=fits,
                         critic_means=[dict(r=r['r'],method=r['method'],
                                            fro2=r['critic_error_fro2']['mean'])
                                       for r in critic_summary]),indent=2),flush=True)


if __name__=='__main__':
    main()
