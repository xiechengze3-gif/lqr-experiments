"""Postprocessing supplement, no change to frozen learning source or selection."""
import json
from pathlib import Path
import tarfile
import sys
import numpy as np
from final_story import (CFG,OUT,KS,BUDGETS,assess,assigned,identity,plant,provenance,
                         sha,targets,trunc,dare,atomic_json,require_compute)
from final_story_report_v4 import main as frozen_report, csvwrite, quant


def main():
    require_compute();report=OUT/'report'
    if '--resume-core' in sys.argv:
        core=json.loads((report/'summary.json').read_text())
        assert core['status']=='COMPLETE' and core['formal_task_files']==1560 and core['identity']==identity()
        coverage=list(__import__('csv').DictReader((report/'output_coverage.csv').open()))
        assert len(coverage)==1560
        for row in coverage:
            p=OUT/'formal'/(row['id']+'.json')
            assert sha(p)==row['json_sha256'] and sha(p.with_suffix('.npz'))==row['policy_sha256']
    else:
        frozen_report()
    partial=OUT/'report_partial_numeric_sha256.json'
    if partial.exists():
        old=json.loads(partial.read_text())
        for name,digest in old.items():assert sha(report/name)==digest,('Numeric table changed in report recovery',name)
        atomic_json(report/'report_recovery_audit.json',dict(status='PASS',numeric_tables_identical=True,
            checked_tables=len(old),learning_restarted=False,undefined_spectral_diagnostic='JSON null',
            perturbed_evaluation='Direct stationary Lyapunov cost; nominal optimal cost is not a bound on perturbed plants.'))
    endpoints=list(__import__('csv').DictReader((report/'actor_endpoints.csv').open()))
    raw=[json.loads(p.read_text()) for p in sorted((OUT/'formal').glob('*.json'))]
    adaptive=[];paired=[];ce_summary=[];pop=[]
    for final in BUDGETS:
        group=[d for d in raw if d['spec']['family']=='E2' and d['spec']['algorithm']=='NPG'
               and d['spec']['final']==final and d['spec']['mode']=='adaptive']
        ranks=[d['rows'][-1].get('retained_rank') for d in group if d['status']=='complete']
        rows=[r for d in group for r in d['rows'][1:] if r.get('threshold') is not None]
        adaptive.append(dict(final=final,transitions=assigned(final),n=24,
            complete=sum(d['status']=='complete' for d in group),
            median_terminal_rank=float(np.median(ranks)) if ranks else None,
            min_terminal_rank=min(ranks) if ranks else None,max_terminal_rank=max(ranks) if ranks else None,
            observed_threshold_stages=len(rows),
            empirical_radius_coverage=float(np.mean([r['raw_spectral_error']<=r['threshold'] for r in rows])) if rows else None,
            median_terminal_threshold=float(np.median([d['rows'][-1]['threshold'] for d in group if d['status']=='complete'])) if ranks else None))
    for alg in ['NPG','PI']:
        for m in CFG['ms']:
            ds={}
            for d in raw:
                t=d['spec']
                if t['family']=='E1' and t['algorithm']==alg and t['m']==m:
                    ds[(t['system'],t['trial'],t['mode'])]=d
            ratios=[];unstable=0
            for sy in CFG['systems']:
                for trial in CFG['trials']:
                    a,b=ds[sy,trial,'dense'],ds[sy,trial,'truncated']
                    if a['status']=='complete' and b['status']=='complete':
                        ratios.append(a['rows'][-1]['gap']/b['rows'][-1]['gap'])
                    else:unstable+=1
            paired.append(dict(algorithm=alg,m=m,m_minus_r=m-2,n=24,unpaired_due_to_failure=unstable,
                paired_median_dense_over_truncated=float(np.median(ratios)) if ratios else None))
    ce=[r for d in raw if d['spec']['family']=='E2' and d['spec']['algorithm']=='CE' for r in d['rows']]
    for budget in CFG['ce_budgets']:
        for mode in sorted({r['mode'] for r in ce}):
            group=[r for r in ce if r['N']==budget and r['mode']==mode]
            ce_summary.append(dict(N=budget,transitions=budget+CFG['burn'],mode=mode,
                median_retained_rank=float(np.median([r['k'] for r in group])),**quant(group)))
    # Exact population references are diagnostic only. Record cycling as well as
    # terminal error; a fixed truncation order need not produce a fixed subspace.
    for system in CFG['systems']:
        s,_,_=plant('E2',system)
        for rank in KS:
            k=s['K0'].copy();last64=[];change=None
            for stage in range(1025):
                q=assess(s,k)
                if stage>=961:last64.append(q['gap'])
                if stage in [0,64,256,512,1024]:
                    pop.append(dict(algorithm='NPG',system=system,k=rank,stage=stage,last_policy_change_fro=change,**q))
                if stage==1024:break
                z=targets(s,k,CFG['H'])['ZH']
                ck=k-CFG['eta']*(k+(z if rank==12 else trunc(z,rank)))
                change=float(np.linalg.norm(ck-k));k=ck
            pop[-1].update(last64_gap_min=float(min(last64)),last64_gap_max=float(max(last64)),
                           converged_policy=change<1e-9)
            ck,_=dare(s['A'],s['B'] if rank==12 else trunc(s['B'],rank),s['Q'],s['R'])
            pop.append(dict(algorithm='CE',system=system,k=rank,stage=0,converged_policy=True,**assess(s,ck)))
    csvwrite(report/'e2_adaptive_ranks_coverage.csv',adaptive)
    csvwrite(report/'e1_paired_gap_ratios.csv',paired)
    csvwrite(report/'e2_ce_summary.csv',ce_summary)
    csvwrite(report/'e2_population_diagnostic.csv',pop)
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(7.1,2.8))
    for budget in CFG['ce_budgets']:
        curve=[]
        for rank in KS:
            mode='dense' if rank==12 else 'k'+str(rank)
            curve.append(next(x['median'] for x in ce_summary if x['N']==budget and x['mode']==mode))
        axs[0].plot(KS,curve,'o-',ms=3,label=str(budget+CFG['burn']))
    for mode,label,color in [('k2','Fixed k=2','#b38c30'),('adaptive1.0','Frozen threshold','#1966a6'),('dense','Dense','#b53b38')]:
        curve=[next(x['median'] for x in ce_summary if x['N']==budget and x['mode']==mode) for budget in CFG['ce_budgets']]
        axs[1].plot([b+CFG['burn'] for b in CFG['ce_budgets']],curve,'o-',ms=3,label=label,color=color)
    envelope=[min(x['median'] for x in ce_summary if x['N']==b and not x['mode'].startswith('adaptive') and x['median'] is not None) for b in CFG['ce_budgets']]
    axs[1].plot([b+CFG['burn'] for b in CFG['ce_budgets']],envelope,'k:',label='Fixed-k median envelope')
    axs[0].set(xlabel='Truncation order k',ylabel=r'Final $J-J^\star$',yscale='log',title='(a) CE, shared data within each budget')
    axs[1].set(xlabel='Total transitions',ylabel=r'Final $J-J^\star$',xscale='log',yscale='log',title='(b) CE, frozen threshold')
    for ax in axs:ax.legend(fontsize=7)
    fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(report/('figureS1_ce_effective_rank.'+ext))
    plt.close(fig)
    all_sampling=[]
    for phase in ['preflight','calibration','formal']:
        for p in sorted((OUT/phase).glob('*.json')):
            d=json.loads(p.read_text());all_sampling.append(dict(phase=phase,id=d['spec']['id'],
                actual_transitions=d['actual_transitions'],seconds=d['seconds'],status=d.get('status','complete')))
    csvwrite(report/'all_new_sampling_accounting.csv',all_sampling)
    supplements=dict(adaptive=adaptive,e1_paired_ratios=paired,
        total_new_transitions=sum(r['actual_transitions'] for r in all_sampling),
        total_complete_actor_paths=sum(d.get('status')=='complete' for d in raw if d['spec']['algorithm']!='CE'),
        p0_supplied=4.,chi_supplied=8.,identity=identity(),provenance=provenance(),
        threshold_file_sha256=sha(OUT/'threshold_frozen.json'),
        caveat='Empirical coverage over dependent stages is descriptive; no probability guarantee is inferred.')
    atomic_json(report/'supplement.json',supplements)
    checks={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.suffix in
            ['.json','.npz','.csv','.svg','.png','.psv'] and p.name!='artifact_sha256.json'}
    atomic_json(OUT/'artifact_sha256.json',checks)
    archive=OUT.parent.parent/'exports/final-story-20261024.tar.gz'
    with tarfile.open(archive,'w:gz') as bundle:bundle.add(OUT,arcname=OUT.name)
    atomic_json(archive.with_suffix('.receipt.json'),dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,
        report_sha256=sha(report/'summary.json'),manifest_sha256=sha(OUT/'artifact_sha256.json')))
    preview=OUT.parent.parent/'exports/final-story-20261024-preview.tar.gz'
    with tarfile.open(preview,'w:gz') as bundle:
        for name in ['summary.json','supplement.json','figure1_strict_rank.png','figure2_effective_rank.png','figureS1_ce_effective_rank.png',
                     'e2_summary.csv','e2_ce_summary.csv','e3_small_table.csv','e2_population_diagnostic.csv',
                     'system_tails_certificates.csv','effective_ranks_operational_c1.csv']:
            bundle.add(report/name,arcname=name)
    print(json.dumps(dict(status='COMPLETE',preview_sha256=sha(preview),archive_bytes=archive.stat().st_size,
                         adaptive=adaptive,total_new_transitions=supplements['total_new_transitions'])),flush=True)


if __name__=='__main__':main()
