"""Draft X6a REPORT, for a separately accepted compute-node report job only.

Reads immutable estimates. No training or new trajectory samples. Hierarchical
summaries preserve systems as the independent unit; never pool32 seeds as32
independent systems. A missing cell is a coverage error, not an exclusion.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path
import numpy as np
import frozen_engine as e


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def left_angle(estimate,target,rank=2):
    actual=np.linalg.svd(estimate,full_matrices=False)[0][:,:rank]
    truth=np.linalg.svd(target,full_matrices=False)[0][:,:rank]
    # Residual form avoids cancellation near perfect alignment.
    return float(min(1.,np.linalg.norm(actual-truth@(truth.T@actual),2)))


def metrics(estimate,target):
    delta=estimate-target; norm=float(np.linalg.norm(target,'fro'))
    singular=np.linalg.svd(target,compute_uv=False)
    sigma2=float(singular[1]); tolerance=np.finfo(float).eps*max(target.shape)*singular[0]
    identifiable=sigma2>tolerance
    return dict(relative_error=float(np.linalg.norm(delta,'fro')/norm),
                rho_op=float(np.linalg.norm(delta,2)/sigma2) if identifiable else None,
                left_sin_theta=left_angle(estimate,target) if identifiable else None,
                projection=float(np.sum(estimate*target)/(norm*norm)),
                sigma2=sigma2,truth_fro=norm,identifiable=bool(identifiable))


def pi_pair(g,z,rank=2):
    values,u=np.linalg.eigh(g)
    gp=(u*np.maximum(values,0.))@u.T
    basis=np.linalg.svd(np.concatenate((gp,z),axis=1),full_matrices=False)[0][:,:rank]
    gg=basis@(basis.T@gp@basis)@basis.T
    zz=basis@(basis.T@z)
    return np.concatenate((gp,z),axis=1),np.concatenate((gg,zz),axis=1)


def quantile(values,q):
    """Linear finite quantiles, with extended-real upper endpoints for failures."""
    values=sorted(values);position=(len(values)-1)*q
    lo=int(math.floor(position));hi=int(math.ceil(position))
    if lo==hi or values[lo]==values[hi]:return values[lo]
    if math.isinf(values[hi]):return values[hi]
    return values[lo]+(position-lo)*(values[hi]-values[lo])


def summarize(rows):
    per_system=[];primary=[]
    by_system=defaultdict(list)
    for row in rows:
        key=tuple(row[k] for k in ['role','family','n','N','algorithm','arm','system'])
        by_system[key].append(row)
    keys=['role','family','n','N','algorithm','arm','system']
    for key,values in sorted(by_system.items()):
        assert len(values)==4 and len({r['seed'] for r in values})==4
        result=dict(zip(keys,key));result['seeds']=4
        result['finite_seeds']=sum(np.isfinite(r['relative_error']) for r in values)
        for metric in ['relative_error','rho_op','left_sin_theta','paired_error_ratio']:
            vs=[r[metric] for r in values if r.get(metric) is not None]
            if vs:
                result[metric+'_median']=quantile(vs,.5)
                result[metric+'_q25']=quantile(vs,.25)
                result[metric+'_q75']=quantile(vs,.75)
                result[metric+'_count']=len(vs)
        ps=[r['projection'] for r in values if r.get('projection') is not None]
        if len(ps)==4 and np.isfinite(ps).all():
            result['projection_mean']=float(np.mean(ps))
            result['projection_se']=float(np.std(ps,ddof=1)/math.sqrt(4))
        per_system.append(result)
    groups=defaultdict(list)
    for row in per_system:
        key=tuple(row[k] for k in keys[:-1]);groups[key].append(row)
    for key,values in sorted(groups.items()):
        result=dict(zip(keys[:-1],key));expected=8 if result['role']=='formal' else 2
        assert len(values)==expected
        result['systems']=expected;result['seeds_per_system']=4
        result['finite_observations']=sum(r['finite_seeds'] for r in values)
        result['full_observations']=expected*4
        for metric in ['relative_error','rho_op','left_sin_theta','paired_error_ratio']:
            vs=[r[metric+'_median'] for r in values if metric+'_median' in r]
            if vs:
                result[metric+'_median']=quantile(vs,.5)
                result[metric+'_q25']=quantile(vs,.25)
                result[metric+'_q75']=quantile(vs,.75)
                result[metric+'_systems']=len(vs)
        ps=[r['projection_mean'] for r in values if 'projection_mean' in r]
        if len(ps)==expected:
            result['projection_mean']=float(np.mean(ps))
            result['projection_se']=float(np.std(ps,ddof=1)/math.sqrt(expected))
            result['projection_independent_units']=expected
        primary.append(result)
    return per_system,primary


def analyze(raw,config_path,out):
    e.require_compute()
    assert not out.exists(),'Never replace a report; use a new version.'
    config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    assert config['blocks']==[2048,8192,32768,131072,524288]
    expected_engine='9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989'
    assert e.sha(e.__file__)==expected_engine
    rows=[];certificates=[];checked=0;source_hashes=set();equivalence=[]
    for task_index,task in enumerate(config['formal_tasks']):
        task_root=raw/'formal'/('task-'+str(task_index))
        done=json.loads((task_root/'DONE.json').read_text())
        assert done['status']=='COMPLETE' and done['task']==task
        for spec in task['cells']:
            folder=task_root/(spec['family']+'-n'+str(spec['n']))
            receipt=json.loads((folder/'receipt.json').read_text())
            assert receipt['status']=='COMPLETE' and not receipt['timing_only']
            assert receipt['spec']==spec
            assert receipt['config_sha256']==e.sha(config_path)
            assert receipt['engine_sha256']==expected_engine
            source_hashes.add(receipt['source_sha256'])
            assert e.sha(folder/'model.npz')==receipt['model_sha256']
            for artifact in receipt['artifacts']:
                assert e.sha(folder/artifact['path'])==artifact['sha256'];checked+=1
            stein_grid=config['stein_blocks_by_n'][str(spec['n'])]
            assert len(receipt['artifacts'])==len(stein_grid)+len(config['blocks'])
            truth=np.load(folder/'model.npz')
            a,b,k,p=truth['A'],truth['B'],truth['K0'],truth['P0']
            f=a-b@k;g=b.T@p@b;z=-b.T@p@f
            target_joint=np.concatenate((g,z),axis=1)
            certificates.append(dict(spec,**receipt['certificate']))
            for N in stein_grid:
                stein=np.load(folder/('Stein-'+str(N)+'.npz'))
                ce=np.load(folder/('CE-'+str(N)+'.npz')) if N in config['blocks'] else None
                dense_pi,trunc_pi=pi_pair(stein['G'],stein['Z'])
                # Check exact actor processing using an arbitrary known R,K.
                reference=e.actor_learner(k,truth['R'],stein['G'],stein['Z'],
                                          'truncated',2,'PI',0.)
                candidate=np.linalg.solve(truth['R']+trunc_pi[:,:spec['n']],
                                            trunc_pi[:,:spec['n']]@k-trunc_pi[:,spec['n']:])
                rel=float(np.linalg.norm(reference-candidate)/max(1.,np.linalg.norm(reference)))
                assert rel<1e-10
                equivalence.append(rel)
                pairs=[('NPG',stein['Z'],e.trunc(stein['Z'],2),z),
                       ('PI',dense_pi,trunc_pi,target_joint)]
                if ce is not None:
                    pairs.append(('CE',ce['Bhat'],e.trunc(ce['Bhat'],2),b))
                for algorithm,dense,truncated,target in pairs:
                    d=metrics(dense,target);t=metrics(truncated,target)
                    ratio=d['relative_error']/t['relative_error'] if t['relative_error'] else math.inf
                    for arm,result in [('dense',d),('truncated',t)]:
                        rows.append(dict(spec,N=N,algorithm=algorithm,arm=arm,
                            actual_transitions=N+config['ce_burn'] if algorithm=='CE'
                            else (N+17)*config['horizon'][spec['family']],
                            paired_error_ratio=ratio,**result))
                raw_joint=np.concatenate((stein['G'],stein['Z']),axis=1)
                rows.append(dict(spec,N=N,algorithm='PI_raw',arm='dense',
                    actual_transitions=(N+17)*config['horizon'][spec['family']],
                    paired_error_ratio=None,**metrics(raw_joint,target_joint)))
    assert len(source_hashes)==1,'Mixed collector versions are forbidden.'
    assert len(rows)==12800 and checked==3520
    systems,summary=summarize(rows)
    calibration=[]
    for family in ['S','U']:
        for n in config['n_values']:
            for algorithm in ['NPG','PI','PI_raw']:
                candidates=[r for r in summary if r['role']=='calibration' and
                    r['family']==family and r['n']==n and r['algorithm']==algorithm
                    and r['arm']=='dense']
                assert len(candidates)==len(config['stein_blocks_by_n'][str(n)])
                qualified=sorted(r['N'] for r in candidates if
                    r.get('rho_op_systems')==2 and r['rho_op_median']<=1)
                calibration.append(dict(family=family,n=n,algorithm=algorithm,
                    smallest_N=qualified[0] if qualified else None,
                    status='QUALIFIED' if qualified else 'RIGHT_CENSORED',
                    threshold=1.,censored_above_N=None if qualified else max(config['stein_blocks_by_n'][str(n)]),
                    statistic='median_of_two_system_seed_medians',
                    pilots=','.join(map(str,config['calibration_systems'][family]))))
    out.mkdir(parents=True)
    write_csv(out/'observations.csv',rows)
    write_csv(out/'system_summaries.csv',systems)
    write_csv(out/'summary.csv',summary)
    write_csv(out/'calibration.csv',calibration)
    write_csv(out/'certificates.csv',certificates)
    manifest=dict(status='COMPLETE',scope='SAVED_DATA_ONLY_ZERO_NEW_TRANSITIONS',
        job=os.environ['SLURM_JOB_ID'],rows=len(rows),cells=320,stein_prefixes=1920,ce_prefixes=1600,
        estimates_verified=checked,collector_sha256=next(iter(source_hashes)),
        source_sha256=e.sha(__file__),engine_sha256=expected_engine,
        config_sha256=e.sha(config_path),max_actor_PI_processing_difference=max(equivalence),
        files={p.name:e.sha(p) for p in out.glob('*.csv')})
    e.save(out/'verification.json',manifest)
    print(json.dumps(manifest))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--raw',required=True,type=Path)
    parser.add_argument('--config',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();analyze(args.raw,args.config,args.out)
