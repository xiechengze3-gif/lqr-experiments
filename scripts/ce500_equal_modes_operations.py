"""Receipt-based bounded submission; stdlib only, safe for the login node."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8');temp.replace(p)


def ledger(out,ids,label):
    txt=subprocess.check_output(['sacct','-j',','.join(ids),'-n','-P',
        '--format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU,NNodes,TimelimitRaw,MaxRSS'],text=True)
    (out/'accounting').mkdir(exist_ok=True);(out/'accounting'/(label+'.psv')).write_text(txt)
    rows=[]
    for line in txt.splitlines():
        c=line.split('|')
        if len(c)>=12 and c[0] and '.' not in c[1]:
            rows.append(dict(raw_id=c[0],job_id=c[1],state=c[2],elapsed=int(c[4] or 0),cpus=int(c[5] or 0),tres=c[7]))
    assert rows and all(q['state']=='COMPLETED' for q in rows),rows
    return rows


def settlement(out,rows,label):
    ids={q['raw_id'] for q in rows};text=subprocess.check_output(['myproject','-j','132685389143'],text=True)
    selected=[]
    for line in text.splitlines():
        c=[v.strip() for v in line.split('|')]
        if len(c)>9 and c[1]=='132685389143' and c[2] in ids:
            selected.append(dict(job=c[2],array_index=c[3],wall_seconds=int(c[7]),slots=int(c[8]),SU=float(c[9])))
    write(out/'accounting'/(label+'-AMS.json'),dict(records=selected,matched=len(selected),
          requested_own_ids=sorted(ids),rounded_settled_SU=sum(q['SU'] for q in selected),
          pending_settlement_ids=sorted(ids-{q['job'] for q in selected})))
    return selected


def submit(cfg,release,key,args,receipt):
    assert key not in receipt['jobs']
    receipt['status']='submitting';write(Path(cfg['output'])/receipt['filename'],receipt)
    cmd=['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short','--exclude=c136,c294']+args
    job=subprocess.check_output(cmd,cwd=release,text=True).strip();assert job.isdigit(),job
    receipt['jobs'][key]=job;receipt['status']='submitted';write(Path(cfg['output'])/receipt['filename'],receipt)
    return job


def pilot(cfg,release):
    out=Path(cfg['output']);assert read(out/'preflight.json')['status']=='PASS'
    filename='submission-pilot.json';assert not (out/filename).exists(),'Inspect existing submission; never replay blindly'
    prior=read(out/'submission-preflight.json');rows=ledger(out,[prior['job']],'preflight')
    ams=settlement(out,rows,'preflight')
    benches=[read(out/'diagnostics/benchmark/raw'/f'ce-r{r:03d}-s9002.json') for r in (cfg['ranks'][0],cfg['n'])]
    predicted=max(sum(t['collector_seconds'] for t in b['timings_this_invocation'])/131072*max(cfg['pilot_budgets'])+
                  max(t['solve_and_save_seconds'] for t in b['timings_this_invocation'])*len(cfg['pilot_budgets']) for b in benches)
    assert predicted*1.15+60<1200,(predicted,'Pilot wall limit insufficient')
    receipt=dict(status='new',filename=filename,jobs={},epoch=time.time(),tasks=25,
        wall_minutes=20,maximum_requested_SU=25/3,preflight_allocated_core_hours=sum(q['elapsed']*q['cpus']/3600 for q in rows),
        predicted_pilot_task_seconds_upper=predicted,preflight_settled_records=len(ams),total_SU_cap=60)
    job=submit(cfg,release,'pilot',['-t','00:20:00','--array=0-24%25','-J','ce500-eqm-pilot',
        '-o',str(out/'logs/pilot-%A_%a.out'),'slurm/ce500_equal_modes.sbatch','task','pilot'],receipt)
    submit(cfg,release,'pilot_report',['-t','00:30:00','--dependency=afterok:'+job,'-J','ce500-eqm-pilot-report',
        '-o',str(out/'logs/pilot-report-%j.out'),'slurm/ce500_equal_modes.sbatch','pilot'],receipt)
    print(json.dumps(receipt,indent=2))


def formal(cfg,release):
    out=Path(cfg['output']);assert read(out/'report-pilot/audit.json')['status']=='PASS'
    filename='submission-formal.json';assert not (out/filename).exists(),'Inspect existing submission; never replay blindly'
    prep=read(out/'submission-preflight.json');pilot_receipt=read(out/'submission-pilot.json')
    rows=ledger(out,[prep['job']]+list(pilot_receipt['jobs'].values()),'before-formal')
    ams=settlement(out,rows,'before-formal')
    assert ams,'Current-campaign AMS confirmation required before formal submission'
    assert all(q['slots']==1 for q in ams),'Measured billing differs from one SU/hour'
    by_task={int(q['job_id'].split('_')[-1]):q for q in rows if '_' in q['job_id']}
    assert len(by_task)==25
    bootstrap=read(out/'report-pilot/summary.json')
    round256=lambda n: int(math.ceil(n/256))*256
    grids={};timings=[];brackets=[];maximum=cfg['maximum_OLS_samples']
    for ir,rank in enumerate(cfg['ranks']):
        rr=[read(out/'raw'/f'ce-r{rank:03d}-s{s:04d}.json') for s in cfg['pilot_seeds']]
        base=cfg['pilot_budgets'];primary='dense' if rank==cfg['n'] else 'truncated'
        ranges=[];predictions=[]
        for target in cfg['relative_targets']:
            req=next(q for q in bootstrap['requirements'] if q['rank']==rank and q['method']==primary and q['relative_target']==target)
            if req['N_hat_90'] is not None:
                upper=int(req['N_hat_90'])-cfg['burn'];i=base.index(upper);lower=base[max(0,i-1)]
                extrapolated=False
            else:
                gaps=[next(q['gap'] if q['stable'] else math.inf for q in raw['records'] if q['method']==primary and q['ols_samples']==base[-1]) for raw in rr]
                assert all(math.isfinite(g) for g in gaps),'Pilot stability failure requires separate review'
                upper=max(base[-1],round256(base[-1]*statistics.median(gaps)/target));lower=base[-1];extrapolated=True
                # Explicit pre-formal budget amendment; no old raw results or checkpoints changed.
                maximum=max(maximum,min(4194304,round256(upper*cfg['formal_threshold_buffer'])))
            # Pilot-only local approximation N*gap=C0+C1/N selects evaluation points,
            # never an interpolated reported threshold. Formal seeds remain independent.
            centers=[]
            for raw in rr:
                points=[q for q in raw['records'] if q['method']==primary and q['stable']][-3:]
                assert len(points)==3
                xs=[1/q['ols_samples'] for q in points];ys=[q['ols_samples']*q['gap'] for q in points]
                mx,my=statistics.mean(xs),statistics.mean(ys)
                slope=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)
                c0=max(0,my-slope*mx);c1=max(0,slope)
                centers.append((c0+math.sqrt(c0*c0+4*target*c1))/(2*target))
            center=max(centers);predictions.append(center)
            ranges.append((.8*center,1.25*center))
            maximum=max(maximum,min(4194304,round256(center*1.4)))
            brackets.append(dict(rank=rank,target=target,lower=lower,upper=upper,extrapolated=extrapolated,
                                 pilot_predicted_center=center,predicted_centers_by_seed=centers))
        max_n=min(maximum,max(cfg['common_diagnostic_OLS_samples'],round256(max(predictions)*1.4)))
        budget={cfg['common_diagnostic_OLS_samples'],max_n}
        for lower,upper in ranges:
            value=float(lower);end=min(max_n,round256(upper))
            while value<end:
                budget.add(round256(value));value*=1.08
            budget.add(end)
        grids[str(rank)]=sorted(v for v in budget if 2048<=v<=max_n)
        rates=[];solves=[];startup=[]
        for j,raw in enumerate(rr):
            t=raw['timings_this_invocation'];rates.append(sum(q['collector_seconds'] for q in t)/max(base))
            solves.append(sum(q['solve_and_save_seconds'] for q in t)/len(t))
            startup.append(max(0,by_task[ir*5+j]['elapsed']-raw['seconds_this_invocation']))
        prediction=max(rates)*max_n+max(solves)*len(grids[str(rank)])+max(startup)
        wall=int(math.ceil((prediction*1.2+60)/60));wall=max(5,wall)
        timings.append(dict(rank=rank,max_OLS_samples=max_n,prefixes=len(grids[str(rank)]),
                            predicted_seconds_upper=prediction,formal_wall_minutes=wall,
                            startup_seconds_max=max(startup),collector_seconds_per_transition_max=max(rates),
                            solve_seconds_per_prefix_max=max(solves)))
    spent=sum(q['elapsed']*q['cpus']/3600 for q in rows)
    requested=30*sum(q['formal_wall_minutes'] for q in timings)/60
    recovery=5*max(q['formal_wall_minutes'] for q in timings)/60
    shard_wall=30;aggregate_wall=15
    total=spent+requested+recovery+6*shard_wall/60+aggregate_wall/60+cfg['resources']['archive_wall_minutes']/60
    assert total<cfg['resources']['total_SU_cap'],(total,timings,'Budget review required; no formal jobs submitted')
    concurrency=[8,8,14,30,30]
    plan=dict(status='frozen_before_formal_sampling',budgets_by_rank=grids,seeds=cfg['confirm_seeds'],
        initial_gap=1,relative_targets=cfg['relative_targets'],pilot_brackets=brackets,resource_measurements=timings,
        prior_allocated_core_hours=spent,future_wall_limit_SU=requested,recovery_SU_bound=recovery,
        total_worst_case_SU_bound=total,total_SU_cap=60,maximum_OLS_samples=maximum,
        budget_amendment=dict(original_maximum_OLS_samples=cfg['maximum_OLS_samples'],new_maximum_OLS_samples=maximum,
            reason='Pilot-censored targets require extrapolated grid; frozen before formal data; same sampler and SU cap'),
        grid_refinement_amendment=dict(original_ratio=cfg['formal_grid_ratio'],critical_grid_ratio=1.08,
            center_model='N*gap=C0+C1/N fitted separately on last three stable pilot prefixes; maximum predicted N over five seeds',
            critical_interval_factors=[0.8,1.25],maximum_buffer=1.4,
            omitted_redundant_formal_coarse_prefixes=[8192,32768],
            reason='Resolve adjacent gain ratios using tighter spacing near thresholds; only actual formal tested budgets define N90'),
        concurrency_by_rank={str(q['rank']):c for q,c in zip(timings,concurrency)},
        resource_only_amendment=dict(original_max_concurrency=30,new_max_concurrency=sum(concurrency),
            reason='More independent one-core tasks in parallel; same per-task CPU, memory, threads and total SU bound'),
        audit_shards=6,audit_shard_wall_minutes=shard_wall,aggregate_report_wall_minutes=aggregate_wall,
        operation_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    assert not (out/'formal_plan.json').exists();write(out/'formal_plan.json',plan)
    receipt=dict(status='new',filename=filename,jobs={},epoch=time.time(),tasks=150,plan=plan)
    arrays=[]
    for ir,q in enumerate(timings):
        job=submit(cfg,release,'rank_'+str(q['rank']),['-t',str(q['formal_wall_minutes']),
            '--array='+str(ir*30)+'-'+str((ir+1)*30-1)+'%'+str(concurrency[ir]),'-J','ce500-eqm-r'+str(q['rank']),
            '-o',str(out/'logs/confirm-%A_%a.out'),'slurm/ce500_equal_modes.sbatch','task','confirm'],receipt)
        arrays.append(job)
    audit_job=submit(cfg,release,'formal_audits',['-t',str(shard_wall),'--array=0-5%6',
        '--dependency=afterok:'+':'.join(arrays),'-J','ce500-eqm-audit',
        '-o',str(out/'logs/audit-%A_%a.out'),'slurm/ce500_equal_modes.sbatch','audit-shard'],receipt)
    report_job=submit(cfg,release,'formal_report',['-t',str(aggregate_wall),
        '--dependency=afterok:'+audit_job,'-J','ce500-eqm-final-report',
        '-o',str(out/'logs/confirm-report-%j.out'),'slurm/ce500_equal_modes.sbatch','confirm'],receipt)
    submit(cfg,release,'archive',['-t',str(cfg['resources']['archive_wall_minutes']),
        '--dependency=afterok:'+report_job,'-J','ce500-eqm-archive',
        '-o',str(out/'logs/archive-%j.out'),'slurm/ce500_equal_modes_archive.sbatch'],receipt)
    print(json.dumps(receipt,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['pilot','formal']);p.add_argument('--manifest',type=Path,required=True)
    a=p.parse_args();cfg=read(a.manifest);release=a.manifest.resolve().parents[1]
    (pilot if a.mode=='pilot' else formal)(cfg,release)


if __name__=='__main__':main()
