"""Frozen X6b saved-data analysis. Compute nodes only; zero new transitions.

Diagnostics read simulator truth after training. No learned gain is modified.
Primary gaps retain the full32 denominator. Conditional paired ratios are
explicitly secondary. All ladder/bootstrap definitions follow PROTOCOL v2.
"""
import argparse
import csv
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
import frozen_engine as e

BASE=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101/X6b')
ARMS=['dense','truncated']


def q(values,p):
    ordered=sorted(values)
    if not ordered:return None
    position=(len(ordered)-1)*p;lo=math.floor(position);hi=math.ceil(position)
    if lo==hi or ordered[lo]==ordered[hi]:return ordered[lo]
    if math.isinf(ordered[hi]):return ordered[hi]
    return ordered[lo]+(position-lo)*(ordered[hi]-ordered[lo])


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def metrics(estimate,target):
    norm=float(np.linalg.norm(target,'fro'));singular=np.linalg.svd(target,compute_uv=False)
    sigma2=float(singular[1]);identifiable=sigma2>np.finfo(float).eps*max(target.shape)*singular[0]
    if norm==0:return dict(relative_error=None,rho_op=None,projection=None,sigma2=sigma2,identifiable=False)
    return dict(relative_error=float(np.linalg.norm(estimate-target,'fro')/norm),
        rho_op=float(np.linalg.norm(estimate-target,2)/sigma2) if identifiable else None,
        projection=float(np.sum(estimate*target)/(norm*norm)),sigma2=sigma2,
        target_fro=norm,identifiable=bool(identifiable))


def processing(g,z):
    values,u=np.linalg.eigh(g);gp=(u*np.maximum(values,0.))@u.T
    basis=np.linalg.svd(np.concatenate((gp,z),axis=1),full_matrices=False)[0][:,:2]
    gg=basis@(basis.T@gp@basis)@basis.T;zz=basis@(basis.T@z)
    return gp,gg,zz


def endpoint(s,k,record):
    if not record['stable']:
        return dict(D=None,action_gap=None,D_over_gap=None,action_error_fro=None,
                    gap_decomposition_error=None,cost_identity_error=None)
    f=s['A']-s['B']@k;cov=solve_discrete_lyapunov(f,s['W'])
    p=solve_discrete_lyapunov(f.T,s['Q']+k.T@s['R']@k)
    basis=s['basis'];projected=basis@(basis.T@k);null=k-projected
    d=float(np.trace(null@cov@null.T));delta=projected-s['Kstar']
    weight=s['R']+s['B'].T@s['Pstar']@s['B']
    action=float(np.trace(cov@delta.T@weight@delta));gap=record['gap']
    decomposition=abs(gap-d-action)/max(1.,abs(gap))
    direct=float(np.trace(p)-np.trace(s['Pstar']))
    cost=abs(gap-direct)/max(1.,abs(gap),abs(direct))
    assert decomposition<1e-7 and cost<1e-7
    assert np.linalg.norm(s['B']@(k-projected))<1e-9*max(1.,np.linalg.norm(k))
    return dict(D=d,action_gap=action,D_over_gap=d/gap if gap else None,
        action_error_fro=float(np.linalg.norm(basis.T@(k-s['Kstar']),'fro')),
        gap_decomposition_error=decomposition,cost_identity_error=cost)


def inspect(config_path,raw,out,n):
    e.require_compute();assert not out.exists() and out.resolve().is_relative_to(BASE)
    config=json.loads(config_path.read_text());out.mkdir(parents=True);start=time.monotonic()
    assert config['status']=='FORMAL_FROZEN'
    expected=config['scientific_sources'];assert e.sha(e.__file__)==expected['frozen_engine.py']
    stages=[];ends=[];diagnostics=[];verified=0;primitive=0;continuity=0.;update_error=0.
    for group in [g for g in config['formal_groups'] if g['n']==n]:
        for index in range(32):
            root=raw/group['id']/f'task-{index}'
            group_done=json.loads((root/'DONE.json').read_text())
            assert group_done['status']=='COMPLETE' and group_done['config_sha256']==e.sha(config_path)
            assert group_done['source_sha256']==expected['formal_driver.py']
            assert group_done['actor_sha256']==expected['actor_paths.py']
            assert group_done['group']==group and group_done['index']==index
            system=config['formal_systems'][index//4];seed=config['formal_sampling_seeds'][index%4]
            model=config['model_registry'][f'n{n}-s{system}'];path=config_path.parent/model['path']
            assert e.sha(path)==model['sha256']
            with np.load(path) as archive:s={key:archive[key].copy() for key in archive.files}
            s['certificate']=model['certificate']
            assert len(group_done['paths'])==len(group['runs'])
            for run,receipt in zip(group['runs'],group_done['paths']):
                folder=root/receipt['path'];done_path=folder/'DONE.json'
                assert e.sha(done_path)==receipt['done_sha256']
                done=json.loads(done_path.read_text());alg=run['algorithm'];rung=run['rung']
                assert done['status']=='COMPLETE' and done['algorithm']==alg
                assert done['source_sha256']==expected['actor_paths.py']
                assert done['engine_sha256']==expected['frozen_engine.py']
                spec=done['spec'];assert (spec['n'],spec['system'],spec['seed'],spec['rung'])==(n,system,seed,rung)
                schedule=next(x for x in config['all_schedules'] if x['n']==n and x['rung']==rung)
                batches=schedule['batches'][alg];M=schedule['primitive_per_arm_per_algorithm']
                assert done['primitive_transitions']==dict(dense=M,truncated=M)
                assert len(done['records'])==2*(len(batches)+1) and len(done['artifacts'])==2*len(batches)
                by_key={(r['stage'],r['arm']):r for r in done['records']};assert len(by_key)==len(done['records'])
                artifacts={(r['stage'],r['arm']):r for r in done['artifacts']}
                previous={arm:s['K0'].copy() for arm in ARMS};dead=dict.fromkeys(ARMS,False)
                failure=dict.fromkeys(ARMS,None);padding=dict.fromkeys(ARMS,0);used=0
                for stage in range(len(batches)+1):
                    if stage:used+=(batches[stage-1]+17)*16
                    for arm in ARMS:
                        record=by_key[stage,arm];assert record['primitive_transitions']==used
                        base=dict(n=n,algorithm=alg,rung=rung,system=system,seed=seed,arm=arm,stage=stage,
                                  primitive_transitions=used,padding_transitions=record['padding_transitions'],
                                  stable=record['stable'],gap=record['gap'] if record['stable'] else math.inf,
                                  relative_gap=record['relative_gap'] if record['stable'] else math.inf,
                                  rho=record.get('rho'),padding_stage=record.get('padding_stage',False))
                        stages.append(base)
                        if stage:
                            artifact=artifacts[stage,arm];file=folder/artifact['path']
                            assert e.sha(file)==artifact['sha256'];verified+=1
                            with np.load(file) as archive:data={key:archive[key].copy() for key in archive.files}
                            difference=float(np.linalg.norm(data['K_before']-previous[arm]));continuity=max(continuity,difference)
                            assert difference==0 and record['padding_stage']==dead[arm]==artifact['padding_stage']
                            behavior=s['K0'] if dead[arm] else data['K_before']
                            assert np.array_equal(data['behavior'],behavior)
                            if dead[arm]:
                                padding[arm]+=(batches[stage-1]+17)*16
                                assert not record['stable'] and np.array_equal(data['K_after'],data['K_before'])
                                diagnostics.append(dict(base,diagnostic='PADDING_NOT_AN_UPDATE',eligible=False))
                            else:
                                candidate=e.actor_learner(data['K_before'],s['R'],data['Ghat'],data['Zhat'],arm,2,alg,.2)
                                difference=float(np.linalg.norm(candidate-data['K_after'])/max(1.,np.linalg.norm(candidate)))
                                update_error=max(update_error,difference);assert difference<1e-11
                                k=data['K_before'];f=s['A']-s['B']@k
                                p=solve_discrete_lyapunov(f.T,s['Q']+k.T@s['R']@k)
                                g=s['B'].T@p@s['B'];z=-s['B'].T@p@f
                                if alg=='NPG':
                                    variants=[('NPG_raw',data['Zhat'],z),
                                              ('NPG_applied',data['Zhat'] if arm=='dense' else e.trunc(data['Zhat'],2),z)]
                                else:
                                    gp,gg,zz=processing(data['Ghat'],data['Zhat'])
                                    target=np.concatenate((g,z),axis=1)
                                    variants=[('PI_raw',np.concatenate((data['Ghat'],data['Zhat']),axis=1),target),
                                        ('PI_clipped',np.concatenate((gp,data['Zhat']),axis=1),target),
                                        ('PI_joint_compressed',np.concatenate((gg,zz),axis=1),target)]
                                for name,estimate,target in variants:
                                    applied=(name=='NPG_applied' or (name=='PI_clipped' and arm=='dense')
                                             or (name=='PI_joint_compressed' and arm=='truncated'))
                                    diagnostics.append(dict(base,diagnostic=name,eligible=True,
                                        diagnostic_policy_stage=stage-1,learner_applied=applied,
                                        **metrics(estimate,target)))
                                if not record['stable']:failure[arm]=stage;dead[arm]=True
                            assert record['padding_transitions']==padding[arm]
                            previous[arm]=data['K_after']
                        if stage==len(batches):
                            ends.append(dict(base,first_failure_stage=failure[arm],
                                             **endpoint(s,previous[arm],record)))
                    if stage:
                        check=json.loads((folder/f'checkpoint-{stage:03d}.json').read_text())
                        cp=folder/f'checkpoint-{stage:03d}.npz'
                        assert e.sha(cp)==check['checkpoint_sha256'];verified+=1
                        assert check['status']=='COMPLETE_STAGE' and check['stage']==stage
                        assert check['source_sha256']==expected['actor_paths.py']
                        assert check['engine_sha256']==expected['frozen_engine.py']
                        assert check['dead']==dead and check['padding_transitions']==padding
                        assert check['total_primitive_transitions']==dict(dense=used,truncated=used)
                        with np.load(cp) as archive:
                            for arm in ARMS:assert np.array_equal(archive['K_'+arm],previous[arm])
                primitive+=2*M
    assert len(ends)==4*2*32*2 and len(stages)==4*32*(2*17+2*9)
    write_csv(out/'endpoints.csv',ends);write_csv(out/'stages.csv',stages)
    write_csv(out/'diagnostics.csv',diagnostics)
    proof=dict(status='COMPLETE',n=n,job=os.environ['SLURM_JOB_ID'],zero_new_transitions=True,
        training_primitive_transitions=primitive,endpoint_rows=len(ends),stage_rows=len(stages),
        diagnostic_rows=len(diagnostics),verified_artifacts=verified,max_K_continuity_error=continuity,
        max_update_relative_error=update_error,source_sha256=e.sha(__file__),config_sha256=e.sha(config_path),
        seconds=time.monotonic()-start,files={p.name:e.sha(p) for p in out.glob('*.csv')})
    e.save(out/'verification.json',proof);print(json.dumps(proof))


def cast(row):
    result={}
    for key,value in row.items():
        if value=='':result[key]=None
        elif value in ['True','False']:result[key]=value=='True'
        else:
            try:result[key]=float(value)
            except ValueError:result[key]=value
    return result


def read_csv(path):
    with path.open(newline='',encoding='utf-8') as stream:return [cast(r) for r in csv.DictReader(stream)]


def paired_ratio(d,t):
    if math.isinf(d) and math.isinf(t):return None
    if t==0:return 1. if d==0 else math.inf
    return d/t


def summarize(config_path,root,out):
    e.require_compute();assert not out.exists() and out.resolve().is_relative_to(BASE)
    config=json.loads(config_path.read_text());out.mkdir(parents=True)
    endpoints=[];stages=[];diagnostics=[]
    for n in config['n_values']:
        folder=root/f'diagnostics-n{n}';proof=json.loads((folder/'verification.json').read_text())
        assert proof['status']=='COMPLETE' and proof['config_sha256']==e.sha(config_path)
        assert proof['source_sha256']==e.sha(__file__)
        for name,destination in [('endpoints.csv',endpoints),('stages.csv',stages),('diagnostics.csv',diagnostics)]:
            assert e.sha(folder/name)==proof['files'][name];destination.extend(read_csv(folder/name))
    summaries=[];pairs=[];attainment=[];epsilon_ratios=[];system_summaries=[]
    for n in config['n_values']:
        for alg,tag in [('NPG',20),('PI',21)]:
            # Identical draws for every rung, arm, ratio kind, and epsilon in this cell.
            random=e.rng(config['bootstrap_tag'],n,tag)
            draws=random.integers(0,8,size=(config['bootstrap_repetitions'],8))
            indices=(draws[:,:,None]*4+np.arange(4)[None,None,:]).reshape(-1,32)
            ladder={arm:[] for arm in ARMS};budgets=[]
            for rung in config['rungs']:
                group=[r for r in endpoints if r['n']==n and r['algorithm']==alg and r['rung']==rung]
                assert len(group)==64;by={(int(r['system']),int(r['seed']),r['arm']):r for r in group}
                ordered={arm:[by[s,t,arm] for s in config['formal_systems'] for t in config['formal_sampling_seeds']] for arm in ARMS}
                d,t=ordered['dense'],ordered['truncated'];M=int(d[0]['primitive_transitions']);budgets.append(M)
                flags=[(a['stable'],b['stable']) for a,b in zip(d,t)]
                ratios=[paired_ratio(a['gap'],b['gap']) for a,b in zip(d,t)]
                common=dict(n=n,algorithm=alg,rung=rung,primitive_per_arm=M,full_pairs=32,
                    dense_stable=sum(a for a,b in flags),truncated_stable=sum(b for a,b in flags),
                    both_stable=sum(a and b for a,b in flags),both_failed=sum(not a and not b for a,b in flags),
                    dense_only_failed=sum(not a and b for a,b in flags),
                    truncated_only_failed=sum(a and not b for a,b in flags),structural_factor=(n-2)/4)
                for arm in ARMS:
                    common[arm+'_padding_transitions_total']=sum(r['padding_transitions'] for r in ordered[arm])
                    common[arm+'_first_failure_stages']=json.dumps([r['first_failure_stage'] for r in ordered[arm]])
                    ladder[arm].append(np.asarray([r['relative_gap'] for r in ordered[arm]]))
                    for metric in ['gap','relative_gap']:
                        for suffix,p in [('median',.5),('q25',.25),('q75',.75)]:
                            common[f'{arm}_{metric}_{suffix}']=q([r[metric] for r in ordered[arm]],p)
                    for metric in ['D','action_gap','D_over_gap','action_error_fro']:
                        vs=[r[metric] for r in ordered[arm] if r[metric] is not None]
                        common[f'{arm}_{metric}_eligible']=len(vs)
                        common[f'{arm}_{metric}_median']=q(vs,.5)
                    for system in config['formal_systems']:
                        seed_rows=[r for r in ordered[arm] if r['system']==system];assert len(seed_rows)==4
                        item=dict(n=n,algorithm=alg,rung=rung,arm=arm,system=system,
                                  full_seeds=4,stable=sum(r['stable'] for r in seed_rows))
                        for metric in ['gap','relative_gap']:
                            for suffix,p in [('median',.5),('q25',.25),('q75',.75)]:
                                item[metric+'_'+suffix]=q([r[metric] for r in seed_rows],p)
                        system_summaries.append(item)
                for i,(a,b) in enumerate(zip(d,t)):
                    pairs.append(dict(common,system=a['system'],seed=a['seed'],dense_gap=a['gap'],
                        truncated_gap=b['gap'],dense_pair_stable=a['stable'],truncated_pair_stable=b['stable'],
                        paired_ratio=ratios[i]))
                for kind in ['both_stable','failure_inclusive']:
                    valid=[value if value is not None and (kind!='both_stable' or all(flags[i])) else None
                           for i,value in enumerate(ratios)]
                    values=[v for v in valid if v is not None];boot=[];invalid=0
                    for sample in indices:
                        vs=[valid[int(i)] for i in sample if valid[int(i)] is not None]
                        if vs:boot.append(q(vs,.5))
                        else:invalid+=1
                    summaries.append(dict(common,ratio_kind=kind,ratio_pairs=len(values),paired_ratio_median=q(values,.5),
                        ci_low=q(boot,.025),ci_high=q(boot,.975),bootstrap_invalid=invalid,
                        bootstrap_valid=len(boot),bootstrap_repetitions=len(indices)))
            for epsilon in config['relative_epsilons']:
                selected_boot={}
                for arm in ARMS:
                    successes=[int(np.count_nonzero(v<=epsilon)) for v in ladder[arm]]
                    qualified=[i for i,count in enumerate(successes) if count>=config['required_successes']]
                    observed=budgets[qualified[0]] if qualified else math.inf
                    boot=np.full(len(indices),math.inf)
                    for i,values in enumerate(ladder[arm]):
                        qualifies=np.sum(values[indices]<=epsilon,axis=1)>=config['required_successes']
                        boot[np.isinf(boot)&qualifies]=budgets[i]
                    selected_boot[arm]=boot
                    attainment.append(dict(n=n,algorithm=alg,arm=arm,relative_epsilon=epsilon,
                        required_successes=29,full=32,smallest_observed_budget=observed,
                        status='ATTAINED_ON_REGISTERED_LADDER' if qualified else 'RIGHT_CENSORED',
                        censored_above=budgets[-1] if not qualified else None,
                        successes_by_rung=json.dumps(successes),rungs=json.dumps(config['rungs']),
                        bootstrap_ci_low=q(boot,.025),bootstrap_ci_high=q(boot,.975),
                        bootstrap_censored=int(np.count_nonzero(np.isinf(boot))),bootstrap_repetitions=len(boot)))
                # A ratio of censored minima is not identified; retain this mass explicitly.
                identified=[float(d/t) for d,t in zip(selected_boot['dense'],selected_boot['truncated'])
                            if np.isfinite(d) and np.isfinite(t)]
                epsilon_ratios.append(dict(n=n,algorithm=alg,relative_epsilon=epsilon,
                    conditional_bootstrap_ratio_ci_low=q(identified,.025),conditional_bootstrap_ratio_ci_high=q(identified,.975),
                    bootstrap_both_attained=len(identified),bootstrap_not_both_attained=len(indices)-len(identified),
                    interpretation='Conditional diagnostic only; censoring retained in attainment.csv'))
    stage_summary=[]
    groups=defaultdict(list)
    for row in stages:groups[tuple(row[k] for k in ['n','algorithm','rung','arm','stage'])].append(row)
    for key,rows in sorted(groups.items()):
        assert len(rows)==32
        result=dict(zip(['n','algorithm','rung','arm','stage'],key),full=32,
                    stable=sum(r['stable'] for r in rows),padding=sum(r['padding_stage'] for r in rows))
        for metric in ['gap','relative_gap']:
            for suffix,p in [('median',.5),('q25',.25),('q75',.75)]:result[metric+'_'+suffix]=q([r[metric] for r in rows],p)
        stage_summary.append(result)
    diagnostic_summary=[];groups=defaultdict(list)
    for row in diagnostics:groups[tuple(row[k] for k in ['n','algorithm','rung','arm','stage','diagnostic'])].append(row)
    for key,rows in sorted(groups.items()):
        result=dict(zip(['n','algorithm','rung','arm','stage','diagnostic'],key),full_paths=32,
                    eligible=sum(r['eligible'] for r in rows),observed_rows=len(rows))
        for metric in ['rho_op','relative_error','projection']:
            valid=[r[metric] for r in rows if r.get(metric) is not None]
            result[metric+'_eligible']=len(valid);result[metric+'_median']=q(valid,.5)
            result[metric+'_q25']=q(valid,.25);result[metric+'_q75']=q(valid,.75)
        system_means=[]
        for system in config['formal_systems']:
            vs=[r.get('projection') for r in rows if r['system']==system and r.get('projection') is not None]
            if vs:system_means.append(float(np.mean(vs)))
        result['projection_systems']=len(system_means)
        result['projection_mean_of_available_system_means']=float(np.mean(system_means)) if system_means else None
        result['projection_system_se']=float(np.std(system_means,ddof=1)/math.sqrt(len(system_means))) if len(system_means)>1 else None
        diagnostic_summary.append(result)
    for name,rows in [('endpoints',endpoints),('stages',stages),('diagnostics',diagnostics),('summary',summaries),
                      ('paired_endpoints',pairs),('attainment',attainment),('epsilon_ratios',epsilon_ratios),
                      ('stage_summary',stage_summary),('diagnostic_summary',diagnostic_summary)]:write_csv(out/(name+'.csv'),rows)
    write_csv(out/'system_summaries.csv',system_summaries)
    proof=dict(status='COMPLETE',scope='SAVED_DATA_ONLY_ZERO_NEW_TRANSITIONS',job=os.environ['SLURM_JOB_ID'],
        source_sha256=e.sha(__file__),config_sha256=e.sha(config_path),endpoint_rows=len(endpoints),
        paired_cells=len(summaries),attainment_cells=len(attainment),
        max_gap_decomposition_error=max(r['gap_decomposition_error'] or 0 for r in endpoints),
        max_cost_identity_error=max(r['cost_identity_error'] or 0 for r in endpoints),
        files={p.name:e.sha(p) for p in out.glob('*.csv')})
    e.save(out/'verification.json',proof);print(json.dumps(proof))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['inspect','summarize'])
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--n',type=int)
    args=parser.parse_args()
    if args.mode=='inspect':inspect(args.config,args.raw,args.out,args.n)
    else:summarize(args.config,args.raw,args.out)
