"""Authorized22:55 saved-fit CE gains/gaps. Compute nodes only,0new data."""
from __future__ import annotations
import argparse
import csv
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
import numpy as np
import frozen_engine as e

BASE=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101')


def q(values,p):
    ordered=sorted(values)
    if not ordered:return None
    position=(len(ordered)-1)*p;lo=math.floor(position);hi=math.ceil(position)
    if lo==hi or ordered[lo]==ordered[hi]:return ordered[lo]
    if math.isinf(ordered[hi]):return ordered[hi]
    return ordered[lo]+(position-lo)*(ordered[hi]-ordered[lo])


def ratio(row):
    d,t=row['dense_gap'],row['truncated_gap']
    if math.isinf(d) and math.isinf(t):return None
    if t==0:return 1. if d==0 else math.inf
    return d/t


def bootstrap(rows,both_stable,random,repetitions):
    systems=sorted({r['system'] for r in rows});assert len(systems)==8
    clusters=[[r for r in rows if r['system']==system] for system in systems]
    assert all(len(group)==4 for group in clusters)
    medians=[];invalid=0
    for _ in range(repetitions):
        values=[]
        for index in random.integers(0,8,size=8):
            for row in clusters[index]:
                if both_stable and not (row['dense_stable'] and row['truncated_stable']):continue
                value=ratio(row)
                if value is not None:values.append(value)
        if values:medians.append(q(values,.5))
        else:invalid+=1
    return dict(ci_low=q(medians,.025),ci_high=q(medians,.975),
                bootstrap_valid=len(medians),bootstrap_invalid=invalid,
                bootstrap_repetitions=repetitions)


def write_csv(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def main():
    e.require_compute()
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    assert args.out.resolve().is_relative_to(BASE/'X6a') and not args.out.exists()
    config=json.loads(args.config.read_text(encoding='utf-8-sig'))
    args.out.mkdir(parents=True);(args.out/'gains').mkdir();start=time.monotonic()
    rows=[];certificates={};artifacts=[];max_check=0.;fits=0
    for index in range(32):
        folder=BASE/'X6a/formal'/('task-'+str(index))
        done=json.loads((folder/'DONE.json').read_text());assert done['status']=='COMPLETE'
        for spec in done['task']['cells']:
            assert spec['role']=='formal'
            cell=folder/(spec['family']+'-n'+str(spec['n']))
            receipt=json.loads((cell/'receipt.json').read_text())
            assert receipt['status']=='COMPLETE' and receipt['spec']==spec
            assert receipt['config_sha256']==config['X6a_config_sha256']
            assert receipt['source_sha256']==config['X6a_estimator_sha256']
            assert receipt['engine_sha256']==e.sha(e.__file__)
            model_path=cell/'model.npz';assert e.sha(model_path)==receipt['model_sha256']
            with np.load(model_path) as archive:
                s={name:archive[name].copy() for name in archive.files}
            s['certificate']=receipt['certificate']
            n=spec['n'];family=spec['family'];system=spec['system']
            p0=float(np.linalg.norm(s['P0'],2))
            vstar=float(np.sum((s['Pstar']@(s['A']-s['B']@s['Kstar']))**2))
            key=(family,n,system)
            if key in certificates:
                assert np.isclose(certificates[key]['P0_op'],p0,rtol=1e-12,atol=1e-12)
                assert np.isclose(certificates[key]['v_star'],vstar,rtol=1e-12,atol=1e-12)
            else:certificates[key]=dict(family=family,n=n,system=system,P0_op=p0,v_star=vstar)
            for N in config['ce_budgets']:
                entry=next(a for a in receipt['artifacts'] if a['path']=='CE-'+str(N)+'.npz')
                fit=cell/entry['path'];assert e.sha(fit)==entry['sha256'];fits+=1
                with np.load(fit) as archive:
                    theta=np.concatenate((archive['Ahat'],archive['Bhat']),axis=1)
                row=dict(family=family,n=n,system=system,seed=spec['seed'],N=N,
                    primitive_transitions=N+512,input_fit_sha256=entry['sha256'],
                    input_model_sha256=receipt['model_sha256'])
                gains={}
                for arm,rank in [('dense',n),('truncated',2)]:
                    try:
                        gain=e.ce_learner(theta,n,s['Q'],s['R'],rank)
                        result=e.assess(s,gain);gains['K_'+arm]=gain
                        if result['stable']:
                            gap=float(result['gap']);relative=float(result['relative_gap'])
                            direct=float(result['cost']-np.trace(s['Pstar']))
                            discrepancy=abs(gap-direct)/max(1.,abs(gap),abs(direct))
                            assert discrepancy<=1e-7,'Direct-cost/quadratic-gap disagreement'
                            max_check=max(max_check,discrepancy)
                        else:gap=relative=math.inf
                        row.update({arm+'_stable':bool(result['stable']),arm+'_gap':gap,
                                    arm+'_relative_gap':relative,arm+'_rho':result['rho'],
                                    arm+'_failure':'' if result['stable'] else 'unstable_gain'})
                    except (np.linalg.LinAlgError,ValueError,ArithmeticError) as exc:
                        row.update({arm+'_stable':False,arm+'_gap':math.inf,
                                    arm+'_relative_gap':math.inf,arm+'_rho':None,
                                    arm+'_failure':repr(exc)})
                name=f'{family}-n{n}-s{system}-seed{spec["seed"]}-N{N}.npz'
                path=args.out/'gains'/name;np.savez_compressed(path,**gains)
                artifacts.append(dict(path='gains/'+name,sha256=e.sha(path)))
                row['gain_path']='gains/'+name;row['gain_sha256']=artifacts[-1]['sha256']
                row['paired_ratio']=ratio(row);rows.append(row)
    assert fits==1280 and len(rows)==1280 and len(certificates)==64
    groups=defaultdict(list)
    for row in rows:groups[(row['family'],row['n'],row['N'])].append(row)
    summaries=[]
    for (family,n,N),group in sorted(groups.items()):
        assert len(group)==32
        common=dict(family=family,n=n,N=N,primitive_transitions=N+512,full_pairs=32,
            dense_stable=sum(r['dense_stable'] for r in group),
            truncated_stable=sum(r['truncated_stable'] for r in group),
            both_stable=sum(r['dense_stable'] and r['truncated_stable'] for r in group),
            both_failed=sum(not r['dense_stable'] and not r['truncated_stable'] for r in group),
            dense_only_failed=sum(not r['dense_stable'] and r['truncated_stable'] for r in group),
            truncated_only_failed=sum(r['dense_stable'] and not r['truncated_stable'] for r in group))
        for arm in ['dense','truncated']:
            for metric in ['gap','relative_gap']:
                values=[r[arm+'_'+metric] for r in group]
                for suffix,p in [('median',.5),('q25',.25),('q75',.75)]:
                    common[arm+'_'+metric+'_'+suffix]=q(values,p)
        for kind,both_stable in [('both_stable',True),('failure_inclusive',False)]:
            subset=[r for r in group if (r['dense_stable'] and r['truncated_stable'])] if both_stable else group
            values=[ratio(r) for r in subset if ratio(r) is not None]
            row=dict(common,ratio_kind=kind,ratio_pairs=len(values),
                dropped_pairs=32-len(values),ratio_median=q(values,.5),ratio_q25=q(values,.25),ratio_q75=q(values,.75))
            row.update(bootstrap(group,both_stable,e.rng(620,1 if family=='S' else 2,n,N,int(both_stable)),config['bootstrap_repetitions']))
            summaries.append(row)
    cert_summary=[]
    for family in ['S','U']:
        for n in [24,36,48,72]:
            selected=[r for r in certificates.values() if r['family']==family and r['n']==n]
            assert len(selected)==8
            row=dict(family=family,n=n,independent_systems=8)
            for key in ['P0_op','v_star']:
                for suffix,p in [('median',.5),('q25',.25),('q75',.75)]:row[key+'_'+suffix]=q([r[key] for r in selected],p)
            cert_summary.append(row)
    write_csv(args.out/'observations.csv',rows);write_csv(args.out/'summary.csv',summaries)
    write_csv(args.out/'system_certificates.csv',list(certificates.values()))
    write_csv(args.out/'certificate_summary.csv',cert_summary)
    manifest=dict(status='COMPLETE',scope='SAVED_OLS_FITS_ZERO_NEW_TRANSITIONS',
        job=os.environ['SLURM_JOB_ID'],rows=len(rows),cells=len(groups),models=256,
        independent_systems=64,OLS_fits=fits,gain_artifacts=artifacts,
        bootstrap_repetitions=config['bootstrap_repetitions'],new_primitive_transitions=0,
        max_normalized_cost_gap_discrepancy=max_check,
        source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),config_sha256=e.sha(args.config),
        seconds=time.monotonic()-start,files={p.name:e.sha(p) for p in args.out.glob('*.csv')})
    e.save(args.out/'verification.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k!='gain_artifacts'}))


if __name__=='__main__':main()
