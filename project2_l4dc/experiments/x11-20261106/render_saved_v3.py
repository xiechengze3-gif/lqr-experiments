"""Layout-only PNG/SVG rendering from completed CSVs; no statistics/training."""
import csv,hashlib,json,os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent;SOURCE=R/'report-v2';OUT=R/'figures-v3';OUT.mkdir()
def read(name):
    with (SOURCE/name).open(newline='') as f:return list(csv.DictReader(f))
cost=read('merged_X6a_sample_cost_derived.csv');ratios=read('paired_gap_ratios_by_N.csv')
for rows in [cost,ratios]:
    for r in rows:
        for key in ['n','m']:r[key]=int(r[key])
plt.rcParams.update({'font.size':10,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
for ax,filter_,key,title in [(axes[0],lambda x:x['n']==48,'m','Fixed state dimension n=48'),(axes[1],lambda x:x['m']==16,'n','Fixed input dimension m=16')]:
    rows=sorted([r for r in cost if filter_(r)],key=lambda r:r[key]);ticks=[r[key] for r in rows]
    for arm,color in [('dense','#b45309'),('truncated','#0369a1')]:
        ax.plot(ticks,[float(r[arm+'_N_req']) for r in rows],'-o',label=arm,color=color)
    ax.set(xlabel='Input dimension m' if key=='m' else 'State dimension n',ylabel='Regression samples for absolute gap 0.01',yscale='log',title=title)
    ax.set_xticks(ticks);ax.grid(alpha=.2);ax.legend();ax.set_yticks([3000,5000,10000,20000,50000,100000]);ax.set_yticklabels(['3k','5k','10k','20k','50k','100k'])
    values=[float(r[a+'_N_req']) for r in rows for a in ['dense','truncated']];ax.set_ylim(min(values)/1.15,max(values)*1.3)
fig.savefig(OUT/'sample_cost.png',dpi=180);fig.savefig(OUT/'sample_cost.svg');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
for ax,filter_,key,title in [(axes[0],lambda x:x['n']==48,'m','n=48: paired gap ratios'),(axes[1],lambda x:x['m']==16,'n','m=16: paired gap ratios')]:
    subset=[r for r in ratios if filter_(r) and r['ratio_kind']=='failure_inclusive']
    for v in sorted({r[key] for r in subset}):
        rows=sorted([r for r in subset if r[key]==v],key=lambda r:float(r['N']))
        ax.plot([float(r['N']) for r in rows],[float(r['median']) for r in rows],'-o',markersize=3,label=f'{key}={v}')
    ax.axhline(1,color='gray',lw=1);ax.set(xscale='log',yscale='log',xlabel='Regression samples N',ylabel='Paired dense / rank-2 gap ratio',title=title)
    ax.grid(alpha=.2);ax.legend(ncol=4 if key=='m' else 3,fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.19),frameon=False)
fig.savefig(OUT/'paired_gap_ratios.png',dpi=180);fig.savefig(OUT/'paired_gap_ratios.svg');plt.close(fig)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with (OUT/'RENDER_RECEIPT.json').open('x') as f:json.dump(dict(status='LAYOUT_ONLY_NO_STATS_NO_TRAINING',new_training_transitions=0,numerical_reanalysis=False,Grace_SU=0,
    source_csv_hashes={name:sha(SOURCE/name) for name in ['merged_X6a_sample_cost_derived.csv','paired_gap_ratios_by_N.csv']},
    files={p.name:sha(p) for p in OUT.iterdir() if p.is_file()},source_sha256=sha(Path(__file__))),f,indent=2)
print(json.dumps(dict(status='LAYOUT_ONLY_COMPLETE',figures=2,Grace_SU=0)))
