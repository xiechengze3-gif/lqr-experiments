"""Saved-record-only report using literal original X10a q/cost arithmetic."""
import ast,csv,hashlib,json,math,os,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;C=R.parents[1];X=R.parent/'x10-20261106'
sys.path.insert(0,str(R/'src-v1'));import core
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old=(X/'ce-src-v2/analyze_ce.py').read_text();parts={n.name:ast.get_source_segment(old,n) for n in ast.parse(old).body if isinstance(n,ast.FunctionDef)}
exec(compile(parts['q']+'\n'+parts['cost'],str(X/'ce-src-v2/analyze_ce.py'),'exec'))

def csv_new(p,rows,fields=None):
    fields=fields or list(dict.fromkeys(k for row in rows for k in row))
    with p.open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    assert sha(C/'CLAUDE_TASK.md')==os.environ['X11_ADVANCE_REVIEW_SHA256']
    cfg=json.loads((R/'config-v1.json').read_text());formal=R/'formal-v1'
    done=json.loads((formal/'FORMAL_DONE.json').read_text());assert done['status']=='COMPLETE_FORMAL_NEW_CONFIGURATIONS_ONLY'
    assert done['config_sha256']==sha(R/'config-v1.json')
    out=R/'report-v2';out.mkdir();records=[];raw_checks=0
    for item in done['paths']:
        p=formal/item['path']/'DONE.json';assert sha(p)==item['done_sha256']
        d=json.loads(p.read_text());assert d['engine_sha256']==cfg['sources']['frozen_engine.py'] and d['source_sha256']==cfg['sources']['core.py']
        assert d['primitive_transitions']==524800 and len(d['records'])==10
        assert {r['arm'] for r in d['records']}=={'dense','truncated'}
        for artifact in d['artifacts']:
            assert sha(p.parent/artifact['path'])==artifact['sha256'];raw_checks+=1
        records.extend(dict(r,source='new_X11') for r in d['records'])
    assert len(records)==3520 and raw_checks==1760
    reused=[];sources={}
    old48=R.parent/'x6-20261101/CE-addition-v2/deliveries/ce-20365253-v7/X6a/CE-addition-v1/observations.csv'
    sources[str(old48)]=sha(old48)
    with old48.open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['family']=='S' and int(row['n'])==48:
                for arm in ['dense','truncated']:
                    stable=row[arm+'_stable']=='True'
                    reused.append(dict(n=48,m=48,system=int(row['system']),seed=int(row['seed']),N=int(row['N']),arm=arm,
                        primitive_transitions=int(row['primitive_transitions']),stable=stable,gap=float(row[arm+'_gap']) if stable else math.inf,
                        relative_gap=float(row[arm+'_relative_gap']) if stable else math.inf,source='reused_X6a_CE'))
    old16=X/'ce-report-v3/new_dimension_records.csv';sources[str(old16)]=sha(old16)
    with old16.open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if int(row['n'])==16:
                row.update(n=16,m=16,system=int(row['system']),seed=int(row['seed']),N=int(row['N']),
                    stable=row['stable']=='True',gap=float(row['gap']),relative_gap=float(row['relative_gap']),source='reused_X10a_CE')
                reused.append(row)
    assert len(reused)==640 and len({(r['n'],r['m'],r['system'],r['seed'],r['N'],r['arm']) for r in reused})==640
    all_records=records+reused
    csv_new(out/'new_records.csv',records);csv_new(out/'reused_records.csv',reused)
    fields=['n','eps','dense_N_req','truncated_N_req','m'];cost_rows=[];flags=[];stable_rows=[];ratio_rows=[]
    for n,m in sorted({(r['n'],r['m']) for r in all_records}):
        selected=[r for r in all_records if r['n']==n and r['m']==m];Ns=sorted({r['N'] for r in selected})
        row=dict(n=n,m=m,eps=.01)
        for arm in ['dense','truncated']:
            med=[]
            for N in Ns:
                group=[r for r in selected if r['N']==N and r['arm']==arm];assert len(group)==32
                med.append(q([r['gap'] for r in group],.5))
                stable_rows.append(dict(n=n,m=m,N=N,arm=arm,total=32,stable=sum(r['stable'] for r in group),failures=sum(not r['stable'] for r in group),
                    gap_median=med[-1],gap_q25=q([r['gap'] for r in group],.25),gap_q75=q([r['gap'] for r in group],.75),source=group[0]['source']))
            row[arm+'_N_req']=cost(np.array(Ns,float),np.array(med),.01)
            flags.append(dict(n=n,m=m,arm=arm,eps=.01,left_censored=med[0]<=.01,right_censored=not math.isfinite(row[arm+'_N_req']),
                minimum_N=min(Ns),maximum_N=max(Ns),source=selected[0]['source']))
        cost_rows.append(row)
        for N in Ns:
            pairs={}
            for r in selected:
                if r['N']==N:pairs.setdefault((r['system'],r['seed']),{})[r['arm']]=r
            assert len(pairs)==32 and all(set(p)=={'dense','truncated'} for p in pairs.values())
            stable={};inclusive={};both_failed=0;dense_only=0;trunc_only=0
            for (system,seed),pair in pairs.items():
                d,t=pair['dense'],pair['truncated'];ratio=None
                if d['stable'] and t['stable']:
                    assert t['gap']>0;ratio=d['gap']/t['gap'];stable.setdefault(system,[]).append(ratio)
                elif not d['stable'] and t['stable']:ratio=math.inf;dense_only+=1
                elif d['stable'] and not t['stable']:ratio=0.;trunc_only+=1
                else:both_failed+=1
                if ratio is not None:inclusive.setdefault(system,[]).append(ratio)
            for kind,values in [('both_stable',stable),('failure_inclusive',inclusive)]:
                medians=[q(v,.5) for v in values.values()]
                ratio_rows.append(dict(n=n,m=m,N=N,ratio_kind=kind,total_pairs=32,eligible_pairs=sum(map(len,values.values())),systems=len(values),
                    median=q(medians,.5) if medians else None,q25=q(medians,.25) if medians else None,q75=q(medians,.75) if medians else None,
                    both_failed=both_failed,dense_only_failed=dense_only,truncated_only_failed=trunc_only,
                    definition='median_system(median_seed(dense_gap/truncated_gap))',source=selected[0]['source']))
    baseline=X/'ce-report-v3/merged_X6a_sample_cost_derived.csv';sources[str(baseline)]=sha(baseline)
    with baseline.open(newline='') as f:oldcost={int(r['n']):r for r in csv.DictReader(f) if int(r['n']) in [16,48]}
    paper=R/'paper-rounded-X6a_CE_full_gaps.csv';sources[str(paper)]=sha(paper)
    with paper.open(newline='') as f:paperrows=[r for r in csv.DictReader(f) if r['family']=='S' and r['n']=='48']
    reused_cost=[];new_cost=[];rounding_audit=[]
    for row in cost_rows:
        if row['n']==row['m']:
            oldrow=oldcost[row['n']]
            for arm,key in [('dense','dense_abs_gap'),('truncated','trunc_abs_gap')]:
                if row['n']==48:
                    reference=cost(np.array([float(r['N']) for r in paperrows]),np.array([float(r[key]) for r in paperrows]),.01)
                else:reference=row[arm+'_N_req']
                assert np.isclose(reference,float(oldrow[arm+'_N_req']),rtol=1e-12,atol=1e-8),'Original-paper input arithmetic mismatch.'
                rounding_audit.append(dict(n=row['n'],m=row['m'],arm=arm,full_precision_raw_cross=row[arm+'_N_req'],
                    original_csv_cross=float(oldrow[arm+'_N_req']),original_input_cross=reference,
                    raw_vs_original_difference=row[arm+'_N_req']-float(oldrow[arm+'_N_req']),
                    explanation='Old X6a paper CSV uses 5-significant-digit report transcription; new rows use full precision.' if row['n']==48 else 'X10a full-precision saved records reproduce unchanged original row.'))
                row[arm+'_N_req']=float(oldrow[arm+'_N_req'])
            reused_cost.append(dict(oldrow,m=row['n']))
        else:new_cost.append(row)
    csv_new(out/'legacy_rounding_audit.csv',rounding_audit)
    assert len(new_cost)==11 and len(reused_cost)==2
    csv_new(out/'new_X6a_sample_cost_derived.csv',new_cost,fields)
    csv_new(out/'merged_X6a_sample_cost_derived.csv',new_cost+reused_cost,fields)
    csv_new(out/'stability_by_N.csv',stable_rows);csv_new(out/'paired_gap_ratios_by_N.csv',ratio_rows);csv_new(out/'censoring_flags.csv',flags)
    csv_new(out/'failures.csv',[r for r in records if not r['stable']],list(dict.fromkeys(k for r in records for k in r)))
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
    for ax,filter_,key,title in [(axes[0],lambda x:x['n']==48,'m','Fixed state dimension n=48'),(axes[1],lambda x:x['m']==16,'n','Fixed input dimension m=16')]:
        rows=sorted([r for r in cost_rows if filter_(r)],key=lambda r:r[key])
        for arm,color in [('dense','#b45309'),('truncated','#0369a1')]:
            ax.plot([r[key] for r in rows],[r[arm+'_N_req'] for r in rows],'-o',label=arm,color=color)
        ax.set(xlabel='Input dimension m' if key=='m' else 'State dimension n',ylabel='Regression samples for absolute gap 0.01',yscale='log',title=title)
        ax.grid(alpha=.2);ax.legend()
    fig.savefig(out/'sample_cost.png',dpi=180);fig.savefig(out/'sample_cost.svg');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
    for ax,filter_,key,title in [(axes[0],lambda x:x['n']==48,'m','n=48: paired gap ratios'),(axes[1],lambda x:x['m']==16,'n','m=16: paired gap ratios')]:
        ratios=[r for r in ratio_rows if filter_(r) and r['ratio_kind']=='failure_inclusive']
        for v in sorted({r[key] for r in ratios}):
            rows=sorted([r for r in ratios if r[key]==v],key=lambda r:r['N'])
            ax.plot([r['N'] for r in rows],[r['median'] for r in rows],'-o',markersize=3,label=f'{key}={v}')
        ax.axhline(1,color='gray',lw=1);ax.set(xscale='log',yscale='log',xlabel='Regression samples N',ylabel='Paired dense / rank-2 gap ratio',title=title)
        ax.grid(alpha=.2);ax.legend(ncol=2,fontsize=8)
    fig.savefig(out/'paired_gap_ratios.png',dpi=180);fig.savefig(out/'paired_gap_ratios.svg');plt.close(fig)
    totalfails=sum(not r['stable'] for r in records)
    text='# X11 CE rectangular sweeps\n\n352 new physical paths,11 unique cells,8systems x4seeds,184729600transitions; 0GraceSU. Square48/16 reused from verified local sources; no resampling. All1760 raw fit archive hashes checked. Every arm/N stability denominator32.\n\n'
    text+='| n | m | Dense N at gap.01 | Rank2 N at gap.01 | Sample ratio |\n|---:|---:|---:|---:|---:|\n'
    for r in sorted(cost_rows,key=lambda r:(r['n'],r['m'])):text+=f"|{r['n']}|{r['m']}|{r['dense_N_req']:.2f}|{r['truncated_N_req']:.2f}|{r['dense_N_req']/r['truncated_N_req']:.3f}|\n"
    text+=f'\nNew arm-prefix failure records: {totalfails}/3520. See stability_by_N.csv for each cell and N; censoring_flags.csv for every arm. Crossing is the original median32 gap/log-log first downcross, no extrapolation. Square48 original paper crossings reproduce from its rounded report-transcribed gap CSV; raw full-precision crosses differ by 0.3000 dense and 0.02047 rank2 samples. Square16 reproduces directly from full-precision X10a records. Original source values retained in merged rows; all new rows use full precision with the same crossing arithmetic. See legacy_rounding_audit.csv. Report-v1 stopped on this provenance check and is preserved; no trajectory rerun. Paired ratio instead aggregates within-seed pairs, then per-system medians. These distinct statistics are labeled.\n\n'
    text+='Both figures are saved-record descriptive comparisons. All failures retained; no theorem verification or epsilon-success-probability claim. Source/caches/temp/output on E; one BLAS thread each, four local workers. Old results and paper untouched.\n'
    with (out/'REPORT.md').open('x',encoding='utf-8') as f:f.write(text)
    proof=dict(status='REPORT_GENERATED_VISUAL_QA_PENDING',new_paths=352,new_records=3520,new_cells=11,reused_cells=2,raw_archive_hash_checks=raw_checks,
        failures=totalfails,old_square_crosses_reproduced_from_original_inputs=True,legacy_rounding_disclosed=True,reused_sources=sources,formal_receipt_sha256=sha(formal/'FORMAL_DONE.json'),
        analysis_source_sha256=sha(Path(__file__)),original_arithmetic_functions_literal=True,arithmetic_source_sha256=sha(X/'ce-src-v2/analyze_ce.py'),
        new_training_transitions=0,Grace_SU=0,Slurm_job_id=None,files={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    core.save_new(out/'REPORT_GENERATED.json',proof)
    print(json.dumps({k:v for k,v in proof.items() if k not in ['files','reused_sources']}),flush=True)

if __name__=='__main__':main()
