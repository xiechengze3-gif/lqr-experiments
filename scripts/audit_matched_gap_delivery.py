"""Independent budget arithmetic and real Slurm provenance from saved results."""
import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def audit(root,accounting,destination):
    cfg=read(root/'resolved_config.json');jobs={}
    for line in accounting.read_text(encoding='utf-8-sig').splitlines():
        f=line.strip().split('|')
        if len(f)<11 or not f[0] or '.' in f[1]:continue
        assert f[0] not in jobs
        jobs[f[0]]=dict(real_job_id=f[0],array_task_id=f[1],state=f[2],elapsed_seconds=int(f[4] or 0),allocated_CPUs=int(f[5] or 0))
    recoveries=[read(p) for p in sorted((root/'resource_adjustments').glob('npg-recovery-*/recovery_request.json'))]
    recovery_map={(d['route'],d['phase'],d['rank'],d['seed']):d for d in recoveries}
    assert len(recovery_map)==len(recoveries)
    pairs=[];totals=[];main_ids=set();records_checked=0;valid_timeout_outputs=[];formal={}
    for route in ('npg','pi'):
        folder=root/route;c=read(folder/'resolved_config.json')
        increments=[c['burn']+(n+1)*c['horizon'] for n,length in c['schedule_segments'] for _ in range(length)] if route=='npg' else [c['burn']+n for n in c['batch_schedule']]
        budgets=[0]+list(itertools.accumulate(increments))
        for phase in ('pilot','confirm'):
            plan=[(rank,seed) for seed in c[phase+'_seeds'] for rank in c['ranks']]
            physical=charged=0
            submission=read(folder/(phase+'_submission.json'))
            for index,(rank,seed) in enumerate(plan):
                stem=f'{route}-r{rank:03d}-s{seed:04d}';path=folder/'raw'/(stem+'.json')
                d=read(path);receipt=read(folder/'task_receipts'/f'{phase}-{index:03d}.json')
                if phase=='confirm':formal[route,rank,seed]=d
                assert d['rank']==receipt['rank']==rank and d['seed']==receipt['seed']==seed
                assert receipt['route']==route and receipt['phase']==phase and d['identity']==c['identity']
                assert len(d['records'])==2*len(budgets)
                for method in ('dense','truncated'):
                    group=sorted([q for q in d['records'] if q['method']==method],key=lambda q:q['stage'])
                    assert [q['stage'] for q in group]==list(range(len(budgets)))
                    previous=0
                    for q,budget in zip(group,budgets):
                        assert q['transitions']==budget
                        assert previous<=q['actual_transitions']<=budget
                        if q['observed']:
                            assert q['actual_transitions']==budget,('An interrupted collector needs explicit additional accounting',route,rank,seed,q)
                        if not q['observed']:assert q['failure']=='prior_failure'
                        previous=q['actual_transitions'];records_checked+=1
                    assert previous==d['algorithm_actual_transitions'][method]
                if all(q['observed'] and q['stable'] for q in d['records']):
                    expected=budgets[-1] if rank==100 else 2*budgets[-1]-increments[0]
                    assert d['physical_transitions']==expected,(route,rank,seed,d['physical_transitions'],expected)
                job=jobs[str(receipt['slurm_job_id'])]
                expected_root=submission['pilot_array'] if phase=='pilot' else submission['arrays'][1 if route=='npg' and rank==100 else 0]
                bundled=phase=='confirm' and submission.get('task_layout')=='seed_bundle'
                expected_index=c[phase+'_seeds'].index(seed) if bundled else index
                recovery=recovery_map.get((route,phase,rank,seed))
                if recovery is not None:
                    assert not bundled and recovery['source_and_schedule_unchanged']
                    assert recovery['max_recovery_attempts']==1 and recovery['original_array']==expected_root
                    original=jobs[recovery['original_real_job_id']]
                    assert original['state']=='TIMEOUT' and original['array_task_id']==f'{expected_root}_{index}'
                    saved=root/'resource_adjustments'/('npg-recovery-'+recovery['original_real_job_id'])
                    assert sha(saved/'original-checkpoint.npz')==recovery['checkpoint_sha256']
                    before=read(saved/'original-checkpoint-meta.json')
                    assert before['rows']==[q for q in d['records'] if q['stage']<=recovery['checkpoint_stage']]
                    assert before['physical']==recovery['original_committed_physical_transitions']
                    expected_root=recovery['recovery_array']
                assert job['array_task_id']==f'{expected_root}_{expected_index}'
                assert job['state'] in ('COMPLETED','TIMEOUT'),('Explicit interruption accounting is required before claiming exact global physical counts',job)
                if job['state']=='TIMEOUT':
                    # Raw output is committed only after all stage checkpoints,
                    # policies and (for PI) critics; no collection follows it.
                    # Completeness does not require success or stability:
                    # legitimate algorithm failures remain in the denominator.
                    assert all(len([q for q in d['records'] if q['method']==m])==len(budgets) for m in ('dense','truncated'))
                    for kind,key in [('policies','policy_sha256')]+([('critics','critic_sha256')] if route=='pi' else []):
                        assert sha(folder/kind/(stem+'.npz'))==d[key]
                    valid_timeout_outputs.append(dict(route=route,phase=phase,rank=rank,seed=seed,**job,
                        complete_output_committed=True,raw_sha256=sha(path)))
                assert job['allocated_CPUs']==1
                if route=='pi':assert str(d['slurm_job_id'])==job['real_job_id']
                if not bundled:assert job['real_job_id'] not in main_ids
                main_ids.add(job['real_job_id'])
                physical+=d['physical_transitions'];charged+=sum(d['algorithm_actual_transitions'].values())
                pairs.append(dict(route=route,phase=phase,rank=rank,seed=seed,**job,
                    resumed_original_real_job_id=recovery['original_real_job_id'] if recovery else None,
                    resume_checkpoint_stage=recovery['checkpoint_stage'] if recovery else None,
                    seed_bundle_shared_job=bundled,
                    raw_sha256=sha(path),policy_sha256=d['policy_sha256'],
                    physical_transitions=d['physical_transitions'],algorithm_charged_transitions=sum(d['algorithm_actual_transitions'].values())))
            totals.append(dict(route=route,phase=phase,paired_tasks=len(plan),physical_transitions=physical,algorithm_charged_transitions=charged))
    assert len(pairs)==350
    expected_real_jobs=230 if read(root/'pi/confirm_submission.json').get('task_layout')=='seed_bundle' else 350
    assert len(main_ids)==expected_real_jobs
    attempts=main_ids|{q['original_real_job_id'] for q in recoveries}
    extra_upper=sum(q['extra_uncommitted_physical_transitions_bounds'][1] for q in recoveries)
    assert sum(q['recovery_reservation_core_hours'] for q in recoveries)<=10
    diagnostics=[dict(name='NPG numerical/recovery tests and maximum-batch benchmarks',physical_transitions=read(root/'npg/verification.json')['diagnostic_primitive_transitions']),
        dict(name='PI numerical/recovery tests',physical_transitions=read(root/'pi/verification.json')['primitive_transitions']),
        dict(name='PI maximum-memory verification',physical_transitions=read(root/'pi/maximum_memory_verification.json')['physical_transitions']),
        dict(name='CE raw-trajectory identification audit',physical_transitions=read(root.parent/'matched-gap-npg-pi-20261019/ce-identification-audit/audit.json')['audit_primitive_transitions'])]
    # Bound the effect of discarded work on the endpoint itself. Upper-cost
    # curves charge every affected method the complete unfinished estimator,
    # including its burn and priming block. No data or seed is removed.
    endpoint_bounds=[];execution_success_envelopes=[]
    def succeeded(q,eps):
        return bool(q['observed'] and q['stable'] and q['whole_path_stable'] and q['gap'] is not None and q['gap']<=eps)
    for route in ('npg','pi'):
        c=read(root/route/'resolved_config.json')
        for rank in c['ranks']:
            for method in ('dense','truncated'):
                curves={};by_side={}
                for side in ('lower','upper'):
                    seed_curves=[]
                    for seed in c['confirm_seeds']:
                        d=formal[route,rank,seed];rec=recovery_map.get((route,'confirm',rank,seed))
                        overhead=rec['extra_uncommitted_transitions_per_method_bounds'][method][1] if side=='upper' and rec else 0
                        seed_curves.append([(q['transitions']+(overhead if rec and q['stage']>rec['checkpoint_stage'] else 0),q)
                            for q in d['records'] if q['method']==method])
                    by_side[side]=seed_curves
                    grid=sorted({b for points in seed_curves for b,q in points})
                    curves[side]=[]
                    for budget in grid:
                        last=[max((p for p in points if p[0]<=budget),key=lambda p:p[1]['stage'])[1] for points in seed_curves]
                        curves[side].append((budget,last))
                for eps in (.1,.05):
                    estimates={}
                    for side,curve in curves.items():
                        estimates[side]=next((budget for budget,last in curve if sum(succeeded(q,eps) for q in last)>=27),None)
                    # Success can be nonmonotone along a learning trajectory.
                    # Check every possible intervening saved policy, rather
                    # than inferring robustness from the two cost endpoints.
                    grid=sorted({b for side in by_side.values() for points in side for b,q in points})
                    envelope=[]
                    for budget in grid:
                        certain=possible=0
                        for low,high in zip(by_side['lower'],by_side['upper']):
                            lo=max(i for i,(b,q) in enumerate(high) if b<=budget)
                            hi=max(i for i,(b,q) in enumerate(low) if b<=budget)
                            hits=[succeeded(low[i][1],eps) for i in range(lo,hi+1)]
                            certain+=all(hits);possible+=any(hits)
                        envelope.append((budget,certain,possible))
                        def wilson(k,n=30):
                            z=1.959963984540054;p=k/n;d=1+z*z/n
                            mid=(p+z*z/(2*n))/d
                            half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
                            return max(0.,mid-half),min(1.,mid+half)
                        execution_success_envelopes.append(dict(route=route,rank=rank,method=method,epsilon=eps,
                            transitions=budget,seeds=30,successes_certain=certain,successes_possible=possible,
                            success_rate_min=certain/30,success_rate_max=possible/30,
                            failure_rate_min=1-possible/30,failure_rate_max=1-certain/30,
                            Wilson95_lower_at_min=wilson(certain)[0],Wilson95_upper_at_max=wilson(possible)[1]))
                    possible_N=next((b for b,c,p in envelope if p>=27),None)
                    guaranteed_N=next((b for b,c,p in envelope if c>=27),None)
                    endpoint_bounds.append(dict(route=route,rank=rank,method=method,epsilon=eps,
                        N_hat_90_lower_cost=estimates['lower'],N_hat_90_upper_cost=estimates['upper'],
                        N_hat_90_possible=possible_N,N_hat_90_guaranteed=guaranteed_N,
                        unchanged_under_discarded_work_bound=possible_N==guaranteed_N))
    main_committed=sum(q['physical_transitions'] for q in totals)
    campaign_committed=sum(q['physical_transitions'] for q in totals+diagnostics)
    charged_committed=sum(q['algorithm_charged_transitions'] for q in totals)
    charged_extra_upper=sum(v[1] for q in recoveries for v in q['extra_uncommitted_transitions_per_method_bounds'].values())
    result=dict(status='PASS',paired_learning_tasks=350,distinct_real_learning_jobs=len(main_ids),distinct_real_learning_attempts=len(attempts),learning_records_checked=records_checked,
        main_learning_Slurm_states=dict(Counter(jobs[j]['state'] for j in main_ids)),
        all_learning_attempt_Slurm_states=dict(Counter(jobs[j]['state'] for j in attempts)),
        complete_outputs_committed_by_TIMEOUT_jobs=valid_timeout_outputs,
        bounded_checkpoint_recoveries=recoveries,execution_aware_sample_requirement_bounds=endpoint_bounds,
        all_burns_and_Stein_priming_blocks_counted=True,
        committed_main_physical_transitions=main_committed,
        unique_main_physical_transitions_bounds=[main_committed,main_committed+extra_upper],
        main_algorithm_committed_data_transitions=charged_committed,
        main_algorithm_charged_transitions_bounds=[charged_committed,charged_committed+charged_extra_upper],phase_totals=totals,
        diagnostics=diagnostics,diagnostic_physical_transitions=sum(q['physical_transitions'] for q in diagnostics),
        entire_campaign_physical_transitions=campaign_committed if not extra_upper else None,
        entire_campaign_physical_transitions_bounds=[campaign_committed,campaign_committed+extra_upper],
        analytic_oracles_model_perturbations_and_saved_result_reports_primitive_transitions=0,
        accounting_source_sha256=sha(accounting),
        note='Every algorithm is charged its own complete cumulative learning budget. Unjournaled discarded collection is additionally bounded and its possible effect on sample thresholds is explicitly checked. Shared initial/full-rank estimators are counted once in physical simulator work. Historical CE production samples remain under their original campaign. Auxiliary analytic TIMEOUT has zero primitive transitions; all timeout occupancy is charged.')
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'transition_and_execution_audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    with (destination/'execution_provenance_by_pair.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
    with (destination/'execution_cost_success_envelopes.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(execution_success_envelopes[0]));w.writeheader();w.writerows(execution_success_envelopes)
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--accounting',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();audit(a.root,a.accounting,a.output)
