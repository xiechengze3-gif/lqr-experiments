"""Saved-CSV CE figures and explicit failure rates; no estimator or controller calls."""
import csv
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
OUT=HERE/'ce-report-v3'
COLORS=dict(dense='#df773c',truncated='#287bb5')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):return math.nan if value is None or value=='' else float(value)


def read(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:return list(csv.DictReader(stream))


def write(path,rows,fields=None):
    fields=fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open('x',newline='',encoding='utf-8') as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)


def failure_tables():
    groups=defaultdict(list)
    inputs=HERE/'ce-report-inputs-v1'
    for origin,rows in [('REUSED_X8',read(inputs/'X8_exact_raw.csv')+read(inputs/'X8_geometric_raw.csv')),
                        ('NEW_X10a',read(OUT/'new_X8_records.csv'))]:
        for r in rows:
            groups[('X8',r['config'],r['order'],int(float(r['N'])),origin)].append(not math.isfinite(float(r['rel_gap'])))
    for r in read(inputs/'X6a_CE_observations.csv'):
        if r['family']!='S':continue
        for arm in COLORS:
            groups[('X6a','n'+str(int(float(r['n']))),arm,int(float(r['N'])),'REUSED_X6a')].append(r[arm+'_stable']=='False')
    for r in read(OUT/'new_dimension_records.csv'):
        groups[('X6a','n'+str(int(float(r['n']))),r['arm'],int(float(r['N'])),'NEW_X10a')].append(r['stable']=='False')
    rows=[]
    for (part,config,order,N,origin),flags in sorted(groups.items()):
        assert len(flags)==32
        rows.append(dict(part=part,config=config,order_or_arm=order,N=N,origin=origin,
                         full=32,failures=sum(flags),failure_rate=sum(flags)/32))
    for r in read(OUT/'merged_X1_normalized_statistics.csv'):
        if float(r['null_scale'])!=.25 or r['mode'] not in COLORS or float(r['m_minus_r'])<=0:continue
        full=int(float(r['count']));failed=int(float(r['failures']));assert full==32
        rows.append(dict(part='X1',config='m'+str(int(float(r['m']))),order_or_arm=r['mode'],N=int(float(r['N'])),
                         origin='MERGED_SAVED_CSV',full=full,failures=failed,failure_rate=failed/full))
    write(OUT/'all_failure_rates_by_prefix.csv',rows)
    return rows


def plot_values(ax,x,y,*,color,label,marker='o',linestyle='-',bounds=None,lo=None,hi=None):
    x,y=np.asarray(x,float),np.asarray(y,float)
    positive=np.isfinite(y)&(y>0)
    ax.plot(x,np.where(positive,y,np.nan),color=color,marker=marker,ls=linestyle,label=label,ms=4,lw=1.1)
    if lo is not None:
        lo,hi=np.asarray(lo,float),np.asarray(hi,float)
        valid=np.isfinite(lo)&np.isfinite(hi)&(lo>0)
        ax.fill_between(x,lo,hi,where=valid,color=color,alpha=.10)
    for i in range(len(y)):
        if not math.isfinite(y[i]):
            point=bounds[i] if bounds is not None else (max(y[positive])*3 if any(positive) else 1.)
            assert point>0
            text='>' if bounds is not None and math.isinf(y[i]) else ('∞' if math.isinf(y[i]) else 'N/A')
            ax.plot(x[i],point,'^',mfc='none',mec=color,ms=6)
            ax.annotate(text,(x[i],point),xytext=(3,3),textcoords='offset points',fontsize=7,color=color)
        elif y[i]<=0:
            point=min(y[positive])/3 if any(positive) else .001
            ax.plot(x[i],point,'v',mfc='none',mec=color,ms=5)
            ax.annotate(f'{y[i]:.3g}',(x[i],point),xytext=(3,3),textcoords='offset points',fontsize=7,color=color)
    ax.set_xscale('log');ax.set_yscale('log');ax.grid(alpha=.18)


def mark_left_bound(ax,x,y,color):
    if math.isfinite(y) and y>0:
        ax.plot([x],[.72*y],'v',mfc='none',mec=color,ms=4)
        ax.annotate('',(x,.72*y),(x,.95*y),arrowprops=dict(arrowstyle='->',color=color,lw=.7))
        ax.annotate('≤',(x,y),xytext=(3,-11),textcoords='offset points',fontsize=7,color=color)


def render(eps,failure_rows,folder):
    fig,axes=plt.subplots(1,3,figsize=(15,5.4))
    s=[r for r in read(OUT/'merged_X8_sample_cost.csv') if float(r['eps'])==eps]
    totals=[]
    for family,marker,linestyle in [('exact','o','-'),('geometric','D','--')]:
        for arm,color in COLORS.items():
            selected=sorted([r for r in s if r['family']==family and r['arm']==arm],key=lambda r:float(r['k']))
            x=[float(r['k']) for r in selected];y=[number(r['N_req']) for r in selected]
            plot_values(axes[0],x,y,color=color,label=family+' '+arm,marker=marker,linestyle=linestyle,
                        bounds=[262144]*len(x),lo=[number(r['ci_low']) for r in selected],hi=[number(r['ci_high']) for r in selected])
            for r in selected:
                matching=[t for t in failure_rows if t['part']=='X8' and t['config']==r['config'] and t['order_or_arm']==r['order']]
                assert len(matching)==10
                full=sum(t['full'] for t in matching);failed=sum(t['failures'] for t in matching)
                assert full==320 and failed==int(float(r['n_unstable']))
                left=math.isfinite(number(r['N_req'])) and number(r['N_req'])<=min(t['N'] for t in matching)
                if left:mark_left_bound(axes[0],float(r['k']),number(r['N_req']),color)
                totals.append(dict(panel='a',eps=eps,config=r['config'],arm=arm,order=r['order'],full_across_prefixes=full,
                                   failures_across_prefixes=failed,failure_rate=failed/full,
                                   left_censored=left,right_censored=not math.isfinite(number(r['N_req']))))
    axes[0].set_xlabel('Retained k / effective rank');axes[0].set_ylabel('Regression transitions to absolute target')
    axes[0].set_title('(a) Exact / geometric spectrum, n=m=48');axes[0].legend(fontsize=6.5)
    dims=sorted(read(OUT/'merged_X6a_sample_cost_derived.csv'),key=lambda r:float(r['n']))
    for arm,color in COLORS.items():
        x=[float(r['n']) for r in dims];y=[number(r[arm+'_N_req']) for r in dims];bounds=[]
        for r in dims:
            config='n'+str(int(float(r['n'])))
            matching=[t for t in failure_rows if t['part']=='X6a' and t['config']==config and t['order_or_arm']==arm]
            assert matching
            bounds.append(max(t['N'] for t in matching))
            full=sum(t['full'] for t in matching);failed=sum(t['failures'] for t in matching)
            left=math.isfinite(number(r[arm+'_N_req'])) and number(r[arm+'_N_req'])<=min(t['N'] for t in matching)
            if left:mark_left_bound(axes[1],float(r['n']),number(r[arm+'_N_req']),color)
            totals.append(dict(panel='b',eps=.01,config=config,arm=arm,order=2 if arm=='truncated' else int(float(r['n'])),
                               full_across_prefixes=full,failures_across_prefixes=failed,failure_rate=failed/full,
                               left_censored=left,right_censored=not math.isfinite(number(r[arm+'_N_req']))))
        plot_values(axes[1],x,y,color=color,label=arm,bounds=bounds)
    axes[1].set_xlabel('n=m');axes[1].set_title('(b) Family S, rank 2, absolute target .01');axes[1].legend(fontsize=7)
    redundancy=[r for r in read(OUT/'merged_X1_normalized_statistics.csv')
        if float(r['null_scale'])==.25 and float(r['m_minus_r'])>0 and float(r['N'])==8192 and r['mode'] in COLORS]
    for arm,color in COLORS.items():
        selected=sorted([r for r in redundancy if r['mode']==arm],key=lambda r:float(r['m_minus_r']))
        assert len(selected)==10
        plot_values(axes[2],[float(r['m_minus_r']) for r in selected],[float(r['median']) for r in selected],
            color=color,label=arm,lo=[float(r['q25']) for r in selected],hi=[float(r['q75']) for r in selected])
        for r in selected:
            totals.append(dict(panel='c',eps=None,config='m'+str(int(float(r['m']))),arm=arm,order=2 if arm=='truncated' else int(float(r['m'])),
                               full_across_prefixes=32,failures_across_prefixes=int(float(r['failures'])),failure_rate=int(float(r['failures']))/32))
    axes[2].set_xlabel('m-r');axes[2].set_ylabel('N D(K) / v_star');axes[2].set_title('(c) n=12, r=2, null scale .25, N=8192');axes[2].legend(fontsize=7)
    for index,panel in enumerate(['a','b','c']):
        cells=[r for r in totals if r['panel']==panel]
        maxrate=max(r['failure_rate'] for r in cells)
        axes[index].text(.0,-.27,f'Max failure rate over plotted curves: {maxrate:.2%}\n'
             'Exact rates by configuration/N in companion CSV',transform=axes[index].transAxes,fontsize=6.5,va='top')
    fig.suptitle(f'X10a: registered CE densification; panel (a) absolute target {eps:g}\n'
        'All failures retained; > marks right censoring, downward ≤ arrows mark left bounds; CI/IQR only where finite.',fontsize=10)
    fig.tight_layout(rect=(0,0,1,.91))
    products=[]
    for suffix in ['png','svg']:
        target=folder/(f'ce_main_eps_{eps:g}.'+suffix);assert not target.exists()
        fig.savefig(target,dpi=180,bbox_inches='tight');products.append(target)
    plt.close(fig)
    return products,totals


def main():
    for key in ['TEMP','TMP','TMPDIR','XDG_CACHE_HOME','MPLCONFIGDIR']:
        assert Path(os.environ[key]).drive.upper()=='E:' and Path(os.environ[key]).is_dir()
    proof=json.loads((OUT/'REPORT_DONE.json').read_text())
    assert proof['status']=='COMPLETE_NEW_ROWS_BASELINE_BYTES_PRESERVED'
    assert all(v['baseline_prefix_byte_identical'] for v in proof['preservation'].values())
    for name,digest in proof['files'].items():assert sha(OUT/name)==digest
    sourceproof=json.loads((HERE/'ce-report-inputs-v1/MANIFEST_v1.json').read_text())
    for name,meta in sourceproof['files'].items():assert sha(HERE/'ce-report-inputs-v1'/name)==meta['sha256']
    assert not (OUT/'CE_PRESENTATION_v1.json').exists()
    figures=OUT/'figures';assert not figures.exists();figures.mkdir()
    rates=failure_tables();products=[];totals=[]
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    for eps in [.01,.005]:
        generated,table=render(eps,rates,figures);products+=generated;totals+=table
    write(OUT/'plotted_curve_failure_rates.csv',totals)
    counts={'new_sample_cost':len(read(OUT/'new_X8_sample_cost.csv')),
            'new_dimension':len(read(OUT/'new_X6a_sample_cost_derived.csv')),
            'new_normalized':len(read(OUT/'new_X1_normalized_statistics.csv')),
            'new_failures':len(read(OUT/'failures.csv'))}
    assert [counts[k] for k in ['new_sample_cost','new_dimension','new_normalized']]==[32,7,24]
    text=f'''# X10a CE saved-data report

Completed 672 new physical paths and 236797952 primitive transitions, locally with one worker/thread; Grace requested/elapsed 0/0 SU. New grids and all eight systems/four seeds were registered before the pilot. Old result files and paper source remain untouched. Failed pilot-v1 files are retained: the portable wrapper lacked `import json`; the authorized v2 correction passed full bitwise fits/gains/metrics/RNG/count checks. Its completed old X8 pilot was reused by reference. No performance tuning or scope selection followed that failure.

This is descriptive densification of existing experiments. X8 uses its amended **absolute** gap targets .01 and .005; family S dimensions use absolute .01; X1 reports N D(K)/v_star at n12/r2/null scale .25. Targets are median-curve crossings with the frozen original interpolation/censor rules. These are not 29/32 attainment or new theorem-verification claims. All nonfinite observations remain in saved records; no stability-conditioned curve is used.

The plots read merged CSVs whose old rows form a byte-identical prefix. New rows: X8 sample costs {counts['new_sample_cost']}, dimension costs {counts['new_dimension']}, normalized statistics {counts['new_normalized']}; individual new failure records {counts['new_failures']}. All fixed X8 orders remain in new_X8_records.csv. `censoring_flags.csv` contains every registered new target/arm bound. Main plot eps=.005 changes panel (a); panel (b) stays at its registered .01 target, panel (c) at N8192. N4096 results remain exported.

`all_failure_rates_by_prefix.csv` reports exact failures/count32 for every old/new X8 order/prefix, every family S dimension/arm/prefix, and the saved X1 normalization cells. `plotted_curve_failure_rates.csv` gives each displayed curve's failures over its registered prefixes (or the single N8192 cell). Each panel shows its maximum displayed-curve failure rate. These pooled display rates have explicit denominators; per-prefix rates are in the first CSV. Failed or censored sample-cost points remain marked rather than assigned a fabricated crossing. A finite cost at the first registered prefix is the original rule's left-censored upper bound and has a downward arrow/≤ label; > marks right censoring. X8 percentile CIs and X1 IQR bands are drawn only where finite; every original numerical value remains in the CSV.

Frozen engines: shared single-trajectory CE with 512 burn-in transitions, nu1 and original OLS/DARE/truncation. X8 n=m48 retains its exact original loop; rank/spectrum variants share original A/U/V/system and seed construction. Family S dimensions retain the registered prefix grid, with powers through 2^20 appended for n>=60. X1 has m-r=1..10 after merging, no rerun of existing redundancies.

Source/config/model/fit/DONE hashes and true local host/PID provenance are in CE_FORMAL_COVERAGE_v1.json and ce-formal-v2. REPORT_DONE.json binds frozen statistics and exact baseline-byte preservation. Failure metadata inputs are copied with hashes under ce-report-inputs-v1; no old file was changed. Figures and this prose are saved-data presentation only, zero new training transitions.
'''
    report=OUT/'SCIENCE_REPORT.md'
    with report.open('x',encoding='utf-8') as stream:stream.write(text)
    products += [report,OUT/'all_failure_rates_by_prefix.csv',OUT/'plotted_curve_failure_rates.csv']
    receipt=dict(status='SAVED_CE_CSV_FIGURES_FAILURE_RATES_RENDERED',source_sha256=sha(Path(__file__)),
        report_done_sha256=sha(OUT/'REPORT_DONE.json'),config_sha256=proof['config_sha256'],counts=counts,
        new_training_transitions=0,Grace_SU=0,Slurm_job_id=None,
        files={p.relative_to(OUT).as_posix():sha(p) for p in products})
    with (OUT/'CE_PRESENTATION_v1.json').open('x') as stream:json.dump(receipt,stream,indent=2)
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'}))


if __name__=='__main__':main()
