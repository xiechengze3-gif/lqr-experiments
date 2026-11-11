"""Prepare presentation/transport adapters only. No old file is edited."""
import ast,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;X=R.parent/'x10-20261106';CTL=X/'actor-correction-controls-v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,b):
    if isinstance(b,str):b=b.encode()
    if p.suffix=='.py':ast.parse(b.decode(),filename=p.name)
    with p.open('xb') as f:f.write(b)
old=(CTL/'render_report_v2.py').read_text(encoding='utf-8');prefix=old[:old.index('def main(config_path):')]
prefix=prefix.replace('/results/x10-20261106/X10b','/results/x12-20261106')
main='''def main(config_path):
    e.require_compute();directory=BASE/'report-v1'
    proof=json.loads((directory/'PRODUCTS_COMPLETE_v1.json').read_text(encoding='utf-8'))
    assert proof['status']=='MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED' and proof['config_sha256']==e.sha(config_path)
    for n,h in proof['files'].items():assert e.sha(directory/n)==h
    rows=read(directory/'summary_merged_nine_rungs.csv');primary=[r for r in rows if r['ratio_kind']=='failure_inclusive']
    assert len(rows)==180 and len(primary)==90
    figures=directory/'figures';assert not figures.exists();figures.mkdir()
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    generated=[]
    for metric,label in [('gap','Absolute gap'),('relative_gap','Gap / initial gap')]:
        fig,axes=plt.subplots(5,2,figsize=(12,15))
        for i,n in enumerate([24,36,48,60,72]):
            for j,alg in enumerate(['NPG','PI']):
                cell(axes[i,j],[r for r in primary if int(float(r['n']))==n and r['algorithm']==alg],metric)
                axes[i,j].set_ylabel(label)
                if i==0:axes[i,j].legend(fontsize=7)
        fig.suptitle('X12: n=m=60 added; all nine budgets and all 32 outputs retained per cell\\n'
                     'Existing n=24,36,48,72 statistics reused byte-for-byte. Descriptive experiments.',fontsize=10)
        fig.tight_layout(rect=(0,0,1,.96));generated+=emit(fig,figures,'all_dimensions_'+metric)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,alg in zip(axes,['NPG','PI']):
        cell(ax,[r for r in primary if int(float(r['n']))==60 and r['algorithm']==alg],'gap')
        ax.set_ylabel('Absolute gap');ax.legend(fontsize=7)
    fig.suptitle('n=m=60; exact rank 2; all 32 outputs retained at every rung',fontsize=10)
    fig.tight_layout(rect=(0,0,1,.92));generated+=emit(fig,figures,'n60_main_gap')
    selected=[r for r in primary if int(float(r['n']))==60]
    derived=read(directory/'transitions_saved_derived.csv')
    lines=['# X12 saved-data report','',
       'Descriptive extension of the accepted X6b/X10b experiments to n=m=60. No theorem verification or epsilon/probability guarantee.','',
       'Family S, Q=R=W=I, exact rank B=2, retained rank k=2, K0=0, eta=.2, nu=1, H=16. '
       'NPG16/PI8 updates; 16 pulse burn blocks and one baseline block each update; fixed growing integer schedules. '
       'Every arm/rung has its own continuous state and paired external randomness. These are the frozen observation-only Stein NPG and PI learners. '
       'No critic/LSTD, oracle input, line search, clipping, recovery or adaptive rank is introduced.','',
       'Pilot K0-only calibration selected N_cal=2097152 from the complete registered grid. '
       'This selection does not certify all-stage estimation errors or the sufficient theoretical constants. '
       'Every formal configuration was fixed before observations: 8 systems301..308 x4 seeds1701..1704, '
       'nine rungs1/256..1, two algorithms and both arms. All576paired paths/1152arms and193644738560formal transitions are retained.','',
       'Instability is absorbing and consumes its remaining registered budget under K0 padding. '
       'All gap medians/IQR use the full32 denominator with failures at infinity. Failure counts/rates appear at every plotted budget and in CSV. '
       'Both paired-ratio definitions, 5000 system-cluster bootstrap draws, undefined bootstrap mass, '
       'and all attainment/censoring diagnostics follow the unchanged original analyzer. '
       'Saved-stage estimator arrays, updates, padding counts and checkpoint hashes are audited on compute nodes.','',
       'summary.csv under new-n60 contains36new rows in the exact X6b schema. '
       'summary_merged_nine_rungs.csv contains180rows with the accepted144row X10b table as an exact byte prefix. '
       'The original8derived saving-factor rows, failures and per-cell counts are also exact prefixes of their merged copies. '
       'Old results are reused without simulation, bootstrap or reanalysis.','',
       '|algorithm|rung|M per arm|dense gap median|truncated gap median|dense stable|truncated stable|paired ratio [95% CI]|',
       '|---|---:|---:|---:|---:|---:|---:|---|']
    for r in sorted(selected,key=lambda r:(r['algorithm'],float(r['rung']))):
        lines.append('|'+ '|'.join([r['algorithm'],r['rung'],r['primitive_per_arm'],fmt(r['dense_gap_median']),
            fmt(r['truncated_gap_median']),r['dense_stable']+'/32',r['truncated_stable']+'/32',
            f"{fmt(r['paired_ratio_median'])} [{fmt(r['ci_low'])}, {fmt(r['ci_high'])}]"])+'|')
    lines+=['','|algorithm|n60 saving factor|left censored|right censored|unbracketed|',
            '|---|---:|---|---|---|']
    for r in derived:
        lines.append('|'+ '|'.join([r['algorithm'],fmt(r['factor']),r['left_censored'],r['right_censored'],r['unbracketed']])+'|')
    lines+=['','Factors use the verbatim paper cross function: first log-log crossing of the truncated full32 median '
        'curve with the dense full-rung median. No smoothing or extrapolation. Censoring and unidentified targets remain explicit.','',
        'The frozen cost gate uses max(measured n60 pilot body,historical larger-dimension floor), '
        'ceil((1.20*body+30)/60) task limits, all pilots, model-only prep and8SU report reserve. '
        'Actual-spend forecast<=230SU; requested upper<=300SU; total own concurrency<=64. '
        'Completed Slurm elapsed, forecast, requested reservations and AMS settlements are distinct; overlapping AMS and Slurm charges are never added.','',
        'No old result, release, paper source or TeX is edited. Full raw outputs, models, RNG receipts, sources and ledgers accompany the report.']
    report=directory/'SCIENCE_REPORT.md'
    with report.open('x',encoding='utf-8') as f:f.write('\\n'.join(lines)+'\\n')
    generated.append(report)
    result=dict(status='SAVED_CSV_FIGURES_TABLES_RENDERED',source_sha256=e.sha(__file__),config_sha256=e.sha(config_path),
                job=os.environ['SLURM_JOB_ID'],no_new_training_transitions=True,plot_gap_denominator='FULL32_FAILURE_INCLUSIVE',
                files={p.relative_to(directory).as_posix():e.sha(p) for p in generated})
    with (directory/'RENDER_COMPLETE_v1.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(status=result['status'],files=len(generated))),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);main(p.parse_args().config)
'''
put(R/'report_render_v1.py',prefix+main)
transfer=(CTL/'transfer_report_v2.py').read_text(encoding='utf-8').replace('/results/x10-20261106/X10b','/results/x12-20261106').replace('tmp/x10-20261106','tmp/x12-20261106').replace('x10b-report-v1','x12-report-v1').replace('X10B','X12').replace('X10b','X12').replace("coverage['paired_paths'] == 1280","coverage['paired_paths'] == 576")
before="prefixes = ['formal-v1', 'resource-v1', 'resource-v2', 'report-v1', 'budget', 'submissions', 'logs']"
after="prefixes = ['calibration-v1','calibration-resolution-v1','timing-v1','formal-models-v1','formal-v1','report-v1','budget','submissions','logs','failures','submission-correction-v2','submission-correction-v3','deployments']"
assert transfer.count(before)==1;transfer=transfer.replace(before,after);put(R/'transfer_report_v1.py',transfer)
provenance=(X/'copy_actor_provenance.py').read_text(encoding='utf-8').replace('/results/x10-20261106/X10b','/results/x12-20261106')
put(R/'copy_report_provenance_v1.py',provenance)
chunks=(CTL/'report_chunks_v1.py').read_text(encoding='utf-8').replace('tmp/x10-20261106','tmp/x12-20261106').replace('x10b-report','x12-report').replace('X10B','X12')
put(R/'report_chunks_v1.py',chunks)
for name in ['Prepare-ReportChunks-v1.ps1','Fetch-ReportChunks-v1.ps1']:
    text=(CTL/name).read_text(encoding='utf-8').replace('$root=Split-Path $PSScriptRoot -Parent','$root=$PSScriptRoot')
    text=text.replace('x10-20261106','x12-20261106').replace('x10b-report','x12-report').replace('downloads-actor-report-v1','downloads-report-v1').replace('delivery-actor-report-v1','delivery-report-v1')
    text=text.replace('transfer_report_v2.py','transfer_report_v1.py').replace('ACTOR_REPORT_MANIFEST_v1.json','REPORT_MANIFEST_v1.json').replace("$release.files.'transfer_actor_report.py'","$release.files.'transfer_report_v1.py'")
    put(R/name,text)
oldast=ast.parse(old);newtext=(R/'report_render_v1.py').read_text(encoding='utf-8');newast=ast.parse(newtext)
functions={n.name:ast.get_source_segment(old,n) for n in oldast.body if isinstance(n,ast.FunctionDef)}
newfunctions={n.name:ast.get_source_segment(newtext,n) for n in newast.body if isinstance(n,ast.FunctionDef)}
preserved=['read','fmt','cell','emit']
assert all(functions[n]==newfunctions[n] for n in preserved)
proof=dict(status='PRESENTATION_TRANSPORT_SOURCES_PREPARED_NO_JOBS',render_functions_literal_identical=preserved,
           source_sha256=sha(CTL/'render_report_v2.py'),new_render_sha256=sha(R/'report_render_v1.py'),
           changes='X12 namespace,5dimensions,n60 report narrative; all plotting primitives unchanged. Transport namespace and coverage/prefix metadata only.',
           new_training_transitions=0,Grace_SU=0,files={p.name:sha(p) for p in [R/'report_render_v1.py',R/'transfer_report_v1.py',R/'copy_report_provenance_v1.py',R/'report_chunks_v1.py',R/'Prepare-ReportChunks-v1.ps1',R/'Fetch-ReportChunks-v1.ps1']})
put(R/'REPORT_SOURCE_PREPARED_v1.json',json.dumps(proof,indent=2))
print(json.dumps(proof))
