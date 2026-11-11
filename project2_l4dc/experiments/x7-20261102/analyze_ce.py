"""Frozen X7 saved-data audits and descriptive inference; compute nodes only."""
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
import ce_fullrank as c


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def q(values,p):
    """Type7 linear quantile,with positive infinity retained,not interpolated away."""
    values=sorted(values)
    if not values:return None
    index=(len(values)-1)*p;lo=int(math.floor(index));hi=int(math.ceil(index))
    if lo==hi:return float(values[lo])
    if math.isinf(values[hi]):return float(values[hi])
    return float(values[lo]+(index-lo)*(values[hi]-values[lo]))


def ratio(dense,other):
    if math.isinf(dense) and math.isinf(other):return None
    if math.isinf(other):return 0.
    if math.isinf(dense):return math.inf
    if other==0:return 1. if dense==0 else math.inf
    return dense/other


def inspect(config_path,raw,out,n,spectrum):
    c.require_compute();config_path=Path(config_path);raw=Path(raw);out=Path(out)
    assert out.resolve().is_relative_to(c.OUT) and not out.exists()
    config=json.loads(config_path.read_text());c.verify_sources(config)
    assert config['status']=='FORMAL_FROZEN'
    out.mkdir(parents=True);started=time.monotonic()
    records=[];models=[];tails=[];verified=0;max_fit_error=0.;max_policy_error=0.;max_cost_error=0.
    case=f'n{n}-{spectrum}'
    registry={};artifact_digests=[]
    for index in range(32):
        system=config['formal_systems'][index//4];trial=config['formal_seeds'][index%4]
        bundle_path=raw/f'task-{index}'/'BUNDLE_DONE.json'
        bundle=json.loads(bundle_path.read_text())
        assert bundle['status']=='COMPLETE' and bundle['index']==index
        assert bundle['config_sha256']==e.sha(config_path)
        assert bundle['source_sha256']==config['scientific_sources']['x7_driver.py']
        assert len(bundle['paths'])==4 and bundle['system']==system and bundle['trial']==trial
        entry=next(row for row in bundle['paths'] if row['case']==case)
        path=raw/f'task-{index}'/case
        assert e.sha(path/'DONE.json')==entry['done_sha256']
        done=json.loads((path/'DONE.json').read_text())
        spec=dict(experiment='X7',n=n,m=n,r=n,system=system,trial=trial,spectrum=spectrum)
        assert done['status']=='COMPLETE' and done['spec']==spec
        assert done['config_sha256']==e.sha(config_path)
        assert done['source_sha256']==config['scientific_sources']['ce_fullrank.py']
        assert done['engine_sha256']==config['scientific_sources']['frozen_engine.py']
        model_ref=config['model_registry'][f'{case}-s{system}']
        assert done['model_sha256']==model_ref['sha256']
        if system not in registry:
            model=c.load_model(model_ref['path'],model_ref['sha256'])
            registry[system]=model;cert=model['certificate']
            assert cert['system']==system and cert['n']==n and cert['spectrum']==spectrum
            assert cert['full_rank'] and cert['P0_op']<=1.5625+1e-10
            assert np.array_equal(model['K0'],np.zeros((n,n)))
            models.append(dict(n=n,spectrum=spectrum,system=system,
                rho_A=cert['rho_A'],P0_op=cert['P0_op'],P0_class_bound=1.5625,
                B_op=cert['B_op'],sigma_min=cert['singular_values'][-1],
                J0=cert['J0'],Jstar=cert['Jstar'],initial_gap=cert['initial_gap'],
                optimal_sensitivity_fro2=cert['optimal_sensitivity_fro2'],
                model_sha256=model_ref['sha256']))
            for k in range(n+1):
                tails.append(dict(n=n,spectrum=spectrum,system=system,k=k,
                    tau_k_squared=cert['tau2'][k],beta_k=cert['beta'][k],
                    theorem_c_eff='UNSPECIFIED_NOT_NUMERICALLY_CALIBRATED'))
        model=registry[system]
        assert done['primitive_transitions']==max(c.prefixes(config,n))+config['ce_burn']
        assert [a['N'] for a in done['artifacts']]==c.prefixes(config,n)
        seen=[]
        for artifact in done['artifacts']:
            N=artifact['N'];archive=path/artifact['path']
            assert e.sha(archive)==artifact['sha256'];verified+=1
            checkpoint=json.loads((path/f'prefix-{N:09d}.json').read_text())
            assert checkpoint['status']=='COMPLETE_PREFIX' and checkpoint['spec']==spec
            assert checkpoint['config_sha256']==e.sha(config_path)
            assert checkpoint['source_sha256']==config['scientific_sources']['ce_fullrank.py']
            assert checkpoint['engine_sha256']==config['scientific_sources']['frozen_engine.py']
            assert checkpoint['model_sha256']==model_ref['sha256']
            assert checkpoint['artifact']==artifact and checkpoint['N']==N
            assert checkpoint['transitions']==N+512
            with np.load(archive,allow_pickle=False) as data:
                fit={key:data[key].copy() for key in
                    ['theta','theta1','theta2','gram','cross','half_gram','half_cross','x','rng_state']}
                fit['N']=N
                for key,left,right in [
                    ('theta',fit['gram'],fit['cross']),
                    ('theta1',fit['half_gram'],fit['half_cross']),
                    ('theta2',fit['gram']-fit['half_gram'],fit['cross']-fit['half_cross'])]:
                    calculated=e.fit_model(left,right)
                    error=float(np.linalg.norm(calculated-fit[key])/max(1.,np.linalg.norm(calculated)))
                    max_fit_error=max(max_fit_error,error);assert error<1e-11
                assert np.allclose(data['estimated_B_singular_values'],
                    np.linalg.svd(fit['theta'][:,n:],compute_uv=False),rtol=1e-11,atol=1e-12)
                arm_records,policies,_=c.evaluate_fit(model,fit,spec,config)
                assert len(arm_records)==len(checkpoint['records'])
                for expected,record in zip(arm_records,checkpoint['records']):
                    for key in ['mode','k','kind','label','constant','N','transitions']:
                        assert record[key]==expected[key],key
                    for key in ['threshold','noise_proxy']:
                        if record[key] is None:assert expected[key] is None
                        else:assert abs(record[key]-expected[key])<1e-11*max(1.,abs(record[key]),abs(expected[key]))
                    assert record['stable']==expected['stable']
                    if record['stable']:
                        assert math.isfinite(record['gap']) and record['gap']>=0
                        assert math.isfinite(record['relative_gap']) and record['relative_gap']>=0
                        for key in ['gap','relative_gap','cost','rho']:
                            left=record[key];right=expected[key]
                            assert abs(left-right)<1e-9*max(1.,abs(left),abs(right)),key
                        max_cost_error=max(max_cost_error,expected['cost_identity_error'])
                    else:assert record['gap'] is None and record['relative_gap'] is None
                    key=record['policy_key']
                    if key in policies:
                        error=float(np.linalg.norm(data[key]-policies[key])/max(1.,np.linalg.norm(policies[key])))
                        max_policy_error=max(max_policy_error,error);assert error<1e-11
                    else:assert key not in data
                    row=dict(record,full_denominator=32,model_sha256=model_ref['sha256'],
                        tau_k_squared=model['certificate']['tau2'][record['k']],
                        beta_k=model['certificate']['beta'][record['k']],
                        unscaled_tradeoff=record['k']*(2*n)/N+model['certificate']['tau2'][record['k']],
                        tradeoff_label='Uncalibrated shape,not a numeric gap prediction',
                        smallest_retained_true_sigma=model['certificate']['singular_values'][record['k']-1] if record['k'] else None,
                        next_true_sigma=model['certificate']['beta'][record['k']])
                    records.append(row)
            seen.extend(checkpoint['records'])
            artifact_digests.append(dict(path=str(archive),sha256=artifact['sha256']))
        assert seen==done['records']
    expected_arms=len([k for k in config['fixed_rank_pool'] if k<n])+5
    assert len(records)==32*6*expected_arms and verified==192 and len(models)==8
    write_csv(out/'records.csv',records);write_csv(out/'models.csv',models);write_csv(out/'tails.csv',tails)
    proof=dict(status='COMPLETE',scope='SAVED_DATA_ONLY_ZERO_NEW_TRANSITIONS',n=n,spectrum=spectrum,
        config_sha256=e.sha(config_path),source_sha256=e.sha(__file__),
        core_sha256=e.sha(c.__file__),engine_sha256=e.sha(e.__file__),
        records=len(records),models=len(models),verified_fit_policy_archives=verified,
        physical_training_transitions=32*(max(c.prefixes(config,n))+512),
        max_fit_relative_error=max_fit_error,max_policy_relative_error=max_policy_error,
        max_cost_identity_error=max_cost_error,zero_new_transitions=True,
        job=os.environ['SLURM_JOB_ID'],seconds=time.monotonic()-started,
        files={p.name:e.sha(p) for p in out.glob('*.csv')},artifact_digests=artifact_digests)
    c.save_new(out/'verification.json',proof)
    print(json.dumps({k:v for k,v in proof.items() if k!='artifact_digests'}))


INT_KEYS={'n','m','r','system','trial','k','N','transitions','full_denominator'}
FLOAT_KEYS={'gap','relative_gap','cost','rho','cost_identity_error','threshold','constant','noise_proxy',
    'tau_k_squared','beta_k','unscaled_tradeoff','smallest_retained_true_sigma','next_true_sigma',
    'rho_A','P0_op','P0_class_bound','B_op','sigma_min','J0','Jstar','initial_gap','optimal_sensitivity_fro2'}


def read_csv(path):
    with Path(path).open(encoding='utf-8',newline='') as stream:
        rows=[]
        for raw in csv.DictReader(stream):
            row={}
            for key,value in raw.items():
                if value=='':row[key]=None
                elif key in INT_KEYS:row[key]=int(value)
                elif key in FLOAT_KEYS:row[key]=float(value)
                elif key=='stable':row[key]=value=='True'
                else:row[key]=value
            rows.append(row)
        return rows


def log_slope(values,budgets):
    values=np.asarray(values,float)
    if not np.all(np.isfinite(values)&(values>0)):return None
    x=np.log(np.asarray(budgets,float));x=x-x.mean()
    return float(x@np.log(values)/(x@x))


def summarize(config_path,raw,out):
    c.require_compute();config_path=Path(config_path);raw=Path(raw);out=Path(out)
    assert out.resolve().is_relative_to(c.OUT) and not out.exists()
    config=json.loads(config_path.read_text());c.verify_sources(config)
    assert config['status']=='FORMAL_FROZEN';out.mkdir(parents=True)
    records=[];models=[];tails=[]
    for n in config['n_values']:
        for spectrum in config['spectra']:
            folder=raw/f'diagnostics-n{n}-{spectrum}'
            proof=json.loads((folder/'verification.json').read_text())
            assert proof['status']=='COMPLETE' and proof['source_sha256']==e.sha(__file__)
            assert proof['config_sha256']==e.sha(config_path)
            for name,destination in [('records.csv',records),('models.csv',models),('tails.csv',tails)]:
                assert e.sha(folder/name)==proof['files'][name]
                destination.extend(read_csv(folder/name))
    assert len(records)==10752 and len(models)==32 and len(tails)==1184
    summaries=[];ratios=[];pairs=[];orders=[];best_rows=[];slope_rows=[]
    for n in config['n_values']:
        for spectrum in config['spectra']:
            cell=[r for r in records if r['n']==n and r['spectrum']==spectrum]
            keys=[(system,trial) for system in config['formal_systems'] for trial in config['formal_seeds']]
            budgets=c.prefixes(config,n)
            by={(r['N'],r['mode'],r['system'],r['trial']):r for r in cell}
            fixed=['dense']+['k'+str(k) for k in config['fixed_rank_pool'] if k<n]
            modes=fixed+['adaptive_paper','adaptive_split','sensitivity_C0p5','sensitivity_C1p0']
            random=e.rng(config['bootstrap_seed_tag'],n,config['spectra'].index(spectrum))
            draws=random.integers(0,8,size=(config['bootstrap_repetitions'],8))
            indices=(draws[:,:,None]*4+np.arange(4)[None,None,:]).reshape(-1,32)
            medians={};boot_medians={}
            for N in budgets:
                dense=[by[N,'dense',system,trial] for system,trial in keys]
                for mode in modes:
                    ordered=[by[N,mode,system,trial] for system,trial in keys]
                    common=dict(n=n,spectrum=spectrum,N=N,transitions=N+512,mode=mode,
                        label=ordered[0]['label'],full=32,stable=sum(r['stable'] for r in ordered))
                    result=dict(common)
                    for metric in ['gap','relative_gap']:
                        values=[r[metric] if r['stable'] else math.inf for r in ordered]
                        for suffix,p in [('median',.5),('q25',.25),('q75',.75)]:
                            result[metric+'_'+suffix]=q(values,p)
                        medians[N,mode,metric]=result[metric+'_median']
                        boot_medians[N,mode,metric]=np.median(np.asarray(values)[indices],axis=1)
                    for suffix,p in [('median',.5),('q25',.25),('q75',.75)]:
                        result['order_'+suffix]=q([r['k'] for r in ordered],p)
                    result['chosen_zero']=sum(r['k']==0 for r in ordered)
                    result['chosen_dense']=sum(r['k']==n for r in ordered)
                    summaries.append(result)
                    if mode.startswith(('adaptive_','sensitivity_')):
                        order=dict(common)
                        for metric in ['k','threshold','smallest_retained_true_sigma','next_true_sigma']:
                            values=[r[metric] for r in ordered if r[metric] is not None]
                            order[metric+'_eligible']=len(values)
                            for suffix,p in [('median',.5),('q25',.25),('q75',.75)]:
                                order[metric+'_'+suffix]=q(values,p)
                        order['zero_order']=result['chosen_zero'];order['dense_order']=result['chosen_dense']
                        orders.append(order)
                    if mode=='dense':continue
                    flags=[(d['stable'],r['stable']) for d,r in zip(dense,ordered)]
                    values=[ratio(d['gap'] if d['stable'] else math.inf,
                                  r['gap'] if r['stable'] else math.inf) for d,r in zip(dense,ordered)]
                    count=dict(dense_stable=sum(a for a,b in flags),other_stable=sum(b for a,b in flags),
                        both_stable=sum(a and b for a,b in flags),both_failed=sum(not a and not b for a,b in flags),
                        dense_only_failed=sum(not a and b for a,b in flags),
                        other_only_failed=sum(a and not b for a,b in flags))
                    for (system,trial),d,r,value in zip(keys,dense,ordered,values):
                        pairs.append(dict(common,system=system,trial=trial,dense_stable=d['stable'],
                            other_stable=r['stable'],dense_gap=d['gap'] if d['stable'] else math.inf,
                            other_gap=r['gap'] if r['stable'] else math.inf,paired_ratio=value))
                    for kind in ['both_stable','failure_inclusive']:
                        valid=[value if value is not None and (kind!='both_stable' or all(flags[i]))
                               else None for i,value in enumerate(values)]
                        observed=[value for value in valid if value is not None]
                        boot=[];empty=0
                        for sample in indices:
                            sampled=[valid[int(i)] for i in sample if valid[int(i)] is not None]
                            if sampled:boot.append(q(sampled,.5))
                            else:empty+=1
                        ratios.append(dict(common,**count,ratio_kind=kind,ratio_pairs=len(observed),
                            paired_ratio_median=q(observed,.5),ci_low=q(boot,.025),ci_high=q(boot,.975),
                            bootstrap_valid=len(boot),bootstrap_empty=empty,bootstrap_repetitions=len(indices)))
                candidate=[(medians[N,mode,'gap'],by[(N,mode)+keys[0]]['k'],mode) for mode in fixed]
                best=min(candidate)
                truncated=min(row for row in candidate if row[2]!='dense')
                identified=math.isfinite(best[0]);trunc_identified=math.isfinite(truncated[0])
                best_rows.append(dict(n=n,spectrum=spectrum,N=N,transitions=N+512,
                    best_fixed_k=best[1] if identified else None,best_fixed_mode=best[2] if identified else None,
                    best_fixed_median_gap=best[0],best_truncated_k=truncated[1] if trunc_identified else None,
                    best_truncated_median_gap=truncated[0],includes_dense_in_fixed_set=True,
                    selection='POST_HOC group median;not available to learner;ties smaller k',
                    optimum_identified=identified,truncated_optimum_identified=trunc_identified))
            for mode in modes:
                for metric in ['gap','relative_gap']:
                    for window,selected in [('all_six',budgets),('last_three',budgets[-3:])]:
                        values=[medians[N,mode,metric] for N in selected]
                        point=log_slope(values,selected)
                        x=np.log(np.asarray(selected,float));x=x-x.mean()
                        matrix=np.vstack([boot_medians[N,mode,metric] for N in selected])
                        valid=np.all(np.isfinite(matrix)&(matrix>0),axis=0)
                        slopes=(x@np.log(matrix[:,valid])/(x@x)).tolist() if np.any(valid) else []
                        slope_rows.append(dict(n=n,spectrum=spectrum,mode=mode,metric=metric,window=window,
                            budgets=json.dumps(selected),median_gaps=json.dumps(values),
                            log_gap_log_N_slope=point,reference_one_over_N_slope=-1.,
                            identified=point is not None,bootstrap_ci_low=q(slopes,.025),
                            bootstrap_ci_high=q(slopes,.975),bootstrap_identified=len(slopes),
                            bootstrap_unidentified=len(indices)-len(slopes),
                            bootstrap_repetitions=len(indices),
                            interpretation='Descriptive OLS on full32 median gaps;CI conditional on finite-positive medians;no trimming'))
    assert len(summaries)==336 and len(ratios)==624 and len(orders)==96 and len(best_rows)==24 and len(slope_rows)==224 and len(pairs)==9984
    for name,rows in [('all_records',records),('model_certificates',models),('spectral_tails',tails),
        ('summary',summaries),('paired_ratios',ratios),('paired_records',pairs),
        ('adaptive_orders',orders),('posthoc_best_fixed',best_rows),('log_slopes',slope_rows)]:
        write_csv(out/(name+'.csv'),rows)
    proof=dict(status='COMPLETE',scope='SAVED_DATA_ONLY_ZERO_NEW_TRANSITIONS',
        source_sha256=e.sha(__file__),core_sha256=e.sha(c.__file__),
        engine_sha256=e.sha(e.__file__),config_sha256=e.sha(config_path),
        record_rows=len(records),summary_rows=len(summaries),ratio_rows=len(ratios),
        adaptive_order_rows=len(orders),posthoc_rows=len(best_rows),slope_rows=len(slope_rows),
        physical_training_transitions=37814272,zero_new_transitions=True,
        job=os.environ['SLURM_JOB_ID'],files={p.name:e.sha(p) for p in out.glob('*.csv')})
    c.save_new(out/'verification.json',proof);print(json.dumps(proof))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['inspect','summarize'])
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--n',type=int)
    parser.add_argument('--spectrum',choices=['geometric','polynomial'])
    args=parser.parse_args()
    if args.mode=='inspect':inspect(args.config,args.raw,args.out,args.n,args.spectrum)
    else:summarize(args.config,args.raw,args.out)
