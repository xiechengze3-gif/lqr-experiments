"""Bounded, receipt-based submission of fixed random-A CE; login-node stdlib."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(p)


def ledger(cfg,ids,label):
    out=Path(cfg['output']);dest=out/'accounting';dest.mkdir(exist_ok=True)
    txt=subprocess.check_output(['sacct','-j',','.join(ids),'-n','-P',
        '--format=JobIDRaw,JobID,State,ElapsedRaw,AllocCPUS,AllocTRES,MaxRSS'],text=True)
    (dest/(label+'.psv')).write_text(txt)
    rows=[]
    for line in txt.splitlines():
        c=line.split('|')
        if len(c)>=7 and c[0] and '.' not in c[1]:
            rows.append(dict(raw_id=c[0],job_id=c[1],state=c[2],elapsed=int(c[3] or 0),
                             cpus=int(c[4] or 0),tres=c[5]))
    assert rows and all(q['state']=='COMPLETED' for q in rows),rows
    account=cfg['resources']['account'];wanted={q['raw_id'] for q in rows}
    ams_text=subprocess.check_output(['myproject','-j',account],text=True)
    matches=[]
    for line in ams_text.splitlines():
        c=[v.strip() for v in line.split('|')]
        if len(c)>9 and c[1]==account and c[2] in wanted:
            matches.append(dict(job=c[2],array_index=c[3],wall_seconds=int(c[7]),
                                slots=int(c[8]),SU=float(c[9])))
    write(dest/(label+'-AMS.json'),dict(records=matches,requested_own_ids=sorted(wanted),
        rounded_settled_SU=sum(q['SU'] for q in matches),
        pending_settlement_ids=sorted(wanted-{q['job'] for q in matches})))
    return rows,matches


def verify_billing(cfg,rows,ams,label):
    if ams:
        assert all(q['slots']==1 for q in ams)
        return dict(basis='current-campaign AMS settled records',records=ams)
    prior,settled=ledger(cfg,['20219192'],label+'-same-resource-reference')
    assert len(prior)==1 and prior[0]['cpus']==1 and 'billing=1,' in prior[0]['tres']
    assert settled and all(q['slots']==1 for q in settled)
    assert all(q['cpus']==1 and 'billing=1,' in q['tres'] and 'mem=2G,' in q['tres'] for q in rows)
    proof=dict(basis='current same-account 1CPU/2GiB settled AMS reference; current campaign settlement pending',
        reference_job='20219192',reference_records=settled,
        current_unsettled_ids=[q['raw_id'] for q in rows],
        allocated_core_hours_pending_settlement=sum(q['elapsed']*q['cpus']/3600 for q in rows))
    write(Path(cfg['output'])/'accounting'/(label+'-billing-basis.json'),proof)
    return proof


def submit(cfg,release,receipt,key,opts):
    assert key not in receipt['jobs']
    receipt['status']='submitting';write(Path(cfg['output'])/receipt['filename'],receipt)
    cmd=['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short',
         '--exclude='+','.join(cfg['resources']['excluded_hosts'])]+opts
    job=subprocess.check_output(cmd,cwd=release,text=True).strip();assert job.isdigit(),job
    receipt['jobs'][key]=job;receipt['status']='submitted'
    write(Path(cfg['output'])/receipt['filename'],receipt)
    return job


def pilot(cfg,release):
    out=Path(cfg['output']);assert read(out/'preflight.json')['status']=='PASS'
    filename='submission-pilot.json';assert not (out/filename).exists(),'Inspect receipt before any replay'
    rows,ams=ledger(cfg,[read(out/'submission-preflight.json')['job']],'preflight')
    billing=verify_billing(cfg,rows,ams,'preflight')
    predictions=[]
    for rank in (cfg['ranks'][0],cfg['n']):
        raw=read(out/'diagnostics/benchmark/raw'/f'ce-r{rank:03d}-s9002.json')
        ts=raw['timings_this_invocation']
        prediction=max(t['collector_seconds']/t['additional_samples'] for t in ts)*max(cfg['pilot_budgets'])
        prediction+=max(t['solve_and_save_seconds'] for t in ts)*len(cfg['pilot_budgets'])+30
        predictions.append(prediction)
    wall=max(10,math.ceil((max(predictions)*1.5+60)/60))
    assert wall<=cfg['resources']['pilot_provisional_wall_minutes'],(wall,predictions)
    count=len(cfg['ranks'])*len(cfg['pilot_seeds'])
    spent=sum(q['elapsed']*q['cpus']/3600 for q in rows)
    bound=spent+count*wall/60+cfg['resources']['report_wall_minutes']/60
    assert bound<cfg['resources']['total_SU_cap']
    receipt=dict(status='new',filename=filename,jobs={},epoch=time.time(),tasks=count,
        wall_minutes=wall,predicted_task_seconds_upper=max(predictions),
        pilot_requested_SU_bound=count*wall/60,total_SU_cap=cfg['resources']['total_SU_cap'],billing_basis=billing)
    job=submit(cfg,release,receipt,'pilot',['-t',str(wall),'--array=0-'+str(count-1)+'%25',
        '-J','ce500-rnda-pilot','-o',str(out/'logs/pilot-%A_%a.out'),
        'slurm/ce500_random_a.sbatch','task','--phase','pilot'])
    submit(cfg,release,receipt,'pilot_report',['-t',str(cfg['resources']['report_wall_minutes']),
        '--dependency=afterok:'+job,'-J','ce500-rnda-pilot-report',
        '-o',str(out/'logs/pilot-report-%j.out'),'slurm/ce500_random_a.sbatch','pilot'])
    print(json.dumps(receipt,indent=2))


def formal(cfg,release):
    out=Path(cfg['output']);assert read(out/'report-pilot/audit.json')['status']=='PASS'
    filename='submission-formal.json';assert not (out/filename).exists(),'Inspect receipt before any replay'
    ids=[read(out/'submission-preflight.json')['job']]+list(read(out/'submission-pilot.json')['jobs'].values())
    rows,ams=ledger(cfg,ids,'before-formal')
    billing=verify_billing(cfg,rows,ams,'before-formal')
    by_task={int(q['job_id'].split('_')[-1]):q for q in rows if '_' in q['job_id']}
    maximum=cfg['maximum_OLS_samples'];round256=lambda x:int(math.ceil(x/256))*256
    grids={};measurements=[];centers=[]
    for ir,rank in enumerate(cfg['ranks']):
        raws=[read(out/'raw'/f'ce-r{rank:03d}-s{s:04d}.json') for s in cfg['pilot_seeds']]
        predictions=[];primary_predictions=[]
        for method in ('dense','truncated'):
            if rank==cfg['n'] and method=='truncated':continue
            for target in cfg['relative_targets']:
                by_seed=[]
                for raw in raws:
                    points=[q for q in raw['records'] if q['method']==method and q['stable']][-3:]
                    assert len(points)>=2,'Need stable pilot prefixes to plan'
                    xs=[1/q['ols_samples'] for q in points]
                    ys=[q['ols_samples']*q['gap'] for q in points]
                    mx,my=statistics.mean(xs),statistics.mean(ys)
                    slope=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)
                    c0=max(0,my-slope*mx);c1=max(0,slope)
                    by_seed.append((c0+math.sqrt(c0*c0+4*target*c1))/(2*target))
                center=max(by_seed);predictions.append(center)
                if method==('dense' if rank==cfg['n'] else 'truncated'):primary_predictions.append(center)
                centers.append(dict(rank=rank,method=method,target=target,predicted_center=center,seed_centers=by_seed))
        max_n=min(maximum,max(cfg['common_diagnostic_OLS_samples'],
                              round256(max(primary_predictions)*cfg['formal_threshold_buffer'])))
        grid={2048,8192,32768,cfg['common_diagnostic_OLS_samples'],max_n}
        for center in predictions:
            value=max(2048,.8*center);end=min(max_n,round256(1.3*center))
            while value<end:
                grid.add(round256(value));value*=cfg['formal_grid_ratio']
            grid.add(end)
        grids[str(rank)]=sorted(v for v in grid if 2048<=v<=max_n)
        rates=[];solves=[];startup=[]
        for j,raw in enumerate(raws):
            ts=raw['timings_this_invocation']
            rates.append(sum(q['collector_seconds'] for q in ts)/max(cfg['pilot_budgets']))
            solves.append(max(q['solve_and_save_seconds'] for q in ts))
            startup.append(max(0,by_task[ir*len(raws)+j]['elapsed']-raw['seconds_this_invocation']))
        pred=max(rates)*max_n+max(solves)*len(grids[str(rank)])+max(startup)
        wall=max(8,int(math.ceil((1.5*pred+90)/60)))
        measurements.append(dict(rank=rank,max_OLS_samples=max_n,prefixes=len(grids[str(rank)]),
            predicted_seconds_upper=pred,formal_wall_minutes=wall,
            collector_seconds_per_transition_max=max(rates),solve_seconds_per_prefix_max=max(solves),
            startup_seconds_max=max(startup)))
    spent=sum(q['elapsed']*q['cpus']/3600 for q in rows)
    requested=len(cfg['confirm_seeds'])*sum(q['formal_wall_minutes'] for q in measurements)/60
    recovery=cfg['resources']['manual_resumes_overall_maximum']*max(q['formal_wall_minutes'] for q in measurements)/60
    audits=cfg['resources']['audit_shards']*cfg['resources']['audit_wall_minutes']/60
    total=spent+requested+recovery+audits+cfg['resources']['report_wall_minutes']/60+.5
    plan=dict(status='frozen_before_formal_sampling',budgets_by_rank=grids,seeds=cfg['confirm_seeds'],
        initial_gap=1,relative_targets=cfg['relative_targets'],pilot_centers=centers,billing_basis=billing,
        budget_scope_amendment=dict(primary='full-rank dense versus each low-rank truncated',
            max_by_rank='1.35 times pilot-predicted primary 0.05 crossing, at least common diagnostic and at most hard maximum',
            dense='Paired dense retained at every prefix; add dense crossings within this frozen maximum; otherwise not reached',
            reason='Pilot-only planning controls the 60 SU cap; initial request explicitly allows censored endpoints; never change based on formal outcomes'),
        resource_measurements=measurements,prior_allocated_core_hours=spent,
        formal_requested_SU_bound=requested,recovery_SU_bound=recovery,
        total_worst_case_SU_bound=total,total_SU_cap=cfg['resources']['total_SU_cap'],
        maximum_OLS_samples=maximum,operation_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        grid_rule='1.15 geometric spacing on [0.8,1.3] times pilot-only predicted crossing, both methods and targets; no interpolation of reported thresholds')
    assert not (out/'formal_plan.json').exists()
    if total>=cfg['resources']['total_SU_cap']:
        write(out/'formal_plan_budget_review_required.json',plan)
        raise RuntimeError('Worst-case submission bound exceeds cap; no formal sampling submitted')
    write(out/'formal_plan.json',plan)
    receipt=dict(status='new',filename=filename,jobs={},epoch=time.time(),tasks=len(cfg['ranks'])*len(cfg['confirm_seeds']),plan=plan)
    arrays=[];size=len(cfg['confirm_seeds'])
    for ir,q in enumerate(measurements):
        job=submit(cfg,release,receipt,'rank_'+str(q['rank']),['-t',str(q['formal_wall_minutes']),
            '--array='+str(ir*size)+'-'+str((ir+1)*size-1)+'%'+str(max(1,cfg['resources']['max_concurrency']//len(cfg['ranks']))),
            '-J','ce500-rnda-r'+str(q['rank']),'-o',str(out/'logs/confirm-%A_%a.out'),
            'slurm/ce500_random_a.sbatch','task','--phase','confirm'])
        arrays.append(job)
    audit=submit(cfg,release,receipt,'formal_audits',['-t',str(cfg['resources']['audit_wall_minutes']),
        '--array=0-'+str(cfg['resources']['audit_shards']-1)+'%6','--dependency=afterok:'+':'.join(arrays),
        '-J','ce500-rnda-audit','-o',str(out/'logs/audit-%A_%a.out'),
        'slurm/ce500_random_a.sbatch','audit-shard'])
    submit(cfg,release,receipt,'formal_report',['-t',str(cfg['resources']['report_wall_minutes']),
        '--dependency=afterok:'+audit,'-J','ce500-rnda-report','-o',str(out/'logs/confirm-report-%j.out'),
        'slurm/ce500_random_a.sbatch','confirm'])
    print(json.dumps(receipt,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['pilot','formal']);p.add_argument('--manifest',type=Path,required=True)
    args=p.parse_args();cfg=read(args.manifest)
    (pilot if args.mode=='pilot' else formal)(cfg,args.manifest.resolve().parents[1])


if __name__=='__main__':main()
