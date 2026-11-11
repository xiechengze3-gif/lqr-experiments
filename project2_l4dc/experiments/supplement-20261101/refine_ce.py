"""Claude C1-C3: saved-data-only refinement in a NEW immutable report folder."""
import csv,json,math,os
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import engine as e

def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def q(values,p):
    s=sorted(values);at=p*(len(s)-1);l,h=math.floor(at),math.ceil(at)
    if l==h or s[l]==s[h]:return s[l]
    return math.inf if math.isinf(s[h]) else s[l]+(at-l)*(s[h]-s[l])
def main():
    e.require_compute();old=e.OUT/'X1/report-ce';dest=e.OUT/'X1/report-ce-v2';assert not dest.exists();dest.mkdir()
    report=json.loads((old/'REPORT.json').read_text())
    for item in report['raw_hashes']:assert e.sha(item['path'])==item['sha256']
    rows=read(old/'all_records.csv');certs=read(old/'system_certificates.csv')
    sensitivity={(r['system'],r['m'],r['null_scale']):float(r['optimal_sensitivity_fro2']) for r in certs}
    normalized=[];groups=defaultdict(list)
    for r in rows:
        v=sensitivity[(r['system'],r['m'],r['null_scale'])];assert v>0
        stable=r['stable']=='True';value=int(r['N'])*float(r['redundant_cost'])/v if stable else math.inf
        item=dict(r,v_star=v,N_D_over_v_star=value);normalized.append(item)
        groups[(float(r['null_scale']),int(r['m']),int(r['N']),r['mode'])].append(item)
    stats=[]
    for key,cell in sorted(groups.items()):
        assert len(cell)==32;values=[r['N_D_over_v_star'] for r in cell]
        stats.append(dict(null_scale=key[0],m=key[1],m_minus_r=key[1]-2,N=key[2],mode=key[3],count=32,
          failures=sum(r['stable']=='False' for r in cell),median=q(values,.5),q25=q(values,.25),q75=q(values,.75)))
    write(dest/'normalized_records.csv',normalized);write(dest/'normalized_statistics.csv',stats)
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    colors={'dense':'#456ea7','truncated':'#d57538'}
    artifacts=[]
    for N in [4096,8192]:
        fig,axs=plt.subplots(1,2,figsize=(10,3.7))
        for ax,null in zip(axs,[.25,0.]):
            counts=[]
            for mode in colors:
                cell=sorted([r for r in stats if r['null_scale']==null and r['N']==N and r['mode']==mode],key=lambda r:r['m'])
                x=[r['m_minus_r'] for r in cell];y=[r['median'] if math.isfinite(r['median']) else np.nan for r in cell]
                ax.plot(x,y,'o-',color=colors[mode],label=mode)
                finite=[i for i,r in enumerate(cell) if math.isfinite(r['q25']) and math.isfinite(r['q75'])]
                if finite:ax.fill_between([x[i] for i in finite],[cell[i]['q25'] for i in finite],[cell[i]['q75'] for i in finite],color=colors[mode],alpha=.12)
                counts.append(f"{mode} {sum(r['failures'] for r in cell)}/{32*len(cell)}")
                for xx,yy,r in zip(x,y,cell):
                    if r['failures']:ax.annotate(f"{r['failures']}/32 failed",(xx,yy),fontsize=6,xytext=(0,7),textcoords='offset points')
            ax.set(title=f"null={null}, N={N}, total={N+512}\nFailed outputs: "+'; '.join(counts),xlabel='Redundant inputs m-r',ylabel=r'Per-output $ND/v_\star$, median/IQR')
            ax.legend(frameon=False,fontsize=7);ax.grid(alpha=.2)
        fig.suptitle('Theorem-normalized CE: v*=||P*F*||_F^2; 8 independent systems x4 seeds per cell',fontsize=10)
        fig.tight_layout()
        for ext in ['png','svg']:
            p=dest/f'normalized_N{N}.{ext}';fig.savefig(p,dpi=180,bbox_inches='tight');artifacts.append(str(p))
        plt.close(fig)
    raw=read(old/'all_statistics.csv');fig,axs=plt.subplots(1,3,figsize=(12,3.7))
    modes={'dense':'#456ea7','truncated':'#d57538','oracle_true_space_diagnostic':'#5a9762'}
    for ax,metric in zip(axs,['gap','relative_gap','redundant_cost']):
        counts=[]
        for mode,color in modes.items():
            selected=sorted([r for r in raw if float(r['null_scale'])==.25 and r['N']=='8192' and r['mode']==mode and r['metric']==metric],key=lambda r:int(r['m']))
            x=[int(r['m'])-2 for r in selected];y=[float(r['median']) for r in selected]
            ax.plot(x,y,'o-',color=color,label=mode.replace('oracle_true_space_diagnostic','oracle diagnostic'))
            ax.fill_between(x,[float(r['q25']) for r in selected],[float(r['q75']) for r in selected],color=color,alpha=.08)
            counts.append(sum(int(r['failures']) for r in selected))
        ax.set(title=f'N=8192, total=8704; failures {sum(counts)}/384\nEach method x m cell: 0/32',xlabel='Redundant inputs m-r (>0 matched family)',ylabel=metric)
        if metric!='redundant_cost':ax.set_yscale('log')
        ax.grid(alpha=.2)
    axs[0].legend(fontsize=6,frameon=False);fig.suptitle('X1 CE main point: median/IQR; zero-null control shown in normalized supplementary panels',fontsize=10);fig.tight_layout()
    for ext in ['png','svg']:
        p=dest/('ce_main_v2.'+ext);fig.savefig(p,dpi=180,bbox_inches='tight');artifacts.append(str(p))
    plt.close(fig)
    e.save(dest/'REPORT.json',dict(status='COMPLETE',scope='X1_CE_POSTPROCESS_C1_C2_C3',old_report_unchanged=True,
       source_report_sha256=e.sha(old/'REPORT.json'),per_output_normalization=True,outputs=len(rows),unstable_outputs=15,
       source_report=str(old/'REPORT.json'),artifacts=artifacts,new_training_transitions=0,new_learning_runs=0,
       source_sha256=e.sha(__file__),job=os.environ['SLURM_JOB_ID']))
    print(json.dumps({'status':'COMPLETE','folder':str(dest),'outputs':len(rows),'new_learning_runs':0}))

if __name__=='__main__':main()
