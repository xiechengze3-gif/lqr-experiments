"""Plot-only QA correction from verified aggregate tables; no learning or control solves."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/ce-npg-arguments-20261028'
RELEASE=BASE/'releases/ce-npg-arguments-20261028'
sys.path[:0]=[str(RELEASE),str(RELEASE/'scripts')]
from dense_scaling import require_compute,atomic_json


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    require_compute();report=OUT/'report'
    old={p.name:sha(p) for p in report.iterdir() if p.is_file() and p.name!='SHA256SUMS'}
    spec=importlib.util.spec_from_file_location('argument_report_v2',OUT/'report-recovery.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    rows=[]
    for row in csv.DictReader((report/'aggregate.csv').open()):
        parsed={}
        for key,value in row.items():
            if value=='':parsed[key]=None
            elif value in ['True','False']:parsed[key]=value=='True'
            else:
                try:parsed[key]=json.loads(value)
                except (ValueError,TypeError):parsed[key]=value
        rows.append(parsed)
    original_save=mod.save
    def reviewed_save(fig,dest,name):
        if name.endswith('figure1_learning_dimension'):
            # Autoscaling ignores NaN costs; preserve the FULL declared scan including failed cells.
            for index in [1,4]:fig.axes[index].set_xlim(10,50);fig.axes[index].set_xticks([12,24,48])
            for index in [2,5]:fig.axes[index].set_xlim(.65,8.35);fig.axes[index].set_xticks([1,2,4,8])
        original_save(fig,dest,name)
    mod.save=reviewed_save
    mod.plt.rcParams.update({'font.size':8.5,'axes.spines.top':False,'axes.spines.right':False})
    mod.figure1(report,rows,'scalar','figure1_learning_dimension')
    mod.figure1(report,rows,'dense','appendix_figure1_learning_dimension')
    fig,axes=mod.plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    for ax,algorithm in zip(axes,['CE','NPG']):
        for mode in ['dense','k2']:
            xs=[];ys=[]
            for spectrum,tail in [('gapped001',.01),('gapped',.05),('gapped02',.2)]:
                group=mod.select(rows,algorithm=algorithm,A_family='scalar',spectrum=spectrum,n=16,mode=mode)
                row=next(r for r in group if (r.get('N')==65536 if algorithm=='CE' else r.get('stage')==48))
                xs.append(14*tail**2);ys.append(mod.finite(row['failure_inclusive_gap_median']))
            ax.plot(xs,ys,'o-',color=mod.COLORS[mode],label=mode)
        mod.style(ax,'Squared Frobenius tail of B at k=2',logx=False)
        ax.set_xscale('log');ax.set_title(algorithm+': fixed k2 tail control');ax.legend()
    mod.save(fig,report,'appendix_tail_strength')
    allowed={stem+ext for stem in ['figure1_learning_dimension','appendix_figure1_learning_dimension','appendix_tail_strength'] for ext in ['.png','.svg']}
    for name,expected in old.items():
        if name not in allowed:assert sha(report/name)==expected,('Numerical data changed',name)
    atomic_json(report/'visual_review.json',dict(status='PASS',kind='plot-only correction',
        source_sha256=sha(Path(__file__)),aggregate_sha256=sha(report/'aggregate.csv'),
        corrected_scan_limits=True,tail_xscale='log',numerical_data_unchanged=True,
        regenerated_files=sorted(allowed),learning_replayed=False))
    hashes={p.name:sha(p) for p in report.iterdir() if p.is_file() and p.name!='SHA256SUMS'}
    (report/'SHA256SUMS').write_text(''.join(h+'  '+p+'\n' for p,h in sorted(hashes.items())),encoding='ascii')
    print(json.dumps(dict(status='PASS',numerical_data_unchanged=True,regenerated_files=sorted(allowed))))


if __name__=='__main__':main()
