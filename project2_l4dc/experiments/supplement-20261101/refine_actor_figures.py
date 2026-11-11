"""Saved actor table views: isolate weak NPG effects and show PI stability explicitly."""
import csv,json,os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import engine as e

def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def emit(fig,dest,name):
    fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(dest/(name+'.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)

def main():
    e.require_compute();plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    colors={'dense':'#386aab','truncated':'#cf7735','k2':'#cf7735'}
    for exp in ['X1','X2']:
        old=e.OUT/exp/'report-actors';dest=e.OUT/exp/'report-actors-figures-v3';assert not dest.exists();dest.mkdir()
        stats=read(old/'endpoint_statistics.csv')
        if exp=='X1':
            fig,axs=plt.subplots(1,2,figsize=(10,3.8))
            for ax,metric in zip(axs,['gap','relative_gap']):
                for mode in ['dense','truncated']:
                    cell=sorted([r for r in stats if r['algorithm']=='NPG' and r['null_scale']=='0.25' and r['mode']==mode and r['metric']==metric],key=lambda r:int(r['m']))
                    assert all(r['stable_count']=='32' for r in cell)
                    x=[int(r['m'])-2 for r in cell];ax.plot(x,[float(r['median']) for r in cell],'o-',color=colors[mode],label=mode)
                    ax.fill_between(x,[float(r['q25']) for r in cell],[float(r['q75']) for r in cell],color=colors[mode],alpha=.1)
                ax.set(yscale='log',xticks=[2,4,7,10],xlabel='Redundant inputs m-r (matched nonzero-null family)',ylabel=metric.replace('_',' '),title='NPG: each cell stable32/32; M=93,308,928/arm');ax.legend(frameon=False,fontsize=7);ax.grid(alpha=.2)
            fig.suptitle('X1 NPG descriptive median/IQR; all paired gain95% intervals include1 (see tables)',fontsize=9);emit(fig,dest,'npg_endpoints_only')
            fig,axs=plt.subplots(2,2,figsize=(10,5.6),gridspec_kw={'height_ratios':[4,1]})
            for col,null in enumerate(['0.0','0.25']):
                ax=axs[0,col];table=[];labels=[]
                for mode in ['dense','truncated']:
                    cell=sorted([r for r in stats if r['algorithm']=='PI' and float(r['null_scale'])==float(null) and r['mode']==mode and r['metric']=='gap'],key=lambda r:int(r['m']))
                    x=[int(r['m'])-2 for r in cell];ax.plot(x,[int(r['failures'])/32 for r in cell],'o-',color=colors[mode],label=mode)
                    table.append([r['failures']+'/32' for r in cell]);labels=[str(int(r['m'])-2) for r in cell]
                ax.set(ylim=(-.03,1.03),xlabel='Redundant inputs m-r',ylabel='Failed endpoints / full32',title=f'PI v4: null={null}, M=93,308,928/arm');ax.legend(frameon=False,fontsize=7);ax.grid(alpha=.2)
                below=axs[1,col];below.axis('off');tab=below.table(cellText=table,rowLabels=['dense','truncated'],colLabels=labels,loc='center');tab.auto_set_font_size(False);tab.set_fontsize(7);below.set_title('Exact failed/full counts; columns are m-r',fontsize=7)
            fig.suptitle('X1 PI stability diagnostic: failures persist despite disjoint dense pilot qualification; no successful-only curve',fontsize=9);emit(fig,dest,'pi_failure_rates')
        else:
            fig,axs=plt.subplots(1,2,figsize=(10,4))
            for ax,metric in zip(axs,['gap','relative_gap']):
                for mode,offset in [('dense',-.06),('k2',.06)]:
                    cell=sorted([r for r in stats if r['mode']==mode and r['metric']==metric],key=lambda r:int(r['n']))
                    x=[i+offset for i in range(len(cell))];y=[float(r['median']) for r in cell]
                    ax.errorbar(x,y,yerr=[[v-float(r['q25']) for v,r in zip(y,cell)],[float(r['q75'])-v for v,r in zip(y,cell)]],fmt='o',capsize=4,color=colors[mode],label=mode)
                ax.set(yscale='log',xticks=[0,1],xticklabels=['n=m12\nM=33,602,016','n=m24\nM=542,850,432'],ylabel=metric.replace('_',' '),title='NPG median/IQR; every method x n stable32/32');ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=7)
            fig.suptitle('X2 NPG mixed endpoints: both paired95% ratio intervals include1; within-n comparisons only',fontsize=9);emit(fig,dest,'npg_endpoint_iqr')
        e.save(dest/'REPORT.json',dict(status='COMPLETE',scope='SAVED_CSV_FIGURE_REFINEMENT',source_report_sha256=e.sha(old/'REPORT.json'),
          source_statistics_sha256=e.sha(old/'endpoint_statistics.csv'),source_sha256=e.sha(__file__),new_learning_runs=0,new_training_transitions=0,
          negative_findings_preserved=True,job=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='COMPLETE',new_learning_runs=0)))

if __name__=='__main__':main()
