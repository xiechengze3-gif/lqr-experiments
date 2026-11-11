"""Freeze the formal common grid using completed pilot resource measurements."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def read(p):return json.loads(p.read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--inspect-only',action='store_true');a=p.parse_args()
    cfg=read(a.manifest);out=Path(cfg['output']);rows=[]
    # Common evaluation grid, fixed before any formal data are collected.
    budgets=[12288,14336,24576,28672,40960,65536,81920,131072,
             196608,262144,327680,458752,655360,786432,1048576]
    pilot_seconds=[];estimates=[]
    ledger={}
    for line in (out/'accounting/pilot-and-preflight.psv').read_text().splitlines():
        f=line.split('|')
        if len(f)>=11 and '.' not in f[1]:ledger[f[0]]=(f[2],int(f[4] or 0))
    for rank in cfg['ranks']:
        rr=[read(out/'raw'/f'ce-r{rank:03d}-s{s:04d}.json') for s in cfg['pilot_seeds']]
        collection=[sum(q['collector_seconds'] for q in r['timings_this_invocation']) for r in rr]
        solve=[statistics.mean(q['solve_and_save_seconds'] for q in r['timings_this_invocation']) for r in rr]
        startup=[max(0,ledger[r['slurm_job_id']][1]-r['seconds_this_invocation']) for r in rr]
        prediction=[c+len(budgets)*v+s for c,v,s in zip(collection,solve,startup)]
        estimates+=prediction;pilot_seconds += [ledger[r['slurm_job_id']][1] for r in rr]
        rows.append(dict(rank=rank,pilot_elapsed_seconds_max=max(ledger[r['slurm_job_id']][1] for r in rr),
            collector_seconds_mean=statistics.mean(collection),solve_per_prefix_seconds_mean=statistics.mean(solve),
            predicted_formal_seconds_mean=statistics.mean(prediction),predicted_formal_seconds_max=max(prediction)))
    past_preflight=read(out/'accounting/preflight-settlement/own_settlement_summary.json')
    assert past_preflight['all_measured_jobs_settled'] and past_preflight['matched_own_records']==1
    assert abs(past_preflight['displayed_rounded_settled_SU_sum']-544/3600)<.011
    spent_bound=544/3600+sum(pilot_seconds)/3600+.25
    # Hard wall limits, measured one SU/hour. Archive jobs use 1G (one core).
    wall_minutes={str(rank):(17 if rank==cfg['n'] else 21) for rank in cfg['ranks']}
    future_bound=30*sum(wall_minutes.values())/60+2+8*10/60+10/60
    predicted_formal_SU=sum(estimates)/len(cfg['pilot_seeds'])*len(cfg['confirm_seeds'])/3600
    result=dict(status='inspected' if a.inspect_only else 'frozen',budgets=budgets,initial_gap=cfg['initial_gap'],ranks=cfg['ranks'],
        relative_targets=cfg['relative_targets'],seeds=cfg['confirm_seeds'],pilot_resource_measurements=rows,
        predicted_formal_SU=predicted_formal_SU,prior_spend_upper_bound_SU=spent_bound,
        future_all_jobs_wall_limit_SU_bound=future_bound,initial_total_SU_bound=spent_bound+future_bound,
        total_SU_cap=cfg['resources']['total_SU_cap'],manual_resume_remaining_SU_allowance=cfg['resources']['total_SU_cap']-spent_bound-future_bound,
        formal_wall_minutes_by_rank=wall_minutes,formal_tasks=150,max_concurrency=25,concurrency_per_rank=5,formal_report_wall_minutes=120,
        archive_group_size_seeds=5,archive_formal_groups=6,
        AMS_basis='Preflight real AMS settlement 0.15SU for544s; pilot array own submission precharge8.333333SU for25x20min',
        formal_grid_basis='Pilot hit intervals; same common grid for every rank/method; all pilot prefixes and failures retained',
        plan_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    print(json.dumps(result,indent=2))
    if not a.inspect_only:
        assert read(out/'report-pilot/audit.json')['status']=='PASS'
        assert spent_bound+future_bound<cfg['resources']['total_SU_cap']
        assert all(q['predicted_formal_seconds_max']*1.1<wall_minutes[str(q['rank'])]*60 for q in rows), 'Require10% runtime margin at every rank'
        path=out/'formal_plan.json';assert not path.exists()
        path.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
