"""Portable CSV-only plots. Writes a fresh export directory; never evaluates a policy."""
import argparse,csv,hashlib,json,math,os,shutil,time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
p.add_argument('--output',type=Path)
a=p.parse_args();root=a.root.resolve()
runtime=root/'.runtime/csv-only-plots';temporary=runtime/'tmp';cache=runtime/'matplotlib'
temporary.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
for key in ['TMP','TEMP','TMPDIR']:os.environ[key]=str(temporary)
os.environ['MPLCONFIGDIR']=str(cache)
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='1'
dest=(a.output or root/'exports'/('csv-only-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))).resolve()
assert not dest.exists(),'Choose a fresh output folder; existing results are never overwritten'
assert shutil.disk_usage(root).free>100*1024**2
print(json.dumps(dict(source_root=str(root),actual_output=str(dest),cache=str(cache),temp=str(temporary),
    free_bytes=shutil.disk_usage(root).free,policy_evaluations=0,training_transitions=0)),flush=True)
dest.mkdir(parents=True)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
sources={};figures=[];pending=[]
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()

def read(relative):
    path=root/relative;sources[relative]=sha(path)
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def emit(fig,name):
    fig.tight_layout()
    for ext in ['png','svg']:
        path=dest/(name+'.'+ext);fig.savefig(path,dpi=180,bbox_inches='tight');figures.append(dict(path=str(path),sha256=sha(path)))
    plt.close(fig)
def band(ax,cell,x,color,label):
    finite=[r for r in cell if math.isfinite(float(r['median']))]
    ax.plot([x(r) for r in finite],[float(r['median']) for r in finite],'o-',ms=3,color=color,label=label)
    iqr=[r for r in finite if math.isfinite(float(r['q75']))]
    ax.fill_between([x(r) for r in iqr],[float(r['q25']) for r in iqr],[float(r['q75']) for r in iqr],color=color,alpha=.1)

norm=read('X1/report-ce-v2/normalized_statistics.csv');fig,axs=plt.subplots(2,2,figsize=(10,6))
for row,null in enumerate([.25,0.]):
    for col,N in enumerate([4096,8192]):
        ax=axs[row,col];counts=[]
        for mode,color in [('dense','#386aab'),('truncated','#cf7735')]:
            cell=sorted([r for r in norm if float(r['null_scale'])==null and int(r['N'])==N and r['mode']==mode],key=lambda r:int(r['m']))
            band(ax,cell,lambda r:int(r['m_minus_r']),color,mode)
            for r in cell:
                ax.text(int(r['m_minus_r']),.025 if mode=='dense' else .08,
                        ('d ' if mode=='dense' else 't ')+str(int(r['count'])-int(r['failures']))+'/32',
                        transform=ax.get_xaxis_transform(),ha='center',fontsize=5.5,color=color)
            counts.append(mode+f" {sum(int(r['failures']) for r in cell)}/{32*len(cell)}")
        ax.set(xlabel='Redundant inputs m-r',ylabel='Per-output N D / v_star, median/IQR',title=f'null={null}, N={N}, M={N+512}\nFailures '+', '.join(counts));ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
fig.suptitle('X1 CE theorem normalization; nonzero-null m>r family and separate zero-null control',fontsize=9);emit(fig,'X1_CE_normalized')

ce1=read('X1/report-ce/all_statistics.csv');fig,axs=plt.subplots(2,2,figsize=(10,6))
for row,null in enumerate([.25,0.]):
    for ax,metric in zip(axs[row],['gap','relative_gap']):
        for mode,color in [('dense','#386aab'),('truncated','#cf7735')]:
            cell=sorted([r for r in ce1 if float(r['null_scale'])==null and int(r['N'])==8192 and r['mode']==mode and r['metric']==metric],key=lambda r:int(r['m']))
            assert all(int(r['stable_count'])==32 for r in cell)
            band(ax,cell,lambda r:int(r['m_minus_r']),color,mode)
        ax.set(yscale='log',xlabel='Redundant inputs m-r',ylabel=metric.replace('_',' '),
               title=f'null={null}, N=8192, M=8704\nEach method32/32 stable at every point');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
fig.suptitle('X1 CE endpoint median/IQR; nonzero-null matching uses m>r; true-space oracle stays in diagnostic source tables',fontsize=9);emit(fig,'X1_CE_main_gaps')

ratios=read('X2/report-ce/fixed_budget_ratios.csv');fig,axs=plt.subplots(2,2,figsize=(10,6.6),gridspec_kw={'height_ratios':[4,2]})
for col,metric in enumerate(['absolute_gap_ratio','relative_gap_ratio']):
    ax=axs[0,col];counts=[]
    for nd,color in zip([16,64,256],['#386aab','#cf7735','#57976a']):
        cell=sorted([r for r in ratios if int(r['r'])==2 and float(r['N_over_d'])==nd and r['metric']==metric],key=lambda r:int(r['n']))
        x=[float(r['n_over_r']) for r in cell]
        ax.plot(x,[float(r['paired_ratio_median']) for r in cell],'o-',color=color,label=f'N/d{nd}')
        ax.fill_between(x,[float(r['bootstrap95_low']) for r in cell],[float(r['bootstrap95_high']) for r in cell],color=color,alpha=.1)
        counts.append(['p'+r['finite_pairs']+'/32\nd'+r['dense_stable']+'/32 t'+r['truncated_stable']+'/32' for r in cell])
    ax.set(yscale='log',xticks=[6,12,24,48],xlabel='n/r, r=2',ylabel='Paired dense / rank2 gap',title=metric.replace('_',' '));ax.axhline(1,color='grey',ls='--',lw=.7);ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
    below=axs[1,col];below.axis('off');tab=below.table(cellText=counts,colLabels=['n12','n24','n48','n96'],rowLabels=['N/d16','N/d64','N/d256'],loc='center');tab.auto_set_font_size(False);tab.set_fontsize(7);tab.scale(1,2);below.set_title('p=finite pairs; d/t=dense/truncated stable, each /full32',fontsize=7)
fig.suptitle('X2 CE finite-pair diagnostics, system-bootstrap95%; no fitted scaling law',fontsize=9);emit(fig,'X2_CE_fixed_budget_ratios')

envelope=read('X3/report-ce/fixed_k_envelope.csv');fig,axs=plt.subplots(2,2,figsize=(10,6),gridspec_kw={'height_ratios':[3,1.5]})
for col,n in enumerate([16,32]):
    ax=axs[0,col];below=axs[1,col]
    for sp,color in zip(['smooth','gapped','flat'],['#386aab','#cf7735','#57976a']):
        cell=sorted([r for r in envelope if int(r['n'])==n and r['spectrum']==sp],key=lambda r:int(r['N']))
        ax.step([int(r['N'])/(2*n) for r in cell],[int(r['best_k']) for r in cell],where='mid',color=color,label=sp)
        below.plot([int(r['N'])/(2*n) for r in cell],[(32-int(r['stable_count']))/32 for r in cell],'o-',ms=2,color=color,label=sp)
    ax.set(xscale='log',xlabel='N/(n+m)',ylabel='Best fixed k by group median',title=f'n=m{n}; post-hoc diagnostic');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
    maximum=max((32-int(r['stable_count']))/32 for r in envelope if int(r['n'])==n)
    below.set(xscale='log',ylim=(-.015,max(.1,maximum+.03)),xlabel='N/(n+m)',ylabel='Selected k: failures /32');below.grid(alpha=.2)
fig.suptitle('X3 CE actual fixed-order envelope; no monotonic fitting or online oracle',fontsize=9);emit(fig,'X3_CE_best_fixed_order')

actor=read('X1/report-actors/endpoint_statistics.csv');fig,axs=plt.subplots(2,2,figsize=(10,6))
for row,algorithm in enumerate(['NPG','PI']):
    for col,null in enumerate([0.,.25]):
        ax=axs[row,col]
        for mode,color in [('dense','#386aab'),('truncated','#cf7735')]:
            cell=sorted([r for r in actor if r['algorithm']==algorithm and float(r['null_scale'])==null and r['mode']==mode and r['metric']=='gap'],key=lambda r:int(r['m']))
            ax.plot([int(r['m'])-2 for r in cell],[int(r['failures'])/32 for r in cell],'o-',color=color,label=mode)
        ax.set(ylim=(-.03,1.03),xlabel='m-r',ylabel='Failed endpoints / full32',title=f'{algorithm}, null={null}; fixed M=93,308,928');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
fig.suptitle('X1 actor stability; NPG all stable, PI failures retained in full-denominator tables',fontsize=9);emit(fig,'X1_actor_failure_rates')

stats2=read('X2/report-actors/endpoint_statistics.csv');fig,axs=plt.subplots(1,2,figsize=(10,3.7))
for ax,metric in zip(axs,['gap','relative_gap']):
    for mode,offset,color in [('dense',-.06,'#386aab'),('k2',.06,'#cf7735')]:
        cell=sorted([r for r in stats2 if r['mode']==mode and r['metric']==metric],key=lambda r:int(r['n']))
        y=[float(r['median']) for r in cell]
        ax.errorbar([i+offset for i in range(2)],y,yerr=[[v-float(r['q25']) for v,r in zip(y,cell)],[float(r['q75'])-v for v,r in zip(y,cell)]],fmt='o',capsize=4,color=color,label=mode)
    ax.set(yscale='log',xticks=[0,1],xticklabels=['n12, M=33,602,016','n24, M=542,850,432'],ylabel=metric.replace('_',' '),title='NPG full32 medians/IQR; all stable');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
fig.suptitle('X2 NPG mixed endpoints; paired ratio95% intervals include1 at both dimensions',fontsize=9);emit(fig,'X2_NPG_mixed_endpoints')

mechanism=root/'analysis-P1-P2-v1/REPORT.json'
if mechanism.exists() and json.loads(mechanism.read_text())['status']=='COMPLETE':
    decomp=read('analysis-P1-P2-v1/decomposition_statistics.csv');fig,axs=plt.subplots(1,3,figsize=(12,3.7))
    for ax,metric in zip(axs,['redundant_D','action_gap','D_over_gap']):
        for mode,color in [('dense','#386aab'),('truncated','#cf7735')]:
            cell=sorted([r for r in decomp if r['experiment']=='X1' and float(r['null_scale'])==.25 and r['phase']=='endpoint' and r['mode']==mode and r['metric']==metric],key=lambda r:int(r['m']))
            band(ax,cell,lambda r:int(r['m_minus_r']),color,mode)
        ax.set(xlabel='m-r',ylabel=metric,title='P1 true-cost decomposition;32 runs/cell');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
        if metric!='D_over_gap':ax.set_yscale('log')
        else:ax.set_ylim(0,1)
    fig.suptitle('Saved-policy mechanism: per-output fractions; medians of components need not add',fontsize=9);emit(fig,'P1_NPG_components')

robust=read('X4/report/robustness_statistics.csv');fig,axs=plt.subplots(1,3,figsize=(11,3.7))
for ax,algorithm in zip(axs,['CE','NPG','PI']):
    for mode,color in [('dense','#386aab'),('truncated','#cf7735')]:
        cell=sorted([r for r in robust if r['algorithm']==algorithm and r['mode']==mode],key=lambda r:float(r['scale']))
        ax.plot([float(r['scale']) for r in cell],[int(r['stable_count'])/320 for r in cell],'o-',color=color,label=mode)
    ax.set(ylim=(-.03,1.03),xticks=[.25,.5,1],xlabel='||DeltaB|| / ||B||',ylabel='Stable / full320 evaluations',title=algorithm+' fixed-policy diagnostic');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
fig.suptitle('X4: 8 independent systems x4 seeds x10 fixed directions; inherited source failures retained; zero retraining',fontsize=9);emit(fig,'X4_robustness_stability')

extra='X3/report-actors-order-envelope-v2/fixed_order_median_envelope.csv'
marker=root/'X3/report-actors-order-envelope-v2/REPORT.json'
if marker.exists() and json.loads(marker.read_text())['status']=='COMPLETE':
    rows=read(extra);fig,axs=plt.subplots(1,3,figsize=(11,3.6))
    for ax,sp in zip(axs,['smooth','gapped','flat']):
        cell=sorted([r for r in rows if r['spectrum']==sp and r['metric']=='gap'],key=lambda r:int(r['actual_M']))
        ax.plot([int(r['actual_M']) for r in cell],[int(r['best_k']) for r in cell],'o-')
        ax.set(xscale='log',yticks=[1,2,4,6,12],xlabel='Actual transitions M',ylabel='Best fixed k (diagnostic)',title=sp);ax.grid(alpha=.2)
    fig.suptitle('X3 NPG fixed-order median envelope; all-budget data and stability counts remain in the reports',fontsize=9);emit(fig,'X3_NPG_best_fixed_order')
    nstats=read('X3/report-actors/endpoint_statistics.csv')
    for metric in ['gap','relative_gap']:
        fig,axs=plt.subplots(3,3,figsize=(12,9))
        for row,mult in enumerate([1,4,16]):
            for col,sp in enumerate(['smooth','gapped','flat']):
                ax=axs[row,col]
                cell=sorted([r for r in nstats if r['spectrum']==sp and int(r['budget_multiplier'])==mult and r['metric']==metric],key=lambda r:int(r['k']))
                assert len(cell)==5
                for r in cell:
                    k=int(r['k']);v=float(r['median']);lo,hi=float(r['q25']),float(r['q75'])
                    if math.isfinite(v):
                        if math.isfinite(hi):ax.errorbar(k,v,yerr=[[v-lo],[hi-v]],fmt='o',capsize=3,color='#386aab')
                        else:ax.scatter(k,v,color='#386aab');ax.annotate('upper IQR inf',(k,v),fontsize=5)
                    else:ax.text(k,.5,'inf',transform=ax.get_xaxis_transform(),ha='center',fontsize=6)
                    ax.text(k,.02,r['stable_count']+'/32',transform=ax.get_xaxis_transform(),ha='center',fontsize=6)
                actual_equal=all(r['actual_transitions_min']==r['planned_transitions']==r['actual_transitions_max'] for r in cell)
                ax.set(yscale='log',xticks=[1,2,4,6,12],xlabel='Retained k; dense=12',ylabel=metric.replace('_',' '),
                    title=f'{sp}, multiplier{mult}\n'+('Actual M=' if actual_equal else 'Planned M=')+f'{int(cell[0]["planned_transitions"]):,}');ax.grid(alpha=.2)
        fig.suptitle('X3 NPG full32 medians/IQR; all failed outputs +inf; point labels stable/full32',fontsize=9);emit(fig,'X3_NPG_full_order_'+metric)
    last_marker=root/'X3/report-npg-last-estimator-v1/REPORT.json'
    if last_marker.exists() and json.loads(last_marker.read_text())['status']=='COMPLETE':
        errors=read('X3/report-npg-last-estimator-v1/last_estimator_statistics.csv')
        for branch in ['own_arm_actual_update','common_dense_policy_and_raw_estimate']:
            fig,axs=plt.subplots(1,3,figsize=(12,3.8))
            for ax,sp in zip(axs,['smooth','gapped','flat']):
                for k,color in zip([1,2,4,6,12],['#6a7da6','#cf7735','#57976a','#9c6ab0','#354858']):
                    cell=sorted([r for r in errors if r['branch']==branch and r['spectrum']==sp and int(r['k'])==k and r['metric']=='error_fro'],key=lambda r:int(r['actual_M']))
                    good=[r for r in cell if r['median'] and math.isfinite(float(r['median'])) and float(r['median'])>0]
                    ax.plot([int(r['actual_M']) for r in good],[float(r['median']) for r in good],'o-',color=color,label=f'k{k}')
                    ax.fill_between([int(r['actual_M']) for r in good],[float(r['q25']) for r in good],[float(r['q75']) for r in good],color=color,alpha=.08)
                    for r in good:
                        if int(r['valid_estimators'])<32:ax.annotate(r['valid_estimators']+'/32',(int(r['actual_M']),float(r['median'])),fontsize=6)
                ax.set(xscale='log',yscale='log',xlabel='Planned M per arm',ylabel='Last Frobenius estimator error',title=sp);ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
            fig.suptitle(branch.replace('_',' ')+'; median/IQR conditional on available final update; valid/full counts in CSV',fontsize=9)
            emit(fig,'X3_NPG_last_error_'+branch)
        fig,axs=plt.subplots(1,2,figsize=(10,3.8))
        for ax,metric in zip(axs,['gap','relative_gap']):
            for k,color in zip([1,2,4,6,12],['#6a7da6','#cf7735','#57976a','#9c6ab0','#354858']):
                cell=sorted([r for r in nstats if r['spectrum']=='gapped' and int(r['k'])==k and r['metric']==metric],key=lambda r:int(r['budget_multiplier']))
                finite=[r for r in cell if math.isfinite(float(r['median']))]
                ax.plot([int(r['planned_transitions']) for r in finite],[float(r['median']) for r in finite],'o-',color=color,label=f'k{k}')
                iq=[r for r in finite if math.isfinite(float(r['q75']))]
                ax.fill_between([int(r['planned_transitions']) for r in iq],[float(r['q25']) for r in iq],[float(r['q75']) for r in iq],color=color,alpha=.08)
                for r in finite:
                    if int(r['stable_count'])<32:ax.annotate(r['stable_count']+'/32',(int(r['planned_transitions']),float(r['median'])),fontsize=6)
            ax.set(xscale='log',yscale='log',xlabel='Planned M per arm',ylabel=metric.replace('_',' '),title='Two-level actual endpoints');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
        fig.suptitle('X3 two-level endpoints; median/IQR with failures +inf and full32 denominator; no counterfactual learner',fontsize=9)
        emit(fig,'X3_NPG_two_level_endpoints')
    else:pending.append('X3 NPG last-estimator mechanism not complete; no partial mechanism substituted')
else:pending.append('X3 NPG final order report not yet available; no partial result substituted')

assert all(sha(root/name)==digest for name,digest in sources.items()),'Input changed while rendering'
manifest=dict(status='COMPLETE_AVAILABLE_SAVED_CSV_PLOTS',sources=sources,figures=figures,pending=pending,
    script_sha256=sha(Path(__file__)),policy_evaluations=0,new_training_transitions=0,
    provenance='Local CSV-only plotting; no model solver, estimator, data collection or Slurm job',cache=str(cache),temp=str(temporary))
(dest/'PLOT_MANIFEST.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
print(json.dumps(dict(status=manifest['status'],output=str(dest),figure_files=len(figures),pending=pending)),flush=True)
