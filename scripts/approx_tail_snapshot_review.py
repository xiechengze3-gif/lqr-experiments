"""Gate, audit, threshold measurements, and figures; Grace compute nodes only."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
from dense_scaling import require_compute, atomic_json


ALGORITHMS = ('CE','LSPI','NPG')
COLORS = {'raw':'#b43b39','truncated':'#1769aa'}
RANKS = (1,2,4,8,16)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(path, rows):
    with Path(path).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def short(value):
    return f'{value/1e9:.2f}B' if value >= 1e9 else f'{value/1e6:.2f}M' if value >= 1e6 else f'{value/1e3:.0f}k'


def gate(manifest, root):
    cfg=json.loads(Path(manifest).read_text()); root=Path(root)
    verification=json.loads((root/'verification.json').read_text())
    assert verification['status']=='PASS' and verification['manifest_sha256']==sha(manifest)
    checked=[]
    for tid in cfg['smoke_ids']:
        path=root/'npg-smoke'/'raw'/f'task-{tid:03d}.json'
        p=json.loads(path.read_text())
        for method in ('raw','truncated'):
            rows=[r for r in p['records'] if r['method']==method]
            assert rows[-1]['stage']==cfg['smoke_stages'] and rows[-1]['stable'], ('NPG smoke unstable',tid,method)
            checked.append(dict(task_id=tid,algorithm='NPG',method=method,stable=True))
    for profile in ('ce','lspi-32768'):
        tid=cfg['smoke_ids'][2]
        p=json.loads((root/profile/'raw'/f'task-{tid:03d}.json').read_text())
        assert p['manifest_sha256']==sha(manifest)
        for method in ('raw','truncated'):
            rows=[r for r in p['records'] if r['method']==method]
            if profile.startswith('lspi'):
                # Numerical feasibility is the gate; controller failure stays a recorded scientific result.
                assert all(r.get('solver',{}).get('converged',True) for r in rows)
            checked.append(dict(task_id=tid,algorithm=cfg['profiles'][profile]['algorithm'],method=method,
                                stable=rows[-1]['stable']))
    atomic_json(root/'gate.json',dict(status='PASS',checked=checked,manifest_sha256=sha(manifest),
                                   slurm_job_id=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS',smoke_methods=len(checked))))


def main(manifest, root):
    manifest,root=Path(manifest),Path(root)
    cfg=json.loads(manifest.read_text()); out=root/'review'; out.mkdir(exist_ok=True)
    selected=json.loads((root/'snapshot_scope.json').read_text())['selected_complete_profiles']
    cfg['profiles']={k:v for k,v in cfg['profiles'].items() if k in selected}
    digest=sha(manifest)
    release=manifest.parent.parent
    expected=dict(source_sha256=sha(release/'scripts/approx_tail_run.py'),
                  system_sha256=sha(release/'scripts/approx_tail_system.py'),
                  lstd_sha256=sha(release/'scripts/full_lstd.py'),
                  collector_sha256=sha(release/'scripts/npg_batched_collector.py'))
    expected['engine_sha256']=json.loads((root/'verification.json').read_text())['engine_sha256']
    endpoints, missing, audit, references, refcompletion=[],[],[],[],[]
    diag_by_task={}
    for profile,setting in cfg['profiles'].items():
        algorithm=setting['algorithm']
        schedule=setting.get('schedule')
        planned=(None if algorithm=='CE' else sum(cfg['burn']+count if algorithm=='LSPI'
                 else cfg['burn']+(count+1)*cfg['horizon'] for count in schedule))
        for task in cfg['tasks']:
            tid=task['id']; path=root/profile/'raw'/f'task-{tid:03d}.json'
            if not path.exists():
                missing.append(dict(profile=profile,task_id=tid)); continue
            payload=json.loads(path.read_text())
            assert payload['task']==task and payload['manifest_sha256']==digest
            for key,value in expected.items(): assert payload[key]==value,(path,key)
            diag=payload['diagnostics']
            if tid in diag_by_task: assert diag==diag_by_task[tid]
            diag_by_task[tid]=diag
            for method in ('raw','truncated'):
                rows=[r for r in payload['records'] if r['method']==method]
                solver_ok=all(r.get('solver',{}).get('converged',True) for r in rows)
                for row in rows:
                    if algorithm=='CE': budget=row['N']+512
                    else:
                        prefix=schedule[:row['stage']]
                        budget=sum(cfg['burn']+count if algorithm=='LSPI' else
                                   cfg['burn']+(count+1)*cfg['horizon'] for count in prefix)
                    assert row['transitions']==budget
                    if 'solver' in row:
                        assert row['solver']['samples']==row['N']
                        assert row['solver']['coefficients']==2*task['n']*(2*task['n']+1)//2
                        if row['solver']['converged']:
                            assert row['solver']['relative_residual']<=2*cfg['solver_rtol']
                for row in (rows if algorithm=='CE' else rows[-1:]):
                    complete=algorithm=='CE' or row['stage']==len(schedule)
                    endpoints.append(dict(algorithm=algorithm,profile=profile,method=method,
                        cell=task['cell'],n=task['n'],r=task['r'],seed=task['system_seed'],
                        tail_mode=task['tail_mode'],level=task['level'],
                        tail_singular=diag['tail_singular'],tail_energy=diag['tail_energy'],
                        relative_tail=diag['relative_tail'],N=row['N'],
                        actual_samples=row['transitions'],samples=row['N']+512 if algorithm=='CE' else planned,
                        gap=row['gap'],stable=row['stable'],complete=complete,solver_ok=solver_ok,
                        eligible=bool(complete and row['stable'] and solver_ok),failure=row.get('failure','')))
                audit.append(dict(profile=profile,task_id=tid,method=method,
                    actual_samples=rows[-1]['transitions'],solver_ok=solver_ok,complete=complete,
                    stable=rows[-1]['stable']))
    for task in cfg['tasks']:
        path=root/'reference'/f"task-{task['id']:03d}.json"
        if not path.exists():
            missing.append(dict(profile='reference',task_id=task['id']));continue
        p=json.loads(path.read_text()); assert p['task']==task and p['manifest_sha256']==digest
        for key,value in expected.items():assert p[key]==value
        diag=p['diagnostics']
        for row in p['records']:
            references.append(dict(cell=task['cell'],n=task['n'],r=task['r'],seed=task['system_seed'],
                                   tail_mode=task['tail_mode'],level=task['level'],**row))
        for row in p['completion']:
            refcompletion.append(dict(cell=task['cell'],n=task['n'],r=task['r'],seed=task['system_seed'],
                tail_mode=task['tail_mode'],level=task['level'],tail_singular=diag['tail_singular'],
                tail_energy=diag['tail_energy'],relative_tail=diag['relative_tail'],**row))
    atomic_json(out/'coverage.json',dict(missing=missing,endpoints=len(endpoints),
                                       method_groups=len(audit),reference_systems=len(cfg['tasks'])))
    if missing: raise RuntimeError(f'{len(missing)} missing outputs: no complete report')
    shared={}
    for task in cfg['tasks']:
        d=diag_by_task[task['id']]
        matrices={k:v for k,v in d['matrix_sha256'].items() if k!='B'}
        key=(task['n'],task['system_seed'])
        if key in shared:assert shared[key]==matrices
        shared[key]=matrices
    thresholds=[]
    for algorithm,method,cell in sorted({(e['algorithm'],e['method'],e['cell']) for e in endpoints}):
        rows=[e for e in endpoints if (e['algorithm'],e['method'],e['cell'])==(algorithm,method,cell)]
        budgets=sorted({e['samples'] for e in rows})
        for epsilon in cfg['tolerances']:
            success=[]
            for budget in budgets:
                group=[e for e in rows if e['samples']==budget]
                assert len(group)==2 and {e['seed'] for e in group}=={0,1}
                success.append(all(e['eligible'] and e['gap']<=epsilon for e in group))
            at=next((i for i in range(len(budgets)) if all(success[i:])),None)
            thresholds.append(dict(algorithm=algorithm,method=method,cell=cell,n=rows[0]['n'],r=rows[0]['r'],
                tail_mode=rows[0]['tail_mode'],level=rows[0]['level'],epsilon=epsilon,
                budget=None if at is None else budgets[at],
                status='right_censored' if at is None else 'left_censored' if at==0 else 'attained',
                lower_budget=budgets[-1] if at is None else 0 if at==0 else budgets[at-1],
                tested_budgets=budgets,success_by_budget=success))
    paired=[]
    for algorithm,cell,budget in sorted({(e['algorithm'],e['cell'],e['samples']) for e in endpoints}):
        row=dict(algorithm=algorithm,cell=cell,samples=budget)
        for method in COLORS:
            group=[e for e in endpoints if (e['algorithm'],e['cell'],e['samples'],e['method'])==
                   (algorithm,cell,budget,method)]
            assert len(group)==2
            row[f'{method}_eligible']=all(e['eligible'] for e in group)
            row[f'{method}_gap']=float(np.mean([e['gap'] for e in group])) if row[f'{method}_eligible'] else None
        row['error_gain']=row['raw_gap']/row['truncated_gap'] if (row['raw_eligible'] and
            row['truncated_eligible'] and row['truncated_gap']>0) else None
        paired.append(row)
    plook={(p['algorithm'],p['cell'],p['samples']):p for p in paired}
    tlook={(t['algorithm'],t['method'],t['cell'],t['epsilon']):t for t in thresholds}
    full_rank_checks=[]
    for profile in cfg['profiles']:
        for task in cfg['tasks']:
            if task['r']!=task['n']: continue
            p=json.loads((root/profile/'raw'/f"task-{task['id']:03d}.json").read_text())
            raw=[r for r in p['records'] if r['method']=='raw']
            tr=[r for r in p['records'] if r['method']=='truncated']
            assert len(raw)==len(tr), ('full-rank arm length differs',profile,task['id'])
            differences=[]
            for a,b in zip(raw,tr):
                assert a['stable']==b['stable'] and a['transitions']==b['transitions']
                if a['gap'] is not None and b['gap'] is not None:
                    assert abs(a['gap']-b['gap']) <= 2e-6*max(1.,abs(a['gap']),abs(b['gap']))
                    differences.append(abs(a['gap']-b['gap']))
            full_rank_checks.append(dict(profile=profile,task_id=task['id'],
                                         max_gap_difference=max(differences,default=0)))
    fits=[]
    for algorithm in ALGORITHMS:
        for method in COLORS:
            for epsilon in cfg['tolerances']:
                candidates=[t for t in thresholds if t['algorithm']==algorithm and t['method']==method
                            and t['epsilon']==epsilon and t['tail_mode']=='exact' and t['r']/t['n']<=.2]
                good=[t for t in candidates if t['status']=='attained']
                fit=dict(algorithm=algorithm,method=method,epsilon=epsilon,
                         eligible_cells=len(candidates),fitted_cells=len(good))
                if len({t['n'] for t in good})>=3 and len({t['r'] for t in good})>=3:
                    x=np.array([[1,np.log(t['n']),np.log(t['r'])] for t in good])
                    y=np.log([t['budget'] for t in good])
                    if np.linalg.matrix_rank(x)==3:
                        coef=np.linalg.lstsq(x,y,rcond=None)[0]
                        fit.update(C=float(np.exp(coef[0])),alpha_n=float(coef[1]),beta_r=float(coef[2]))
                fits.append(fit)
    write_csv(out/'endpoints.csv',endpoints); write_csv(out/'same_budget.csv',paired)
    # List-valued columns are unambiguous in JSON; scalar threshold columns in CSV.
    write_csv(out/'samples_to_precision.csv',[{k:v for k,v in t.items()
               if k not in ('tested_budgets','success_by_budget')} for t in thresholds])
    atomic_json(out/'population_references.json',dict(records=references,completion=refcompletion))
    atomic_json(out/'numerical_audit.json',dict(status='PASS',coverage='complete',methods_checked=len(audit),
        shared_matrices_bitwise_identical=True,full_rank_equivalence=full_rank_checks,
        solver_failures=sum(not a['solver_ok'] for a in audit),
        infrastructure_missing=missing,manifest_sha256=digest,source_sha256=expected,
        engine_sha256=next(json.loads((root/profile/'raw'/'task-000.json').read_text())['engine_sha256']
                            for profile in cfg['profiles']),slurm_job_id=os.environ['SLURM_JOB_ID']))
    atomic_json(out/'summary.json',dict(status='snapshot_complete',complete_tasks=len(cfg['tasks'])*len(cfg['profiles']),
        sampled_method_groups=len(audit),thresholds=thresholds,fits=fits,
        stable_method_groups=sum(a['stable'] and a['complete'] for a in audit),
        failures=[e for e in endpoints if not e['eligible']],
        reference_unconverged=[r for r in refcompletion if not r['converged']],
        caveat='Two systems per cell. Discrete measured thresholds, censored values are not exact sample requirements. '
               'All failure outputs retained. Different system version from historical data. '
               'Finite-iteration error and algorithm-specific population bias distinguished; no universal rn^2 law assumed.'))
    plt.rcParams.update({'font.size':10,'axes.titlesize':12,'savefig.facecolor':'white'})
    budgetmax={a:max(e['samples'] for e in endpoints if e['algorithm']==a) for a in ALGORITHMS}
    cells={(t['n'],t['r'],t['tail_mode'],t['level']):t['cell'] for t in cfg['tasks']}

    def cell_for(n,r,family,level):
        return cells[(n,r,'exact' if level==0 else family,level)]

    def save(fig,name):
        fig.savefig(out/f'{name}.png',dpi=180,bbox_inches='tight')
        fig.savefig(out/f'{name}.pdf',bbox_inches='tight'); plt.close(fig)

    for family,levels,label in (('singular',[0.,.003,.01,.03,.1],'Single tail singular value s'),
                                ('relative',[0.,.01,.03,.05,.1,.3],'Relative Frobenius tail alpha'),
                                ('frobenius',[0.,.1],'Total Frobenius tail tau')):
        fig,axes=plt.subplots(2,3,figsize=(15,7.8))
        for i,n in enumerate((50,100)):
            for j,algorithm in enumerate(ALGORITHMS):
                ax=axes[i,j]; values=np.full((len(levels),5),np.nan)
                for li,level in enumerate(levels):
                    for ri,r in enumerate(RANKS):
                        p=plook[(algorithm,cell_for(n,r,family,level),budgetmax[algorithm])]
                        if p['error_gain'] is not None: values[li,ri]=np.log2(p['error_gain'])
                cmap=plt.get_cmap('RdBu').copy(); cmap.set_bad('#e9e9e9')
                ax.imshow(values,cmap=cmap,norm=TwoSlopeNorm(vmin=-4,vcenter=0,vmax=8),aspect='auto')
                for li,level in enumerate(levels):
                    for ri,r in enumerate(RANKS):
                        p=plook[(algorithm,cell_for(n,r,family,level),budgetmax[algorithm])]
                        gain=p['error_gain']
                        text=(f'{gain:.3g}x' if gain<.01 else f'{gain:.2f}x' if gain<2 else f'{gain:.1f}x') if gain is not None else 'failed'
                        color='white' if np.isfinite(values[li,ri]) and (values[li,ri]>4.5 or values[li,ri]<-2.5) else '#222'
                        ax.text(ri,li,text,ha='center',va='center',fontsize=9,color=color)
                ax.set_xticks(range(5),labels=RANKS); ax.set_yticks(range(len(levels)),labels=[f'{x:g}' for x in levels])
                ax.set(xlabel='Rank r',ylabel=label,title=f'{algorithm}, n={n}, M={budgetmax[algorithm]:,}')
        fig.suptitle('Same-budget error gain: mean raw gap / mean truncated gap',fontsize=15)
        fig.subplots_adjust(top=.88,bottom=.16,hspace=.47,wspace=.33)
        fig.text(.5,.025,'Blue (>1x): truncation helps; red (<1x): truncation hurts. Gray: at least one paired output failed.\n'
                 'Each panel uses the same M for both methods; 2 systems per cell. Algorithm budgets differ.',ha='center')
        save(fig,f'same_budget_{family}_rank')
        for epsilon in (1.,.1):
            fig,axes=plt.subplots(2,3,figsize=(15,7.8))
            for i,n in enumerate((50,100)):
                for j,algorithm in enumerate(ALGORITHMS):
                    ax=axes[i,j]; values=np.full((len(levels),5),np.nan); texts={}
                    for li,level in enumerate(levels):
                        for ri,r in enumerate(RANKS):
                            cell=cell_for(n,r,family,level)
                            raw=tlook[(algorithm,'raw',cell,epsilon)]; tr=tlook[(algorithm,'truncated',cell,epsilon)]
                            if raw['budget'] is not None and tr['budget'] is not None:
                                gain=raw['budget']/tr['budget']; values[li,ri]=np.log2(gain)
                                texts[(li,ri)]=f'{gain:.2f}x'+('*' if 'left_censored' in (raw['status'],tr['status']) else '')
                            elif raw['budget'] is None and tr['budget'] is not None:
                                texts[(li,ri)]=f">{raw['lower_budget']/tr['budget']:.2f}x"
                            elif raw['budget'] is not None:
                                texts[(li,ri)]=f"<{raw['budget']/tr['lower_budget']:.2f}x"
                            else: texts[(li,ri)]='unresolved'
                    cmap=plt.get_cmap('RdBu').copy();cmap.set_bad('#e9e9e9')
                    ax.imshow(values,cmap=cmap,norm=TwoSlopeNorm(vmin=-4,vcenter=0,vmax=8),aspect='auto')
                    for (li,ri),text in texts.items():
                        color='white' if np.isfinite(values[li,ri]) and (values[li,ri]>4.5 or values[li,ri]<-2.5) else '#222'
                        ax.text(ri,li,text,ha='center',va='center',fontsize=8.5,color=color)
                    ax.set_xticks(range(5),labels=RANKS);ax.set_yticks(range(len(levels)),labels=[f'{x:g}' for x in levels])
                    ax.set(xlabel='Rank r',ylabel=label,title=f'{algorithm}, n={n}, gap <= {epsilon:g}')
            fig.suptitle('Same-precision sample saving: raw M / truncated M on the tested grid',fontsize=15)
            fig.subplots_adjust(top=.88,bottom=.17,hspace=.47,wspace=.33)
            fig.text(.5,.025,'> / <: only a tested-range bound; unresolved: neither method attained the target.\n'
                     '* At least one arm already succeeds at the smallest tested budget. Exact counts in CSV/JSON.\n'
                     'All primitive transitions included; 2/2 systems must succeed at this and every higher tested budget.',ha='center')
            save(fig,f'same_precision_{family}_{str(epsilon).replace(".","p")}_rank')
    tailcolors={0.:'#555555',.003:'#8d62b5',.01:'#1769aa',.03:'#d9911e',.1:'#b43b39'}
    for algorithm in ALGORITHMS:
        for n in (50,100):
            fig,axes=plt.subplots(1,3,figsize=(15,4.8))
            for ax,r in zip(axes,(1,4,16)):
                for level in (0.,.01,.03,.1):
                    cell=cell_for(n,r,'singular',level)
                    for method in COLORS:
                        rows=sorted([p for p in paired if p['algorithm']==algorithm and p['cell']==cell],key=lambda p:p['samples'])
                        good=[p for p in rows if p[f'{method}_eligible']]
                        ax.plot([p['samples'] for p in good],[max(1e-12,p[f'{method}_gap']) for p in good],
                                color=tailcolors[level],linestyle='--' if method=='raw' else '-',marker='o',markersize=3,
                                label=f's={level:g}, {method}')
                        for p in rows:
                            if not p[f'{method}_eligible']:
                                ax.scatter(p['samples'],.96 if method=='raw' else .90,marker='x',color=tailcolors[level],
                                           transform=ax.get_xaxis_transform())
                    refs=[x for x in refcompletion if x['algorithm']==algorithm and x['cell']==cell and
                          x['method']=='truncated' and not x['finite_horizon']]
                    if all(x['converged'] and x['final_gap'] is not None for x in refs):
                        floor=float(np.mean([x['final_gap'] for x in refs]))
                        if floor>1e-10: ax.axhline(floor,color=tailcolors[level],linestyle=':',alpha=.6)
                ax.set(xscale='log',yscale='log',xlabel='Total primitive transitions M',ylabel='Mean cost gap',title=f'{algorithm}, n={n}, r={r}')
                if algorithm=='NPG':
                    ticks=sorted({p['samples'] for p in paired if p['algorithm']==algorithm})
                    ax.xaxis.set_major_locator(FixedLocator(ticks))
                    ax.xaxis.set_major_formatter(FuncFormatter(lambda x,pos:short(x)))
                    ax.xaxis.set_minor_locator(NullLocator())
                ax.grid(alpha=.2)
            handles,labels=axes[0].get_legend_handles_labels()
            fig.legend(handles,labels,loc='lower center',ncol=4,fontsize=9,bbox_to_anchor=(.5,.02))
            fig.subplots_adjust(top=.82,bottom=.30,wspace=.29)
            fig.suptitle('Budget sweep: raw dashed, truncated solid; dotted = converged population truncated reference',fontsize=13)
            save(fig,f'{algorithm.lower()}_tail_budget_n{n}')
        fig,axes=plt.subplots(2,3,figsize=(14,7.8))
        for i,n in enumerate((50,100)):
            for j,r in enumerate((1,4,16)):
                ax=axes[i,j]
                for method in COLORS:
                    xx,yy=[],[]
                    for level in cfg['single_tails']:
                        cell=cell_for(n,r,'singular',level)
                        refs=[x for x in refcompletion if x['algorithm']==algorithm and x['cell']==cell and
                              x['method']==method and not x['finite_horizon']]
                        if all(x['converged'] and x['final_gap'] is not None for x in refs):
                            xx.append(level);yy.append(max(1e-12,float(np.mean([x['final_gap'] for x in refs]))))
                    ax.plot([cfg['single_tails'].index(x) for x in xx],yy,color=COLORS[method],marker='o',label=method)
                ax.set(yscale='log',xlabel='Single tail singular value s',ylabel='Population-reference gap',title=f'{algorithm}, n={n}, r={r}')
                ax.set_xticks(range(5),labels=['0','.003','.01','.03','.1']);ax.grid(alpha=.2);ax.legend(fontsize=9)
        fig.suptitle('Algorithm-specific converged references; not a lower bound over all rank-r policies',fontsize=14)
        fig.subplots_adjust(top=.88,bottom=.13,hspace=.45,wspace=.27)
        fig.text(.5,.025,'Only converged references shown. Values <=1e-12 are displayed at 1e-12 (numerical zero).\n'
                 'Tail energy = (n-r) s^2; finite-H and matched-256-update NPG diagnostics remain in JSON.',ha='center')
        save(fig,f'{algorithm.lower()}_population_tail_reference')
    # Explicit rank curves and labels at fixed precision for the exact-rank controls.
    for algorithm in ALGORITHMS:
        fig,axes=plt.subplots(2,2,figsize=(12,8.7))
        for i,epsilon in enumerate((1.,.1)):
            rowvalues=[t['budget'] or t['lower_budget'] for t in thresholds if t['algorithm']==algorithm and
                       t['epsilon']==epsilon and t['tail_mode']=='exact' and t['n'] in (50,100) and t['r'] in RANKS]
            for ax,n in zip(axes[i],(50,100)):
                for method,color in COLORS.items():
                    rows=[tlook[(algorithm,method,cell_for(n,r,'singular',0.),epsilon)] for r in RANKS]
                    offset=-.04 if method=='raw' else .04
                    ax.plot(np.arange(5)+offset,[t['budget'] or np.nan for t in rows],color=color,label=method)
                    for j,t in enumerate(rows):
                        value=t['budget'] or t['lower_budget'];status=t['status']
                        ax.scatter(j+offset,value,color=color,marker='^' if status=='right_censored' else 'v' if status=='left_censored' else 'o')
                        text=('>' if status=='right_censored' else '<=' if status=='left_censored' else '')+short(value)
                        ax.annotate(text,(j+offset,value),xytext=(0,10 if method=='raw' else -18),
                                    textcoords='offset points',ha='center',fontsize=9,color=color)
                ax.set(yscale='log',xlabel='Rank r',ylabel='Minimum tested samples M',title=f'{algorithm}, n={n}, gap <= {epsilon:g}')
                ax.set_xticks(range(5),labels=RANKS);ax.set_xlim(-.6,4.6);ax.set_ylim(min(rowvalues)*.45,max(rowvalues)*2.5)
                ax.grid(alpha=.2);ax.legend(fontsize=9)
        fig.suptitle('Exact-rank controls: measured samples to the SAME precision',fontsize=15)
        fig.subplots_adjust(top=.89,bottom=.14,hspace=.43,wspace=.28)
        fig.text(.5,.025,'Up triangles: target not reached in tested range; down triangles: already reached at smallest budget.\n'
                 '2/2 systems and sustained over higher tested budgets. k=1,000; M=1,000,000; B=1,000,000,000.',ha='center')
        save(fig,f'{algorithm.lower()}_exact_samples_by_rank')
    atomic_json(out/'plot_provenance.json',dict(slurm_job_id=os.environ['SLURM_JOB_ID'],
        source_sha256=sha(__file__),artifacts={p.name:sha(p) for p in out.iterdir()
                                              if p.suffix in ('.png','.pdf','.csv')},
        plot_units='Same-budget error ratios and same-precision sample ratios explicitly separated. '
                   'Single singular tail, relative Frobenius tail, and total Frobenius controls separately labeled.'))
    print(json.dumps(dict(status='complete',method_groups=len(audit),endpoints=len(endpoints),
                          reference_unconverged=sum(not r['converged'] for r in refcompletion))))


if __name__=='__main__':
    require_compute();parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['gate','report']);parser.add_argument('--manifest',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    if args.mode=='gate':gate(args.manifest,args.output)
    else:main(args.manifest,args.output)
